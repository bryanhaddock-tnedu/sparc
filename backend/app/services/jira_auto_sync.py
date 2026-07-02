from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import SyncRun
from app.services.jira_rovo import jira_integration_status, run_live_jira_rovo_sync

logger = logging.getLogger("sparc.jira_auto_sync")
MORNING_SYNC_CUTOFF = time(hour=8)


def start_jira_auto_sync_scheduler(session_factory: Callable[[], Session], settings: Settings) -> asyncio.Task[None] | None:
    if not settings.jira_auto_sync_enabled:
        logger.info("Daily Jira actuals sync scheduler disabled")
        return None

    run_time = parse_daily_sync_time(settings.jira_auto_sync_time)
    task = asyncio.create_task(_jira_auto_sync_loop(session_factory, run_time, settings.jira_auto_sync_timezone))
    logger.info(
        "Daily Jira actuals sync scheduler enabled time=%s timezone=%s",
        settings.jira_auto_sync_time,
        settings.jira_auto_sync_timezone,
    )
    return task


async def stop_jira_auto_sync_scheduler(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def parse_daily_sync_time(value: str) -> time:
    try:
        hour_text, minute_text = value.strip().split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        return time(hour=hour, minute=minute)
    except (TypeError, ValueError) as exc:
        raise ValueError("JIRA_AUTO_SYNC_TIME must use HH:MM 24-hour format") from exc


def next_daily_run_at(now: datetime, run_time: time, timezone_name: str) -> datetime:
    local_timezone = ZoneInfo(timezone_name)
    local_now = now.astimezone(local_timezone)
    candidate = datetime.combine(local_now.date(), run_time, tzinfo=local_timezone)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def is_daily_sync_catch_up_window(now: datetime, run_time: time, timezone_name: str) -> bool:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    return run_time <= local_now.time() < MORNING_SYNC_CUTOFF


def has_live_sync_for_local_date(db: Session, local_date: date, timezone_name: str) -> bool:
    local_timezone = ZoneInfo(timezone_name)
    day_start = datetime.combine(local_date, time.min, tzinfo=local_timezone).astimezone(timezone.utc)
    day_end = (datetime.combine(local_date, time.min, tzinfo=local_timezone) + timedelta(days=1)).astimezone(timezone.utc)
    existing = db.scalar(
        select(SyncRun)
        .where(
            SyncRun.source == "jira",
            SyncRun.mode == "live",
            SyncRun.status.in_(("running", "completed")),
            SyncRun.started_at >= day_start,
            SyncRun.started_at < day_end,
        )
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    return existing is not None


async def _jira_auto_sync_loop(session_factory: Callable[[], Session], run_time: time, timezone_name: str) -> None:
    while True:
        now = datetime.now(timezone.utc)
        if is_daily_sync_catch_up_window(now, run_time, timezone_name):
            logger.info("Daily Jira actuals sync is in the morning catch-up window; running now")
        else:
            next_run = next_daily_run_at(now, run_time, timezone_name)
            sleep_seconds = max(0.0, (next_run - now).total_seconds())
            logger.info("Next daily Jira actuals sync scheduled for %s", next_run.isoformat())
            await asyncio.sleep(sleep_seconds)
        await asyncio.to_thread(run_scheduled_jira_actuals_sync, session_factory, timezone_name)


def run_scheduled_jira_actuals_sync(session_factory: Callable[[], Session], timezone_name: str) -> dict[str, object] | None:
    integration_status = jira_integration_status()
    if not integration_status["configured"]:
        logger.warning("Daily Jira actuals sync skipped because Jira integration is not configured")
        return None

    local_today = datetime.now(ZoneInfo(timezone_name)).date()
    with session_factory() as db:
        if has_live_sync_for_local_date(db, local_today, timezone_name):
            logger.info("Daily Jira actuals sync skipped because a live Jira sync already ran today")
            return None
        try:
            result = run_live_jira_rovo_sync(db)
            db.commit()
            logger.info(
                "Daily Jira actuals sync completed imported=%s skipped=%s deleted=%s",
                result.get("imported_worklogs"),
                result.get("skipped_unmapped_worklogs"),
                result.get("deleted_worklogs"),
            )
            return result
        except Exception:
            db.rollback()
            logger.exception("Daily Jira actuals sync failed")
            return None
