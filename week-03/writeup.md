## What I Built
I used Claude Code to build ask.py, a RAG tool that splits documents into chunks, stores them in a local Chroma database, retrieves the most relevant chunks for a question, and has Claude (claude-sonnet-5) answer only from those chunks with citations. To make it work with Larkfield Credit Union's documents, I added a --docs option to choose the document folder, a separate Chroma database for each folder, and a --save option that writes each run to a text file. I then made seven runs: Question 1 before and after fixing the document collection, and Questions 2 to 6.

## Why This Approach
Chunking method: structure
Makes sense on its own: Partly, because most chunks are a full section such as "Consumer Fee Schedule > Overdraft and returned item fees" that answers a question alone, but the intro chunks with only a title and version line carry little meaning by themselves.
Label and source: Both, because every retrieved chunk in my saved runs starts with its document title, section chunks also carry their heading, like "Fee Refund Guide for Member Service Staff > Refunds that need a branch manager", and each lists its source file. The exception is each document's intro chunk, which has only the title.
Short enough: Yes, because each chunk is a single section of a short policy document, and Claude Code measured the longest Larkfield chunk at 116 words, well under the roughly 190-word limit.

## Example Run
#1  score 0.626  source: consumer-fee-schedule.html
Consumer Fee Schedule > Wire transfers
- Incoming domestic wire transfer: $10.
- Incoming international wire transfer: $15.
- Outgoing domestic wire transfer: $25.
- Outgoing international wire transfer: $45. The receiving bank or an intermediary bank may deduct its own fees from the amount sent.

#2  score 0.610  source: fee-refund-guide.html
Fee Refund Guide for Member Service Staff > Refunds that need a branch manager
A refund needs the branch manager's approval when the fee is more than $30, when the member has already had a refund in the last 90 days, or when the member asks for several fees to be refunded at once. A branch manager may approve refunds of up to $150 in total for one member in any 90-day period.

#3  score 0.561  source: fee-refund-guide.html
Fee Refund Guide for Member Service Staff > What a member service representative can approve
A member service representative may approve a refund of a single fee of $30 or less without anyone else's approval. A representative may approve only one refund for the same member in any 90-day period.

#4  score 0.508  source: fee-refund-guide.html
Fee Refund Guide for Member Service Staff > Refunds that need the Member Services Director
Refunds of more than $150 in total for one member in any 90-day period need the Member Services Director's approval. So does any refund for a business account.

#5  score 0.459  source: fee-refund-guide.html
Fee Refund Guide for Member Service Staff > Recording a refund
Every refund must be recorded in the member's account notes with the fee, the amount refunded, the reason, and the name of the person who approved it. Refunds that are not recorded this way may be reversed during the monthly audit.
Larkfield Credit Union Member Services. Questions about this document: memberservices@larkfield.example

ANSWER
No. The outgoing international wire transfer fee is $45 [consumer-fee-schedule.html]. A member service representative can only approve a refund without further approval if the single fee is $30 or less [fee-refund-guide.html]. Since $45 exceeds that threshold, it requires branch manager approval [fee-refund-guide.html].

## Reflection
What was wrong: consumer-fee-schedule-v7.html was an outdated Version 7 fee schedule still marked current, and the Question 1 retrieved chunks showed it next to the Version 8 schedule, giving a $35 overdraft fee against the current $29, so Claude could not tell which was right.
How I fixed it: Moved consumer-fee-schedule-v7.html out of week-03/larkfield-docs into week-03/larkfield-archive, then rebuilt the Larkfield database, and the after run retrieved only the current version of the fee schedule and answered $29.
Prevention: Archive process, so whenever Larkfield publishes a new version of a document, the document owner moves the old version out of the shared drive's live folder into an archive the tool never reads.
Question 6: Declined, because the documents have no mortgage information, so retrieval returned only low-scoring, unrelated chunks such as share certificate dividend rates and checking fees, and Claude said the excerpts do not contain mortgage rates.
