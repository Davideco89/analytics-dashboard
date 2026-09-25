"""Offline regression tests for refresh publication and process coordination."""

import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import duckdb
except ModuleNotFoundError:
    # Publication control-flow tests do not open a database.
    sys.modules["duckdb"] = types.ModuleType("duckdb")

try:
    import dotenv
except ModuleNotFoundError:
    # Import the refresh module without installing its integration dependencies.
    module = types.ModuleType("dotenv")
    module.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = module

from scripts import update_data as pipeline


class RefreshTests(unittest.TestCase):
    def test_lock_rejects_concurrent_process_and_releases_afterward(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(pipeline, "LOCK_PATH", Path(directory) / "refresh.lock"):
                with pipeline.exclusive_refresh_lock():
                    with self.assertRaisesRegex(RuntimeError, "Another analytics refresh"):
                        with pipeline.exclusive_refresh_lock():
                            pass
                with pipeline.exclusive_refresh_lock():
                    pass

    def test_failed_docker_status_is_not_a_stopped_service(self):
        with (
            mock.patch.object(pipeline, "METABASE_MODE", "auto"),
            mock.patch.object(pipeline, "DATABASE_PATH", pipeline.DEFAULT_DATABASE_PATH),
            mock.patch.object(pipeline.shutil, "which", return_value="docker"),
            mock.patch.object(
                pipeline.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, "docker compose ps"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "status is unknown"):
                pipeline.is_metabase_running()

    def test_headless_mode_skips_docker_without_querying_it(self):
        with (
            mock.patch.object(pipeline, "METABASE_MODE", "headless"),
            mock.patch.object(pipeline.subprocess, "run") as run,
        ):
            self.assertFalse(pipeline.is_metabase_running())
            run.assert_not_called()

    def test_nondefault_database_requires_explicit_headless_mode(self):
        with (
            mock.patch.object(pipeline, "METABASE_MODE", "auto"),
            mock.patch.object(pipeline, "DATABASE_PATH", Path("other.duckdb")),
        ):
            with self.assertRaisesRegex(RuntimeError, "Metabase connection"):
                pipeline.is_metabase_running()

    def test_custom_path_is_resolved_from_project_root(self):
        with mock.patch.dict(os.environ, {"DUCKDB_PATH": "data/database/custom.duckdb"}):
            self.assertEqual(
                pipeline.configured_path("DUCKDB_PATH", "unused"),
                (pipeline.PROJECT_ROOT / "data/database/custom.duckdb").resolve(),
            )

    def test_interrupt_after_database_replacement_restores_old_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current_database = root / "analytics.duckdb"
            staged_database = root / "staging" / "analytics.duckdb"
            current_csv = root / "nyc_311.csv"
            staged_csv = root / "nyc_311_next.csv"
            staged_database.parent.mkdir()
            current_database.write_bytes(b"old database")
            staged_database.write_bytes(b"new database")
            current_csv.write_bytes(b"old csv")
            staged_csv.write_bytes(b"new csv")

            with (
                mock.patch.object(pipeline, "DATABASE_PATH", current_database),
                mock.patch.object(pipeline, "STAGED_DATABASE_PATH", staged_database),
                mock.patch.object(pipeline, "RAW_PATH", current_csv),
                mock.patch.object(pipeline, "STAGED_RAW_PATH", staged_csv),
                mock.patch.object(pipeline, "BACKUP_DIRECTORY", root / "backups"),
                mock.patch.object(pipeline, "is_metabase_running", return_value=True),
                mock.patch.object(pipeline, "validate_published_database", side_effect=KeyboardInterrupt),
                mock.patch.object(pipeline, "run_command") as command,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    pipeline.publish_staged_files()

            self.assertEqual(current_database.read_bytes(), b"old database")
            self.assertEqual(current_csv.read_bytes(), b"old csv")
            self.assertEqual(staged_csv.read_bytes(), b"new csv")
            self.assertEqual(command.call_count, 2)
            self.assertEqual(
                command.call_args_list[1].args[0][:4],
                ["docker", "compose", "start", "--wait"],
            )


if __name__ == "__main__":
    unittest.main()
