from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_PATH = PROJECT_ROOT / "data" / "raw" / "nyc_311.csv"
DATABASE_PATH = PROJECT_ROOT / "data" / "database" / "analytics.duckdb"
BACKUP_DIRECTORY = PROJECT_ROOT / "data" / "backups"

STAGED_RAW_PATH = (
    PROJECT_ROOT / "data" / "raw" / "nyc_311_next.csv"
)
STAGED_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "database"
    / "staging"
    / "analytics.duckdb"
)

METABASE_SERVICE = "metabase"


def run_command(
    command: list[str],
    environment: dict[str, str] | None = None,
) -> None:
    """Run a project command and stop the pipeline if it fails."""

    logging.info("Running command: %s", " ".join(command))

    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


def remove_file_if_present(path: Path) -> None:
    """Remove an explicitly identified generated file if it exists."""

    if path.exists():
        path.unlink()
        logging.info("Removed temporary file: %s", path)


def clean_staging_files() -> None:
    """Remove staging files left by an interrupted execution."""

    staged_files = [
        STAGED_RAW_PATH,
        Path(f"{STAGED_RAW_PATH}.part"),
        STAGED_DATABASE_PATH,
        Path(f"{STAGED_DATABASE_PATH}.wal"),
    ]

    for path in staged_files:
        remove_file_if_present(path)


def is_metabase_running() -> bool:
    """Return whether the Metabase Compose service is currently running."""

    if shutil.which("docker") is None:
        return False

    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "ps",
                "--status",
                "running",
                "--services",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        logging.warning(
            "Docker Compose status could not be determined. "
            "The pipeline will continue without managing Metabase."
        )
        return False

    running_services = {
        service.strip()
        for service in result.stdout.splitlines()
        if service.strip()
    }

    return METABASE_SERVICE in running_services


def create_database_backup() -> Path | None:
    """Create a timestamped backup of the current analytical database."""

    if not DATABASE_PATH.exists():
        logging.info("No existing database was found. Backup skipped.")
        return None

    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIRECTORY / f"analytics_{timestamp}.duckdb"

    shutil.copyfile(DATABASE_PATH, backup_path)

    logging.info("Database backup created: %s", backup_path)

    return backup_path

def validate_published_database() -> None:
    """Validate the analytical database after its final publication."""

    with duckdb.connect(
        str(DATABASE_PATH),
        read_only=True,
    ) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM raw.nyc_311),
                (SELECT count(*) FROM dev_staging.stg_nyc_311),
                (SELECT count(*) FROM dev_marts.fct_requests),
                (SELECT count(*) FROM dev_marts.dim_complaint_type)
            """
        ).fetchone()

    raw_rows, staging_rows, fact_rows, complaint_types = counts

    if raw_rows == 0:
        raise RuntimeError("The published raw table is empty.")

    if raw_rows != staging_rows or raw_rows != fact_rows:
        raise RuntimeError(
            "Published row counts are inconsistent: "
            f"raw={raw_rows}, staging={staging_rows}, fact={fact_rows}"
        )

    if complaint_types == 0:
        raise RuntimeError(
            "The published complaint type dimension is empty."
        )

    logging.info(
        "Published database validated: "
        "raw=%s, staging=%s, fact=%s, complaint_types=%s",
        raw_rows,
        staging_rows,
        fact_rows,
        complaint_types,
    )

def publish_staged_files() -> None:
    """Publish staged files and restore the previous database on failure."""

    metabase_was_running = is_metabase_running()
    backup_path: Path | None = None
    database_replaced = False

    try:
        if metabase_was_running:
            logging.info("Stopping Metabase before database replacement.")
            run_command(
                ["docker", "compose", "stop", METABASE_SERVICE]
            )

        backup_path = create_database_backup()

        os.replace(STAGED_DATABASE_PATH, DATABASE_PATH)
        database_replaced = True

        validate_published_database()

        os.replace(STAGED_RAW_PATH, RAW_PATH)

        logging.info("Staged files published successfully.")

    except Exception:
        logging.exception("Database publication failed.")

        if database_replaced:
            if backup_path is not None and backup_path.exists():
                shutil.copyfile(backup_path, DATABASE_PATH)
                logging.warning(
                    "Previous database restored from backup: %s",
                    backup_path,
                )
            else:
                remove_file_if_present(DATABASE_PATH)
                logging.warning(
                    "Invalid published database removed because "
                    "no previous backup was available."
                )

        raise

    finally:
        if metabase_was_running:
            logging.info("Restarting Metabase.")
            run_command(
                ["docker", "compose", "start", METABASE_SERVICE]
            )

def main() -> int:
    """Run the complete analytics refresh pipeline."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    logging.info("Analytics refresh started.")

    clean_staging_files()

    pipeline_environment = os.environ.copy()
    pipeline_environment["NYC_311_RAW_PATH"] = str(STAGED_RAW_PATH)
    pipeline_environment["DUCKDB_PATH"] = str(STAGED_DATABASE_PATH)

    dbt_executable = shutil.which("dbt")

    if dbt_executable is None:
        logging.error(
            "The dbt executable was not found in the active environment."
        )
        return 1

    try:
        run_command(
            [sys.executable, "-m", "src.extract"],
            pipeline_environment,
        )

        run_command(
            [sys.executable, "-m", "src.validate_raw"],
            pipeline_environment,
        )

        run_command(
            [sys.executable, "-m", "src.load"],
            pipeline_environment,
        )

        run_command(
            [
                dbt_executable,
                "build",
                "--profiles-dir",
                ".",
            ],
            pipeline_environment,
        )

        publish_staged_files()

    except Exception:
        logging.exception("Analytics refresh failed.")
        clean_staging_files()
        return 1

    logging.info("Analytics refresh completed successfully.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())