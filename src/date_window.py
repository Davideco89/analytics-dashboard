"""Resolve the extraction window using complete New York calendar days."""

from datetime import date, datetime, time, timedelta
from statistics import median
from zoneinfo import ZoneInfo


def resolve_window(
    days: int,
    start_override: str | None = None,
    end_override: str | None = None,
    now: datetime | None = None,
    source_lag_days: int = 1,
) -> tuple[str, str]:
    if days <= 0:
        raise ValueError("NYC_311_WINDOW_DAYS must be greater than zero")
    if source_lag_days < 0:
        raise ValueError("NYC_311_SOURCE_LAG_DAYS must not be negative")

    if bool(start_override) != bool(end_override):
        raise ValueError(
            "Set both NYC_311_START_DATE and NYC_311_END_DATE, or neither"
        )

    if start_override and end_override:
        start = datetime.fromisoformat(start_override)
        end = datetime.fromisoformat(end_override)
        if start.tzinfo or end.tzinfo:
            raise ValueError(
                "Date overrides must be naive New York local timestamps"
            )
    else:
        if now is not None and now.tzinfo is None:
            raise ValueError("The supplied clock must have a time zone")
        local_now = (now or datetime.now(ZoneInfo("America/New_York")))
        local_today = local_now.astimezone(ZoneInfo("America/New_York")).date()
        end = datetime.combine(
            local_today - timedelta(days=source_lag_days), time.min
        )
        start = end - timedelta(days=days)

    if start >= end:
        raise ValueError(
            "NYC_311_START_DATE must be earlier than NYC_311_END_DATE"
        )

    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")


def validate_latest_day(
    end_date: str,
    latest_created_at: datetime | None,
    daily_counts: dict[date, int],
) -> None:
    """Reject a snapshot whose final day is visibly incomplete in the API."""
    expected_day = datetime.fromisoformat(end_date).date() - timedelta(days=1)
    if (
        latest_created_at is None
        or latest_created_at.date() != expected_day
        or latest_created_at.hour < 23
    ):
        raise RuntimeError(
            f"The source has not supplied the full final day ({expected_day}); "
            f"latest created_date={latest_created_at}. Previous snapshot retained."
        )

    preceding = [count for day, count in daily_counts.items() if day < expected_day]
    if preceding and daily_counts.get(expected_day, 0) < median(preceding) / 4:
        raise RuntimeError(
            f"The final day ({expected_day}) has only "
            f"{daily_counts.get(expected_day, 0)} rows compared with other days; "
            "source delivery may be incomplete. Previous snapshot retained."
        )
