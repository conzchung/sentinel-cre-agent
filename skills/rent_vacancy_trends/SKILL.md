---
id: rent_vacancy_trends
name: Rent & Vacancy Trends
when_to_use: >
  Use for questions about prime or Grade A office RENTS, VACANCY / availability
  rates, or leasing TAKE-UP, broken down by London submarket (City, West End,
  Canary Wharf, Midtown/Fringe). Examples: "how are City prime rents trending",
  "compare vacancy across submarkets", "what's take-up looking like this year".
datasets:
  - prime_rents.csv
  - vacancy.csv
  - takeup.csv
---

## What this skill covers
Quarterly prime/Grade A rents (£/sq ft/yr), vacancy/availability rates (%), and
leasing take-up (sq ft) for four London office submarkets: City, West End,
Canary Wharf, Midtown/Fringe.

## How to analyze
1. Call `query_dataset` with this skill's id and the relevant dataset
   (`prime_rents.csv`, `vacancy.csv`, or `takeup.csv`). Filter by `submarket`
   and/or `quarter` as the question requires.
2. For a TREND question, pull the full quarterly series and call `render_chart`
   with `type: "line"` (x = quarter, y = the metric, one series per submarket).
3. For a COMPARISON across submarkets at a point in time, use
   `type: "grouped_bar"` or `type: "bar"`.
4. Always state the data's as-of quarter and that figures are illustrative.
5. For the WHY behind the numbers — what is driving rents/vacancy (flight-to-
   quality, ESG/EPC, hybrid working, submarket colour) — call `knowledge_search`
   over Sentinel's internal analyst-commentary corpus. This is our own curated
   house view and is SEPARATE from live web news; a briefing should draw on it,
   not just the figures.
6. If the user asks about CURRENT conditions beyond the latest seed quarter,
   call `web_search` to supplement and cite the sources. Treat `knowledge_search`
   (internal house view) and `web_search` (live external news) as DISTINCT
   sources — prefer citing both when explaining a trend.

## Chart recipes
- Rent trend: `type: "line"`, title "Prime office rent trend (£/sq ft)",
  one series per submarket, x = quarter, y = prime_rent_psf.
- Vacancy comparison: `type: "bar"`, title "Vacancy rate by submarket (%)",
  x = submarket, y = vacancy_rate_pct (latest quarter).

## Caveats
Seed figures are ILLUSTRATIVE, anchored to publicly reported CBRE/JLL/Savills
ranges. They are not a proprietary data feed. Label them as illustrative in any
answer. This is market commentary, not investment advice.
