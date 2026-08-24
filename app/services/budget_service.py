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
-- ARGV[3] = event id, ARGV[4] = weight (micro-USD)
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


def window_key(project_id: int) -> str:
    return f"{KEY_PREFIX}:{project_id}"


def _now_ms() -> int:
    return int(time.time() * 1000)


MICRO_USD_PER_USD = 1_000_000


def usd_to_units(usd: float) -> int:
    return int(round(usd * MICRO_USD_PER_USD))


def window_budget_units(monthly_budget_usd: float, window_seconds: int) -> int:
    return int(usd_to_units(monthly_budget_usd) * window_seconds / SECONDS_PER_MONTH)


async def _record_pipeline(
    project_id: int, now_ms: int, window_ms: int, member: str, weight: int
) -> None:
    """Non-Lua record: prune + add as one pipelined batch.

    Upstash Redis does not support EVAL, so when redis_eval_available is False
    we use a pipeline instead. Slightly weaker atomicity than the Lua script
    (two commands, not one atomic script) - acceptable for the MVP.
    """
    key = window_key(project_id)
    cutoff = now_ms - window_ms
    async with redis.pipeline() as pipe:
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zadd(key, {member: now_ms})
        await pipe.execute()


async def _window_total_pipeline(project_id: int, now_ms: int, window_ms: int) -> int:
    """Non-Lua window total: prune, fetch all members, sum weights in Python."""
    key = window_key(project_id)
    cutoff = now_ms - window_ms
    async with redis.pipeline() as pipe:
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zrange(key, 0, -1)
        result = await pipe.execute()
    total = 0
    for member in result[1]:
        sep = member.find(":")
        if sep != -1:
            total += int(member[sep + 1 :])
    return total


async def record_usage(
    project_id: int, cost_usd: float, window_seconds: int | None = None
) -> None:
    if window_seconds is None:
        window_seconds = settings.budget_window_seconds
    weight = usd_to_units(cost_usd)
    member = f"evt-{_now_ms()}-{secrets.token_hex(4)}"
    now_ms = _now_ms()
    try:
        if settings.redis_eval_available:
            await _record_script(
                keys=[window_key(project_id)],
                args=[now_ms, window_seconds * 1000, member, weight],
            )
        else:
            await _record_pipeline(project_id, now_ms, window_seconds * 1000, member, weight)
    except Exception:
        # Redis unavailable — budget tracking silently degrades.
        pass


@dataclass
class BudgetStatus:
    status: str
    used_units: int
    budget_units: int


async def check_budget(
    project_id: int,
    budget_units: int,
    warn_pct: float,
    window_seconds: int | None = None,
) -> BudgetStatus:
    if window_seconds is None:
        window_seconds = settings.budget_window_seconds
    try:
        if settings.redis_eval_available:
            used = int(
                await _window_total_script(
                    keys=[window_key(project_id)],
                    args=[_now_ms(), window_seconds * 1000],
                )
            )
        else:
            used = await _window_total_pipeline(
                project_id, _now_ms(), window_seconds * 1000
            )
    except Exception:
        # If Redis is unreachable, default to zero usage so the
        # dashboard / proxy still works (budget checks become no-ops).
        used = 0

    status = "ok"
    if used >= budget_units:
        status = "exceeded"
    elif used >= int(budget_units * warn_pct):
        status = "warn"

    return BudgetStatus(status=status, used_units=used, budget_units=budget_units)