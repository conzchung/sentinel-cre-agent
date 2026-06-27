---
id: market_news
name: Market News & Briefings
when_to_use: >
  Use for EMERGING NEWS, recent events, deals, or when the user wants a current
  market briefing / digest synthesised from the live web. Examples: "any news
  on Canary Wharf", "what's happening in the London office market this week",
  "summarise recent leasing deals".
---

## What this skill covers
Live, up-to-date London office market news and events, synthesised into a short
briefing with citations. This skill has NO seed dataset — it relies on
`web_search`.

## How to analyze
1. Call `web_search` with a focused query (e.g. "London office market news
   prime rents vacancy 2025", or a submarket-specific query).
2. Synthesise the results into a concise briefing: 3-6 bullet points grouped by
   theme (rents, vacancy, deals, development, macro).
3. ALWAYS cite sources using the citation indices returned by `web_search`.
4. If results are thin, run a second `web_search` with a refined query.
5. Be explicit about the date/recency of what you found.

## Output format
- Lead with a one-line market read.
- Then themed bullets, each with a citation index like [1].
- End with "Sources:" and the list of cited URLs.

## Caveats
News is only as current as the search results. State the recency. Not
investment advice.
