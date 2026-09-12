# Customer validation plan

Draft; no interviews, customers, revenue, or usage claimed.

## Recruit

Find 10 engineers/CTOs at startups shipping containerized agents to enterprise customers. Seek recent security reviews, not general enthusiasm for sovereign AI. Ask three for a synthetic or sanitized workflow and access to the person who consumes the evidence. Do not ask for production credentials or customer data.

## Interview questions

1. Tell us about your most recent customer question concerning where an agent sends data.
2. What exactly did the customer ask, and who had to answer?
3. Show the sanitized evidence you used. What was missing?
4. How much engineering time did it take, and what was delayed?
5. Which firewalls, proxies, tracing tools, or scripts did you try?
6. Would destination-level evidence help, or do you actually need payload inspection, access permissions, or contractual assurances?
7. How often does the answer change? Who owns keeping it current?
8. What environment must a tool support before you can try it?
9. Who could approve a pilot, and what measurable outcome would justify payment?
10. Can we review one workflow and have the evidence consumer evaluate a sample report?

Ask about past behavior before showing the proposed product. Record objections and alternatives as carefully as positive reactions.

## Trial

Baseline the existing process. Have the engineer run a synthetic demo and their approved workflow, without coaching where possible. Measure time to first useful report, setup failures, missing destinations/labels, and reviewer questions answered. Ask them to return the next week; do not substitute an intention to reuse for observed reuse.

## Evidence ledger

| Team alias | Recent problem and date | Current workaround | Time/cost evidence | Evidence consumer | Trial outcome | Repeated use | Budget signal |
|---|---|---|---|---|---|---|---|
| Pending | — | — | — | — | — | — | — |

## Decision gate

Use PRD section 9. If destination evidence is insufficient for customer reviews, narrow the job or stop. If existing tooling already handles it, prefer integration or upstream work. Do not build a hosted dashboard to compensate for weak demand for the local tool.
