from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


load_dotenv()

API_URL = os.getenv(
    "NYC_311_API_URL",
    "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
)
START_DATE = os.getenv("NYC_311_START_DATE", "2026-08-01T00:00:00")
END_DATE = os.getenv("NYC_311_END_DATE", "2026-08-08T00:00:00")
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
    start = datetime.fromisoformat(START_DATE)
    end = datetime.fromisoformat(END_DATE)

    if start >= end:
        raise ValueError(
            "NYC_311_START_DATE must be earlier than NYC_311_END_DATE"
        )

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
) -> list[dict[str, Any]]:
    params = {
        "$select": ",".join(FIELDS),
        "$where": (
            f"created_date >= '{START_DATE}' "
            f"AND created_date < '{END_DATE}'"
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

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT_PATH.with_suffix(
        f"{OUTPUT_PATH.suffix}.part"
    )

    session = build_session()
    seen_keys: set[str] = set()
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
                page = fetch_page(session, offset)

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