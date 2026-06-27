---
id: supply_pipeline
name: Supply Pipeline
when_to_use: >
  Use for questions about NEW DEVELOPMENTS, REFURBISHMENTS, PRE-LETS, and
  upcoming COMPLETIONS / the construction pipeline by London submarket.
  Examples: "what's the supply pipeline in the City", "how much new space
  completes in 2025", "which schemes are pre-let".
datasets:
  - pipeline.csv
---

## What this skill covers
Notable development and refurbishment schemes by submarket, with status
(planned / under-construction / pre-let / completed), size (sq ft), expected
completion year, and pre-let percentage.

## How to analyze
1. Call `query_dataset` with id `supply_pipeline` and dataset `pipeline.csv`.
   Filter by `submarket`, `status`, or `completion_year` as needed.
2. To show the pipeline by year, aggregate `size_sqft` by `completion_year`
   and call `render_chart` with `type: "bar"`.
3. To compare submarkets, group by `submarket`.
4. Note the development risk: high pre-let % means lower speculative risk.
5. For schemes or news beyond this list, call `web_search` and cite sources.

## Chart recipes
- Completions by year: `type: "bar"`, x = completion_year, y = total size_sqft.
- Pipeline by submarket: `type: "bar"`, x = submarket, y = total size_sqft.

## Caveats
Seed figures are ILLUSTRATIVE, anchored to publicly reported scheme data.
Not a proprietary feed. Label as illustrative. Not investment advice.
