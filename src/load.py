from __future__ import annotations

import logging
import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

DATABASE_PATH = Path(
    os.getenv("DUCKDB_PATH", "data/database/analytics.duckdb")
)
CSV_PATH = Path(
    os.getenv("NYC_311_RAW_PATH", "data/raw/nyc_311.csv")
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def load() -> int:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Source file not found: {CSV_PATH}")

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    csv_absolute_path = (
        CSV_PATH.resolve()
        .as_posix()
        .replace("'", "''")
    )
    source_file = CSV_PATH.as_posix().replace("'", "''")

    connection = duckdb.connect(str(DATABASE_PATH))

    try:
        connection.execute("BEGIN")
        connection.execute("CREATE SCHEMA IF NOT EXISTS raw")

        connection.execute(
            f"""
            CREATE OR REPLACE TABLE raw.nyc_311 AS
            SELECT
                *,
                current_timestamp AS _loaded_at,
                '{source_file}' AS _source_file
            FROM read_csv_auto(
                '{csv_absolute_path}',
                header = true,
                all_varchar = true
            )
            """
        )

        validation = connection.execute(
            """
            SELECT
                count(*) AS row_count,
                count(DISTINCT unique_key) AS unique_key_count,
                count(*) FILTER (
                    WHERE unique_key IS NULL
                       OR trim(unique_key) = ''
                ) AS null_key_count,
                min(try_cast(created_date AS TIMESTAMP)) AS min_created_date,
                max(try_cast(created_date AS TIMESTAMP)) AS max_created_date
            FROM raw.nyc_311
            """
        ).fetchone()

        if validation is None:
            raise RuntimeError("The validation query returned no result")

        (
            row_count,
            unique_key_count,
            null_key_count,
            min_created_date,
            max_created_date,
        ) = validation

        if row_count == 0:
            raise ValueError("The raw table is empty")

        if unique_key_count != row_count:
            raise ValueError("Duplicate unique keys detected in the raw table")

        if null_key_count > 0:
            raise ValueError("Null or empty unique keys detected")

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    logger.info("Load completed: %s rows", row_count)
    logger.info("Database: %s", DATABASE_PATH)
    logger.info("Table: raw.nyc_311")
    logger.info(
        "Created date range: %s to %s",
        min_created_date,
        max_created_date,
    )

    return row_count


if __name__ == "__main__":
    load()