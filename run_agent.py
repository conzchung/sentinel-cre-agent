"""CLI chat loop for the Sentinel market agent.

Usage: python run_agent.py
"""

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent"))

from market_agent import run_agent  # noqa: E402


async def chat():
    thread_id = str(uuid.uuid4())
    print("Sentinel — London office market agent. Type 'exit' to quit.\n")
    loop = asyncio.get_event_loop()
    while True:
        user = await loop.run_in_executor(None, input, "You: ")
        if user.strip().lower() in {"exit", "quit"}:
            break
        print("\nSentinel: ", end="", flush=True)
        async for chunk in run_agent(message=user, thread_id=thread_id):
            text = chunk["ai_response"]
            # Charts are interactive and only render in the web UI; in the CLI
            # show a placeholder instead of the base64 <CHART> blob.
            if text.startswith("<CHART>"):
                print("[interactive chart rendered — view in the web UI]", end="", flush=True)
                continue
            # Print raw tagged stream; tags make plan/action/sources visible.
            print(text, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    asyncio.run(chat())
