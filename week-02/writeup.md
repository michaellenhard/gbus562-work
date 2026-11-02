## What I Built
I used Claude Code to build prompt-lab.html, a single-file web app that sends prompts to Claude (claude-sonnet-5) through the Anthropic API. It has a password-style API key field that never saves the key, an optional system prompt, a conversation log that shows exactly what Claude sees, a New Conversation button, and an Export button that downloads the conversation as Markdown. I used it to run four prompting tasks for Wildframe Coffee Roasters, starting a new conversation for each, and saved each export in the runs folder.

## Why This Approach
Task 1 - Technique: zero-shot
The perk ideas task is an open-ended brainstorm with many good answers and no single correct output to imitate. The Brand Kit has no example of a perk, and giving an example would likely make the ideas cluster around it, so a clear zero-shot prompt with the brand context and format rules was the best fit.

Task 2 - Technique: one-shot
Bean cards must follow an exact house format with the same labels in the same order. A format is fully visible in a single example, and the Brand Kit contains exactly one bean card, so one example showed the model the whole layout without anything extra to infer.

Task 3 - Technique: few-shot
Customer replies depend on Wildframe's voice, which is hard to describe in words but easy to recognize. Using all four past replies from the Brand Kit gave the model varied examples, so it could pick up the shared tone (short sentences, honest, a little irreverent) instead of copying one reply's template.

Task 4 - Technique: chain-of-thought
Choosing the pop-up location is a decision with trade-offs and a budget constraint, not a writing task. Asking the model to calculate rent, revenue, and net results step by step, with the location data included in the prompt, made its reasoning visible and let me check the math myself.

## Example Run
Model: claude-sonnet-5

### You

You are a business analyst for Wildframe Coffee Roasters. Wildframe can run one four-week pop-up stand this spring, with a total rent budget of $5,000 for the four weeks. Here is weekly data from comparable past events:

Riverside Farmers Market: 9,000 visitors per week; 2% of visitors buy; average sale $14 (mostly whole-bean bags); rent $900 per week.
Union Station concourse: 30,000 visitors per week; 0.5% of visitors buy; average sale $6 (mostly single cups); rent $2,000 per week.
Campus library atrium: 6,000 visitors per week; 3% of visitors buy; average sale $5 (single cups); rent $600 per week.

Work through this step by step before recommending:
1. Calculate the total four-week rent for each location and check it against the $5,000 budget.
2. Calculate weekly revenue and four-week revenue for each location.
3. Calculate four-week revenue minus rent for each location.
4. Compare the options and decide.

End your response with a single line that starts with "Recommendation:" followed by the location's name. Put nothing after that line.

### Claude

# Step 1: Four-Week Rent Calculation

| Location | Weekly Rent | × 4 Weeks | Within $5,000 Budget? |
|---|---|---|---|
| Riverside Farmers Market | $900 | $3,600 | ✅ Yes |
| Union Station concourse | $2,000 | $8,000 | ❌ No — exceeds budget by $3,000 |
| Campus library atrium | $600 | $2,400 | ✅ Yes |

Union Station is already disqualified on budget grounds alone, but I'll calculate revenue for completeness/comparison.

# Step 2: Weekly and Four-Week Revenue

**Riverside Farmers Market**
- Buyers/week: 9,000 × 2% = 180
- Weekly revenue: 180 × $14 = $2,520
- 4-week revenue: $2,520 × 4 = **$10,080**

**Union Station concourse**
- Buyers/week: 30,000 × 0.5% = 150
- Weekly revenue: 150 × $6 = $900
- 4-week revenue: $900 × 4 = **$3,600**

**Campus library atrium**
- Buyers/week: 6,000 × 3% = 180
- Weekly revenue: 180 × $5 = $900
- 4-week revenue: $900 × 4 = **$3,600**

# Step 3: Four-Week Revenue Minus Rent

| Location | Revenue | Rent | Net Profit |
|---|---|---|---|
| Riverside Farmers Market | $10,080 | $3,600 | **$6,480** |
| Union Station concourse | $3,600 | $8,000 | –$4,400 (and over budget) |
| Campus library atrium | $3,600 | $2,400 | **$1,200** |

# Step 4: Comparison and Decision

- **Union Station** is eliminated immediately: it blows the $5,000 budget on rent alone ($8,000), and even ignoring budget, it would lose money.
- **Campus library atrium** fits comfortably in budget and turns a modest profit ($1,200), leaving $2,600 of budget unused — but the smaller foot traffic and low average sale cap its upside.
- **Riverside Farmers Market** uses $3,600 of the $5,000 budget (leaving a small cushion), and dramatically outperforms the other two: 180 buyers/week at a much higher average ticket ($14 vs. $5–$6) drives $10,080 in four-week revenue — more than 2.5x the next-best option — and a net profit of $6,480, over 5x higher than Campus library atrium.

Riverside wins on every meaningful metric: it's within budget, generates the highest revenue, and delivers by far the highest net profit.

Recommendation: Riverside Farmers Market

## Reflection
Each technique produced a result that met its required format on the first try, but the tasks showed different strengths. Chain-of-thought made the biggest difference in Task 4. Union Station has by far the most visitors, so a quick answer could have picked it, but the step-by-step math showed that its $8,000 rent breaks the $5,000 budget and loses money, while Riverside Farmers Market nets about $6,480. Because the reasoning was visible, I could verify every number. The few-shot replies in Task 3 matched Wildframe's voice well, but one reply claimed the decaf is Swiss Water processed, a fact that is not in the Brand Kit. Examples can teach tone, but they cannot supply facts, so a human still has to check claims before posting. The choice I am least sure of is zero-shot for Task 1. The ideas were on-brand, but a few felt generic, like discounts and early access. Next time I would try adding a constraint, such as requiring at least two sustainability-focused perks, to push the ideas further from the obvious ones.
