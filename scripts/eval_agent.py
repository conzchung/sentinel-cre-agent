"""Ad-hoc evaluation harness: runs Sentinel against a battery of questions that
map to the technical-test coverage areas, and records which skills/tools each
query triggered. Prints a compact transcript + a tool-usage matrix.

Run: python scripts/eval_agent.py
"""

import asyncio
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from market_agent import run_agent  # noqa: E402

# (label, coverage-area, question)
QUERIES = [
    ("Q1 rents-trend", "prime/Grade A rents",
     "How are City prime office rents trending over the last year? Show a chart."),
    ("Q2 vacancy-compare", "vacancy/availability",
     "Compare current vacancy rates across the City, West End, Canary Wharf and Midtown."),
    ("Q3 takeup", "leasing take-up",
     "What has leasing take-up looked like recently and which submarket is strongest?"),
    ("Q4 supply", "supply pipeline",
     "What's the London office supply pipeline — how much new space completes in 2025 and what's pre-let?"),
    ("Q5 macro", "macro drivers",
     "How are interest rates and the macro backdrop affecting London office demand?"),
    ("Q6 demand-why", "occupier demand (flight-to-quality/ESG/hybrid)",
     "Why is flight-to-quality such a big theme right now, and how do ESG and hybrid working factor in?"),
    ("Q7 news", "emerging news",
     "Any notable recent news or deals in the London office market?"),
    ("Q8 briefing", "multi-area briefing + planning",
     "Give me a full briefing on the London office market: rents, vacancy, supply, and the macro picture, with charts."),
]

ACTION_RE = re.compile(r"Action:\s*(\w+)")
SKILL_RE = re.compile(r"read_skill\b")


async def run_one(label, area, question):
    thread_id = str(uuid.uuid4())
    tools_called = []
    charts = 0
    response_chunks = []
    plan_seen = False

    async for chunk in run_agent(message=question, thread_id=thread_id):
        text = chunk["ai_response"]
        if text.startswith("<CHART>"):
            charts += 1
            continue
        if "<PLAN>" in text:
            plan_seen = True
        for m in ACTION_RE.finditer(text):
            tools_called.append(m.group(1))
        # collect response prose (strip tags)
        if "<RESPONSE>" in text or "</RESPONSE>" in text:
            text = text.replace("<RESPONSE>", "").replace("</RESPONSE>", "")
        if not text.lstrip().startswith("<"):
            response_chunks.append(text)

    full = "".join(response_chunks).strip()
    return {
        "label": label, "area": area, "question": question,
        "tools": tools_called, "charts": charts, "plan": plan_seen,
        "response": full,
    }


async def main():
    print("=" * 100)
    print("SENTINEL AGENT EVALUATION — London office market coverage")
    print("=" * 100)
    results = []
    for label, area, question in QUERIES:
        print(f"\n\n{'#' * 100}\n### {label}  |  coverage: {area}\n### Q: {question}\n{'#' * 100}")
        try:
            r = await run_one(label, area, question)
        except Exception as exc:  # noqa: BLE001
            print(f"!!! ERROR: {type(exc).__name__}: {exc}")
            results.append({"label": label, "area": area, "error": str(exc)})
            continue
        results.append(r)
        print(f"\n[tools called]: {r['tools']}")
        print(f"[charts rendered]: {r['charts']}   [plan used]: {r['plan']}")
        print(f"\n[response]:\n{r['response']}")

    # Summary matrix
    print("\n\n" + "=" * 100)
    print("TOOL-USAGE / COVERAGE MATRIX")
    print("=" * 100)
    header = f"{'query':<20}{'area':<48}{'charts':<8}{'plan':<6}tools"
    print(header)
    print("-" * 100)
    for r in results:
        if "error" in r:
            print(f"{r['label']:<20}{r['area']:<48}{'ERR':<8}{'-':<6}{r['error'][:40]}")
            continue
        toolset = ",".join(dict.fromkeys(r["tools"]))  # unique, order-preserving
        print(f"{r['label']:<20}{r['area']:<48}{r['charts']:<8}{str(r['plan']):<6}{toolset}")


if __name__ == "__main__":
    asyncio.run(main())
