"""Ask questions of Copperline's documents (retrieval-augmented generation).

Usage:
    python week-03/ask.py "How long do I have to submit an expense report?"
    python week-03/ask.py --k 8 "What are the meal limits in Boston?"
    python week-03/ask.py --rebuild "..."      # re-index the documents first

The documents in week-03/copperline-docs are split into chunks, embedded with
Chroma's default local embedding model, and stored in week-03/chroma_db. For a
question, the most similar chunks are retrieved and printed, then Claude answers
using only those chunks and cites the source file for each fact.

The Anthropic API key is read only from the ANTHROPIC_API_KEY environment variable.
"""

import argparse
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import chromadb
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
DOCS_DIR = HERE / "copperline-docs"
DB_DIR = HERE / "chroma_db"
COLLECTION = "copperline_docs"
MODEL = "claude-sonnet-5"

CHUNK_CHARS = 1000   # target maximum characters per chunk
OVERLAP_CHARS = 150  # overlap when a long section has to be split


# ---------------------------------------------------------------- text extraction

class _HTMLText(HTMLParser):
    """Collects visible text from an HTML page as (kind, text) blocks.

    kind is "title" for <h1>, "heading" for <h2>-<h6>, or "text" for anything else.
    <style>, <script> and <head> content is skipped.
    """

    BLOCK_TAGS = {"p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                  "tr", "td", "th", "footer", "section", "br"}
    SKIP_TAGS = {"style", "script", "head", "title"}

    def __init__(self):
        super().__init__()
        self.blocks = []
        self._buf = []
        self._kind = "text"
        self._skip = 0

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if text:
            self.blocks.append((self._kind, text))
        self._buf = []
        self._kind = "text"

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip += 1
        elif tag in self.BLOCK_TAGS:
            self._flush()
            if tag == "h1":
                self._kind = "title"
            elif tag in {"h2", "h3", "h4", "h5", "h6"}:
                self._kind = "heading"
            elif tag == "li":
                self._buf.append("- ")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def html_sections(path):
    """Returns (doc_title, [(heading, text), ...]) for an HTML file."""
    parser = _HTMLText()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()

    title = path.stem.replace("-", " ").title()
    sections, heading, lines = [], "", []
    for kind, text in parser.blocks:
        if kind == "title":
            title = text
        elif kind == "heading":
            if lines:
                sections.append((heading, "\n".join(lines)))
            heading, lines = text, []
        else:
            lines.append(text)
    if lines:
        sections.append((heading, "\n".join(lines)))
    return title, sections


def pdf_sections(path):
    """Returns (doc_title, [(heading, text), ...]) for a PDF file.

    PDFs carry no heading markup, so short lines without ending punctuation that
    are followed by body text are treated as section headings.
    """
    reader = PdfReader(str(path))
    raw_lines = []
    for page in reader.pages:
        raw_lines.extend((page.extract_text() or "").splitlines())
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw_lines]
    lines = [ln for ln in lines if ln]

    title = path.stem.replace("-", " ").title()
    # Use the first line that matches the file name as the title when possible.
    for ln in lines[:5]:
        if ln.lower().replace(" ", "-") == path.stem.lower():
            title = ln
            break

    def looks_like_heading(ln):
        return len(ln) <= 60 and not re.search(r"[.,;:]$", ln) and len(ln.split()) <= 8

    sections, heading, body = [], "", []
    for ln in lines:
        if looks_like_heading(ln):
            if body:
                sections.append((heading, " ".join(body)))
                body = []
            heading = ln
        else:
            body.append(ln)
    if body:
        sections.append((heading, " ".join(body)))
    return title, sections


def split_long(text, size=CHUNK_CHARS, overlap=OVERLAP_CHARS):
    """Splits text longer than `size` into overlapping pieces on sentence boundaries."""
    if len(text) <= size:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces, current = [], ""
    for s in sentences:
        if current and len(current) + len(s) + 1 > size:
            pieces.append(current.strip())
            current = current[-overlap:] + " " + s
        else:
            current = (current + " " + s) if current else s
    if current.strip():
        pieces.append(current.strip())
    return pieces


def load_chunks(docs_dir):
    """Splits every .html/.htm/.pdf/.txt/.md file in docs_dir into chunks."""
    chunks = []
    files = sorted(p for p in docs_dir.iterdir() if p.is_file())
    for path in files:
        ext = path.suffix.lower()
        if ext in {".html", ".htm"}:
            title, sections = html_sections(path)
        elif ext == ".pdf":
            title, sections = pdf_sections(path)
        elif ext in {".txt", ".md"}:
            title = path.stem.replace("-", " ").title()
            text = path.read_text(encoding="utf-8", errors="replace")
            sections = [("", p.strip()) for p in re.split(r"\n\s*\n", text) if p.strip()]
        else:
            print(f"  skipping unsupported file: {path.name}", file=sys.stderr)
            continue

        n = 0
        for heading, body in sections:
            for piece in split_long(body):
                # Prefix each chunk with its document title and section so that
                # the chunk makes sense (and embeds well) on its own.
                header = f"{title}" + (f" > {heading}" if heading else "")
                chunks.append({
                    "id": f"{path.name}::{n}",
                    "text": f"{header}\n{piece}",
                    "source": path.name,
                    "section": heading,
                })
                n += 1
        print(f"  {path.name}: {n} chunks")
    return chunks


# ---------------------------------------------------------------- vector store

def get_collection(rebuild=False):
    client = chromadb.PersistentClient(path=str(DB_DIR))
    if rebuild:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
    collection = client.get_or_create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine"}
    )
    if collection.count() == 0:
        print(f"Building the database from {DOCS_DIR} ...")
        chunks = load_chunks(DOCS_DIR)
        if not chunks:
            sys.exit(f"No documents found in {DOCS_DIR}")
        collection.add(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[{"source": c["source"], "section": c["section"]} for c in chunks],
        )
        print(f"Stored {len(chunks)} chunks in {DB_DIR}\n")
    return collection


def retrieve(collection, question, k):
    res = collection.query(query_texts=[question], n_results=min(k, collection.count()))
    results = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        results.append({
            "text": doc,
            "source": meta["source"],
            "section": meta.get("section", ""),
            "score": 1.0 - dist,  # cosine similarity
        })
    return results


# ---------------------------------------------------------------- Claude

SYSTEM_PROMPT = """You answer questions about Copperline Manufacturing's internal documents.

You will be given numbered excerpts retrieved from those documents. Each excerpt names its source file.

Rules:
- Use only the information in the excerpts. Do not use outside knowledge or make assumptions about Copperline's policies.
- After each fact you state, cite its source file in square brackets, for example [travel-expense-policy.html].
- If the excerpts do not contain the answer, say clearly that the documents provided do not contain it. If they answer only part of the question, answer that part and say which part is not covered.
- If excerpts disagree, point out the disagreement and cite both.
- Be concise and direct."""


def ask_claude(question, results):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY is not set. Set it in your environment and try again.")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    excerpts = "\n\n".join(
        f'<excerpt rank="{i}" source="{r["source"]}">\n{r["text"]}\n</excerpt>'
        for i, r in enumerate(results, 1)
    )
    user_message = f"<excerpts>\n{excerpts}\n</excerpts>\n\nQuestion: {question}"

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.AuthenticationError:
        sys.exit("The API key in ANTHROPIC_API_KEY was rejected.")
    except anthropic.RateLimitError:
        sys.exit("Rate limited by the Anthropic API. Wait a moment and try again.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Anthropic API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Could not reach the Anthropic API. Check your internet connection.")

    if response.stop_reason == "refusal":
        return "Claude declined to answer this question."
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if response.stop_reason == "max_tokens":
        text += "\n\n[Answer was cut off at the token limit.]"
    return text


# ---------------------------------------------------------------- main

def main():
    # On Windows, output that is piped or captured defaults to cp1252, which garbles
    # characters such as em dashes. Always write UTF-8.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Ask a question of Copperline's documents.")
    parser.add_argument("question", nargs="*", help="the question to ask")
    parser.add_argument("--k", type=int, default=5, help="number of chunks to retrieve (default 5)")
    parser.add_argument("--rebuild", action="store_true", help="re-index the documents first")
    args = parser.parse_args()

    collection = get_collection(rebuild=args.rebuild)

    question = " ".join(args.question).strip()
    if not question:
        if args.rebuild:
            return
        parser.error("please give a question")

    results = retrieve(collection, question, args.k)

    print(f"Question: {question}\n")
    print("=" * 72)
    print(f"Retrieved chunks (top {len(results)})")
    print("=" * 72)
    for i, r in enumerate(results, 1):
        print(f"\n#{i}  score {r['score']:.3f}  source: {r['source']}")
        print("-" * 72)
        print(r["text"])

    print("\n" + "=" * 72)
    print(f"Answer ({MODEL})")
    print("=" * 72)
    print(ask_claude(question, results))


if __name__ == "__main__":
    main()
