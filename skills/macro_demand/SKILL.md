---
id: macro_demand
name: Macro & Demand Drivers
when_to_use: >
  Use for MACROECONOMIC context (BoE base rate, unemployment) and DEMAND
  drivers (office occupancy / hybrid working, flight-to-quality, ESG /
  sustainability). Examples: "how are interest rates affecting demand",
  "what's the hybrid-working impact", "is flight-to-quality still a thing".
datasets:
  - macro.csv
---

## What this skill covers
Quarterly macro indicators (BoE base rate %, UK unemployment %, central London
office occupancy % as a hybrid-working proxy) plus qualitative demand-driver
notes (flight-to-quality, ESG).

## How to analyze
1. Call `query_dataset` with id `macro_demand` and dataset `macro.csv`.
2. For a rate/occupancy trend, call `render_chart` with `type: "line"`.
3. Link macro to the office market: higher rates pressure valuations and
   development viability; rising occupancy supports demand; flight-to-quality
   concentrates demand in best-in-class, well-located, sustainable buildings.
4. For the latest rate decision or current data, call `web_search` and cite.

## Chart recipes
- Rate vs occupancy: `type: "line"`, x = quarter, two series
  (boe_base_rate_pct, london_office_occupancy_pct).

## Caveats
Seed figures are ILLUSTRATIVE, anchored to publicly reported ranges. Not a
proprietary feed. Label as illustrative. Not investment advice.
