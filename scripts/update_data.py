from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "database" / "analytics.duckdb"


def configured_path(name: str, default: str) -> Path:
    """Resolve configuration relative to the project, not the caller's cwd."""

    path = Path(os.getenv(name, default)).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


RAW_PATH = configured_path("NYC_311_RAW_PATH", "data/raw/nyc_311.csv")
DATABASE_PATH = configured_path("DUCKDB_PATH", "data/database/analytics.duckdb")
BACKUP_DIRECTORY = PROJECT_ROOT / "data" / "backups"

STAGED_RAW_PATH = RAW_PATH.with_name(f"{RAW_PATH.stem}_next{RAW_PATH.suffix}")
STAGED_DATABASE_PATH = DATABASE_PATH.parent / "staging" / DATABASE_PATH.name
LOCK_PATH = PROJECT_ROOT / "data" / "database" / ".refresh.lock"
METABASE_MODE = os.getenv("METABASE_MODE", "auto").lower()

METABASE_SERVICE = "metabase"


@contextmanager
def exclusive_refresh_lock():
    """Prevent a second local process from deleting active staging files."""

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.seek(0)
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)

        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another analytics refresh is running.") from exc
        else:
            import fcntl

            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Another analytics refresh is running.") from exc

        try:
            yield
        finally:
            lock_file.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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

    if METABASE_MODE == "headless":
        return False
    if METABASE_MODE != "auto":
        raise ValueError("METABASE_MODE must be 'auto' or 'headless'.")
    if DATABASE_PATH != DEFAULT_DATABASE_PATH:
        raise RuntimeError(
            "The local Metabase connection uses data/database/analytics.duckdb. "
            "Use the default DUCKDB_PATH or set METABASE_MODE=headless."
        )
    if shutil.which("docker") is None:
        raise RuntimeError(
            "Docker is unavailable; set METABASE_MODE=headless only when "
            "no local Metabase instance needs to be managed."
        )

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
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Docker Compose status is unknown; publication was cancelled."
        ) from exc

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

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = BACKUP_DIRECTORY / f"{DATABASE_PATH.stem}_{timestamp}.duckdb"

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

    except BaseException:
        logging.exception("Database publication failed.")

        if database_replaced:
            if backup_path is not None and backup_path.exists():
                restore_path = DATABASE_PATH.with_name(
                    f"{DATABASE_PATH.name}.restore"
                )
                try:
                    shutil.copyfile(backup_path, restore_path)
                    os.replace(restore_path, DATABASE_PATH)
                finally:
                    remove_file_if_present(restore_path)
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
                [
                    "docker", "compose", "start", "--wait",
                    "--wait-timeout", "180", METABASE_SERVICE,
                ]
            )

def main() -> int:
    """Run the complete analytics refresh pipeline."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    logging.info("Analytics refresh started.")

    try:
        with exclusive_refresh_lock():
            try:
                is_metabase_running()
                clean_staging_files()

                pipeline_environment = os.environ.copy()
                pipeline_environment["NYC_311_RAW_PATH"] = str(STAGED_RAW_PATH)
                pipeline_environment["DUCKDB_PATH"] = str(STAGED_DATABASE_PATH)

                dbt_executable = shutil.which("dbt")
                if dbt_executable is None:
                    raise RuntimeError("dbt was not found in the active environment.")

                run_command(
                    [sys.executable, "-m", "src.extract"], pipeline_environment
                )
                run_command(
                    [sys.executable, "-m", "src.validate_raw"], pipeline_environment
                )
                run_command(
                    [sys.executable, "-m", "src.load"], pipeline_environment
                )
                run_command(
                    [dbt_executable, "build", "--profiles-dir", "."],
                    pipeline_environment,
                )
                publish_staged_files()
            finally:
                clean_staging_files()

    except Exception:
        logging.exception("Analytics refresh failed.")
        return 1

    logging.info("Analytics refresh completed successfully.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
