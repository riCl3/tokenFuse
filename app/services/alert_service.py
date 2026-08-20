"""Burn-rate spike detection and alert delivery.

Detection model (budget-baseline spike):
  - recent rate  = spend in the last N seconds (from Redis) / N
  - baseline     = this project's budget-derived burn rate, i.e.
                   monthly_budget_usd prorated to micro-USD per second
  - SPIKE if recent rate >= multiplier * baseline AND recent spend >= a
    minimum floor (so we don't alert on tiny absolute amounts).

A per-project cooldown (Redis SET NX EX) stops alert storms: once an alert
fires for a project, no further alerts are sent for alert_cooldown_seconds.

Delivery is channel-agnostic: Telegram (if bot token + chat id configured),
a webhook (if a URL is configured), otherwise just a log line. Configuring
neither is valid and makes the service testable without any external keys.
"""

import logging
import time

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.redis_client import redis
from app.db.base import async_session_factory
from app.db.models import Project
from app.services import budget_service

logger = logging.getLogger(__name__)

settings = get_settings()

TELEGRAM_API = "https://api.telegram.org/bot"


async def recent_spend_units(project_id: int, seconds: int) -> int:
    """Total micro-USD spent by a project in the last `seconds`, from Redis.

    The budget window is a sorted set keyed `budget:<project_id>`; the score of
    each member is the event timestamp in ms, so we ask Redis for all members
    newer than now - seconds and sum the micro-USD weight baked into each
    member (`evt-<ms>-<rand>:<weight>`).
    """
    cutoff_ms = int(time.time() * 1000) - seconds * 1000
    members = await redis.zrangebyscore(
        budget_service.window_key(project_id), min=cutoff_ms, max="+inf"
    )
    total = 0
    for member in members:
        try:
            total += int(member.rsplit(":", 1)[1])
        except (ValueError, IndexError):
            continue
    return total


async def detect_spike(project: Project) -> dict | None:
    """Return an alert payload if the project is currently burning abnormally.

    None means: spend below the floor, or recent rate within `multiplier`x of
    the budget-derived rate.
    """
    recent_units = await recent_spend_units(project.id, settings.alert_recent_window_seconds)
    if recent_units < budget_service.usd_to_units(settings.alert_min_spend_usd):
        return None

    # Baseline burn rate this project is budgeted for, in micro-USD per second.
    budget_rate_per_sec = budget_service.window_budget_units(
        float(project.monthly_budget_usd), window_seconds=1
    )
    recent_rate_per_sec = recent_units / settings.alert_recent_window_seconds

    if recent_rate_per_sec < settings.alert_spike_multiplier * budget_rate_per_sec:
        return None

    return {
        "project_id": project.id,
        "project_name": project.name,
        "recent_units": recent_units,
        "recent_window_seconds": settings.alert_recent_window_seconds,
        "recent_rate_per_sec": recent_rate_per_sec,
        "budget_rate_per_sec": budget_rate_per_sec,
        "multiplier": settings.alert_spike_multiplier,
    }


async def _mark_in_cooldown(project_id: int) -> bool:
    """Atomically claim the cooldown; True if this call is allowed to alert."""
    got = await redis.set(
        f"alert:cooldown:{project_id}",
        int(time.time()),
        ex=settings.alert_cooldown_seconds,
        nx=True,
    )
    return bool(got)


def _format_alert(spike: dict) -> str:
    ratio = spike["recent_rate_per_sec"] / spike["budget_rate_per_sec"]
    return (
        f"TokenFuse burn-rate spike: project {spike['project_name']} (#{spike['project_id']})\n"
        f"Spent ${spike['recent_units'] / 1_000_000:.2f} in the last "
        f"{spike['recent_window_seconds']}s ({spike['recent_rate_per_sec']:.0f} units/s)\n"
        f"This is {ratio:.0f}x the budget-derived burn rate "
        f"({spike['budget_rate_per_sec']:.2f} units/s); threshold was "
        f"{spike['multiplier']:.0f}x."
    )


async def _send_telegram(message: str) -> None:
    """Post the alert to Telegram via the Bot API, if configured."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        logger.info("Telegram not configured; skipping")
        return
    url = f"{TELEGRAM_API}{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            url, json={"chat_id": settings.telegram_chat_id, "text": message}
        )
        response.raise_for_status()
        logger.info("Telegram alert sent (status=%s)", response.status_code)


async def _send_webhook(message: str, spike: dict) -> None:
    """POST the alert as JSON to a webhook URL, if configured."""
    if not settings.alert_webhook_url:
        logger.info("Webhook not configured; skipping")
        return
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            settings.alert_webhook_url, json={"text": message, "spike": spike}
        )
        response.raise_for_status()
        logger.info("Webhook alert sent (status=%s)", response.status_code)


async def run_alert_check() -> None:
    """Scan all active projects, alert on any spike (respecting cooldowns)."""
    async with async_session_factory() as session:
        result = await session.execute(select(Project).where(Project.is_active.is_(True)))
        projects = result.scalars().all()

    for project in projects:
        try:
            spike = await detect_spike(project)
            if spike is None:
                continue
            if not await _mark_in_cooldown(project.id):
                logger.info("project %s spike in cooldown; skipping", project.id)
                continue
            message = _format_alert(spike)
            logger.warning("BURN-RATE SPIKE: %s", message.replace("\n", " | "))
            await _send_telegram(message)
            await _send_webhook(message, spike)
        except Exception:
            logger.exception("alert check failed for project %s", project.id)


def create_scheduler():
    """Build the APScheduler AsyncIOScheduler with the burn-rate job wired in."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_alert_check,
        trigger="interval",
        seconds=settings.alert_check_interval_seconds,
        id="burn_rate_alert_check",
        max_instances=1,  # never let overlapping runs pile up
        coalesce=True,    # if a run is missed, skip it, don't backfill
    )
    return scheduler