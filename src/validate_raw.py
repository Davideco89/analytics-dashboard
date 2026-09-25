from __future__ import annotations

import logging
import os
from pathlib import Path

import great_expectations as gx
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

CSV_PATH = Path(
    os.getenv("NYC_311_RAW_PATH", "data/raw/nyc_311.csv")
)
MIN_ROW_COUNT = int(os.getenv("NYC_311_MIN_ROWS", "50000"))
MAX_ROW_COUNT = int(os.getenv("NYC_311_MAX_ROWS", "100000"))

EXPECTED_COLUMNS = [
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
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def failed_expectations(result: dict) -> list[str]:
    failures = []

    for entry in result.get("results", []):
        if entry.get("success") is not False:
            continue

        config = entry.get("expectation_config") or {}
        name = config.get("type") or config.get("expectation_type") or "unknown_expectation"
        column = (config.get("kwargs") or {}).get("column")
        label = f"{name}({column})" if column else name

        details = entry.get("result") or {}
        if "unexpected_count" in details:
            label += f": unexpected_count={details['unexpected_count']}"
        elif name == "expect_table_row_count_to_be_between" and "observed_value" in details:
            label += f": observed_count={details['observed_value']}"

        failures.append(label)

    return failures


def validate_raw() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Source file not found: {CSV_PATH}")

    dataframe = pd.read_csv(CSV_PATH, dtype="string")

    context = gx.get_context(mode="ephemeral")

    data_source = context.data_sources.add_pandas(
        name="nyc_311_pandas"
    )
    data_asset = data_source.add_dataframe_asset(
        name="nyc_311_raw"
    )
    batch_definition = (
        data_asset.add_batch_definition_whole_dataframe(
            name="nyc_311_complete_file"
        )
    )
    batch = batch_definition.get_batch(
        batch_parameters={"dataframe": dataframe}
    )

    suite = gx.ExpectationSuite(name="nyc_311_raw_suite")

    suite.add_expectation(
        gx.expectations.ExpectTableColumnsToMatchOrderedList(
            column_list=EXPECTED_COLUMNS
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=MIN_ROW_COUNT,
            max_value=MAX_ROW_COUNT,
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="unique_key"
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(
            column="unique_key"
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="created_date"
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="created_date",
            regex=(
                r"^\d{4}-\d{2}-\d{2}"
                r"T\d{2}:\d{2}:\d{2}"
                r"(?:\.\d+)?$"
            ),
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="complaint_type"
        )
    )

    validation_result = batch.validate(suite)
    result = validation_result.to_json_dict()
    statistics = result["statistics"]

    logger.info(
        "GX validation: evaluated=%s, passed=%s, failed=%s",
        statistics["evaluated_expectations"],
        statistics["successful_expectations"],
        statistics["unsuccessful_expectations"],
    )

    if not validation_result.success:
        failures = failed_expectations(result)
        detail = "; ".join(failures) if failures else "no failure details returned"
        raise RuntimeError(f"Great Expectations validation failed: {detail}")

    logger.info(
        "Raw data validation completed successfully: %s rows",
        len(dataframe),
    )


if __name__ == "__main__":
    validate_raw()
