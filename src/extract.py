from __future__ import annotations

import csv
import logging
import os
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.date_window import resolve_window, validate_latest_day


load_dotenv()

API_URL = os.getenv(
    "NYC_311_API_URL",
    "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
)
WINDOW_DAYS = int(os.getenv("NYC_311_WINDOW_DAYS", "7"))
SOURCE_LAG_DAYS = int(os.getenv("NYC_311_SOURCE_LAG_DAYS", "1"))
START_OVERRIDE = os.getenv("NYC_311_START_DATE") or None
END_OVERRIDE = os.getenv("NYC_311_END_DATE") or None
PAGE_SIZE = int(os.getenv("NYC_311_PAGE_SIZE", "10000"))
OUTPUT_PATH = Path(
    os.getenv("NYC_311_RAW_PATH", "data/raw/nyc_311.csv")
)

FIELDS = (
    "unique_key",
    "created_date",
    "closed_date",
    "agency",
    "agency_name",
    "complaint_type",
    "descriptor",
    "location_type",
    "incident_zip",
    "city",
    "status",
    "due_date",
    "resolution_description",
    "resolution_action_updated_date",
    "borough",
    "community_board",
    "council_district",
    "open_data_channel_type",
    "latitude",
    "longitude",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def validate_config() -> None:
    if PAGE_SIZE <= 0:
        raise ValueError("NYC_311_PAGE_SIZE must be greater than zero")


def build_session() -> requests.Session:
    retry_policy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods={"GET"},
    )

    session = requests.Session()
    session.mount(
        "https://",
        HTTPAdapter(max_retries=retry_policy),
    )
    session.headers["User-Agent"] = "analytics-dashboard/1.0"

    app_token = os.getenv("SODA_APP_TOKEN")
    if app_token:
        session.headers["X-App-Token"] = app_token

    return session


def fetch_page(
    session: requests.Session,
    offset: int,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    params = {
        "$select": ",".join(FIELDS),
        "$where": (
            f"created_date >= '{start_date}' "
            f"AND created_date < '{end_date}'"
        ),
        "$order": "created_date ASC, unique_key ASC",
        "$limit": PAGE_SIZE,
        "$offset": offset,
    }

    response = session.get(API_URL, params=params, timeout=60)
    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list):
        raise TypeError("The API response does not contain a list of records")

    return payload


def extract() -> int:
    validate_config()
    start_date, end_date = resolve_window(
        WINDOW_DAYS, START_OVERRIDE, END_OVERRIDE,
        source_lag_days=SOURCE_LAG_DAYS,
    )
    logger.info("Extraction window (New York local time): [%s, %s)", start_date, end_date)
    if START_OVERRIDE:
        logger.warning("Using fixed date overrides; remove them for a rolling refresh")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT_PATH.with_suffix(
        f"{OUTPUT_PATH.suffix}.part"
    )

    session = build_session()
    seen_keys: set[str] = set()
    daily_counts: Counter[date] = Counter()
    latest_created_at: datetime | None = None
    rows_written = 0
    offset = 0

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=FIELDS,
                extrasaction="ignore",
            )
            writer.writeheader()

            while True:
                page = fetch_page(session, offset, start_date, end_date)

                if not page:
                    break

                for row in page:
                    unique_key = row.get("unique_key")

                    if not unique_key:
                        raise ValueError(
                            "The API returned a record without unique_key"
                        )

                    if unique_key in seen_keys:
                        raise ValueError(
                            f"Duplicate unique_key detected: {unique_key}"
                        )

                    try:
                        created_at = datetime.fromisoformat(row["created_date"])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValueError(
                            f"Invalid created_date for unique_key={unique_key}"
                        ) from exc

                    daily_counts[created_at.date()] += 1
                    if latest_created_at is None or created_at > latest_created_at:
                        latest_created_at = created_at

                    seen_keys.add(unique_key)
                    writer.writerow(row)

                rows_written += len(page)

                logger.info(
                    "Page completed: offset=%s, rows=%s, total=%s",
                    offset,
                    len(page),
                    rows_written,
                )

                if len(page) < PAGE_SIZE:
                    break

                offset += PAGE_SIZE

        validate_latest_day(end_date, latest_created_at, daily_counts)
        temporary_path.replace(OUTPUT_PATH)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    finally:
        session.close()

    logger.info(
        "Extraction completed: %s rows written to %s",
        rows_written,
        OUTPUT_PATH,
    )

    return rows_written


if __name__ == "__main__":
    extract()
