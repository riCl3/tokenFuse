"""Isolated demo of the Redis sliding-window budget tracking.

Run from the project root:  .venv\\Scripts\\python.exe scripts\\demo_budget.py
No API server or database needed -- only Redis (Docker container tokenfuse-redis).

The window stores spend in micro-USD (USD * 1e6) so sub-cent LLM costs are
not lost to rounding.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.redis_client import redis
from app.services.budget_service import check_budget, record_usage

PROJECT_ID = 1
WINDOW_SECONDS = 8
BUDGET_UNITS = 1_000_000  # $1 per window
WARN_PCT = 0.8


def fmt(units: int) -> str:
    return f"${units / 1_000_000:.2f}"


async def record(label: str, cost_usd: float) -> None:
    await record_usage(PROJECT_ID, cost_usd, window_seconds=WINDOW_SECONDS)
    s = await check_budget(PROJECT_ID, BUDGET_UNITS, WARN_PCT, window_seconds=WINDOW_SECONDS)
    print(f"  {label:<34} used {fmt(s.used_units):>8} / {fmt(s.budget_units)} -> {s.status.upper()}")


async def main() -> None:
    key = f"budget:{PROJECT_ID}"
    await redis.delete(key)
    print(f"window={WINDOW_SECONDS}s  budget={fmt(BUDGET_UNITS)}  warn at {fmt(int(BUDGET_UNITS * WARN_PCT))}")

    print("1) Accumulating spend (each event $0.40):")
    await record("+ $0.40", 0.40)
    await asyncio.sleep(0.3)
    await record("+ $0.40", 0.40)
    await asyncio.sleep(0.3)
    await record("+ $0.40", 0.40)

    print("2) Still inside the window, spend keeps counting (no boundary reset):")
    await asyncio.sleep(3)
    await record("+ $0.40 (4s later)", 0.40)

    print(f"3) Wait {WINDOW_SECONDS}s -- the window slides, old events expire:")
    await asyncio.sleep(WINDOW_SECONDS + 1)
    s = await check_budget(PROJECT_ID, BUDGET_UNITS, WARN_PCT, window_seconds=WINDOW_SECONDS)
    print(f"  after window elapsed:      used {fmt(s.used_units)} -> {s.status.upper()} (old events pruned)")
    await record("+ $0.40 (fresh window)", 0.40)

    await redis.delete(key)
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())