"""Check the local Python installation without downloading data or starting Docker."""

from __future__ import annotations

import sys
import sysconfig
from importlib.metadata import version
from pathlib import Path

import duckdb
import great_expectations
import pandas


ROOT = Path(__file__).resolve().parent


def main() -> None:
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError("Use Python 3.13 for this project.")

    for relative_path in (
        ".env",
        "compose.yaml",
        "dbt_project.yml",
        "profiles.yml",
        "requirements.txt",
    ):
        if not (ROOT / relative_path).is_file():
            raise FileNotFoundError(f"Required project file is missing: {relative_path}")

    dbt_executable = Path(sysconfig.get_path("scripts")) / (
        "dbt.exe" if sys.platform == "win32" else "dbt"
    )
    if not dbt_executable.is_file():
        raise FileNotFoundError(f"dbt executable is missing: {dbt_executable}")

    with duckdb.connect(":memory:") as connection:
        if connection.execute("SELECT 1").fetchone() != (1,):
            raise RuntimeError("DuckDB could not execute an in-memory query.")

    print(f"Python: {sys.version.split()[0]}")
    print(f"DuckDB: {duckdb.__version__}")
    print(f"Great Expectations: {version('great-expectations')}")
    print(f"pandas: {pandas.__version__}")
    print(f"dbt Core: {version('dbt-core')}")
    print(f"dbt-duckdb: {version('dbt-duckdb')}")
    print("[OK] Local setup checks passed.")


if __name__ == "__main__":
    main()
