import secrets
import time
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.redis_client import redis

settings = get_settings()

KEY_PREFIX = "budget"
SECONDS_PER_MONTH = 30 * 24 * 3600

_LUA_RECORD = """
-- KEYS[1] = window key, ARGV[1] = now_ms, ARGV[2] = window_ms
-- ARGV[3] = event id, ARGV[4] = weight (cents)
local cutoff = tonumber(ARGV[1]) - tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, cutoff)
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[3] .. ':' .. ARGV[4])
return 1
"""

_LUA_WINDOW_TOTAL = """
-- KEYS[1] = window key, ARGV[1] = now_ms, ARGV[2] = window_ms
local cutoff = tonumber(ARGV[1]) - tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, cutoff)
local members = redis.call('ZRANGE', KEYS[1], 0, -1)
local total = 0
for _, m in ipairs(members) do
  local sep = string.find(m, ':')
  if sep then
    total = total + tonumber(string.sub(m, sep + 1))
  end
end
return total
"""

_record_script = redis.register_script(_LUA_RECORD)
_window_total_script = redis.register_script(_LUA_WINDOW_TOTAL)


def _window_key(project_id: int) -> str:
    return f"{KEY_PREFIX}:{project_id}"


def _now_ms() -> int:
    return int(time.time() * 1000)


def usd_to_cents(usd: float) -> int:
    return int(round(usd * 100))


def window_budget_cents(monthly_budget_usd: float, window_seconds: int) -> int:
    return int(usd_to_cents(monthly_budget_usd) * window_seconds / SECONDS_PER_MONTH)


async def record_usage(
    project_id: int, cost_usd: float, window_seconds: int | None = None
) -> None:
    if window_seconds is None:
        window_seconds = settings.budget_window_seconds
    weight = usd_to_cents(cost_usd)
    member = f"evt-{_now_ms()}-{secrets.token_hex(4)}"
    await _record_script(
        keys=[_window_key(project_id)],
        args=[_now_ms(), window_seconds * 1000, member, weight],
    )


@dataclass
class BudgetStatus:
    status: str
    used_cents: int
    budget_cents: int


async def check_budget(
    project_id: int,
    budget_cents: int,
    warn_pct: float,
    window_seconds: int | None = None,
) -> BudgetStatus:
    if window_seconds is None:
        window_seconds = settings.budget_window_seconds
    used = int(
        await _window_total_script(
            keys=[_window_key(project_id)],
            args=[_now_ms(), window_seconds * 1000],
        )
    )

    status = "ok"
    if used >= budget_cents:
        status = "exceeded"
    elif used >= int(budget_cents * warn_pct):
        status = "warn"

    return BudgetStatus(status=status, used_cents=used, budget_cents=budget_cents)