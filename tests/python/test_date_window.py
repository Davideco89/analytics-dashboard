import unittest
from datetime import date, datetime, timezone

from src.date_window import resolve_window, validate_latest_day


class DateWindowTests(unittest.TestCase):
    def test_window_advances_on_subsequent_sundays(self):
        first = resolve_window(7, now=datetime(2026, 9, 27, 12, tzinfo=timezone.utc))
        second = resolve_window(7, now=datetime(2026, 10, 4, 12, tzinfo=timezone.utc))
        self.assertEqual(first, ("2026-09-19T00:00:00", "2026-09-26T00:00:00"))
        self.assertEqual(second, ("2026-09-26T00:00:00", "2026-10-03T00:00:00"))

    def test_new_york_day_boundary_handles_daylight_saving(self):
        actual = resolve_window(7, now=datetime(2026, 11, 1, 16, tzinfo=timezone.utc))
        self.assertEqual(actual, ("2026-10-24T00:00:00", "2026-10-31T00:00:00"))

    def test_source_lag_is_configurable(self):
        now = datetime(2026, 9, 27, 16, tzinfo=timezone.utc)
        self.assertEqual(resolve_window(14, now=now, source_lag_days=2),
                         ("2026-09-11T00:00:00", "2026-09-25T00:00:00"))
        with self.assertRaises(ValueError):
            resolve_window(7, source_lag_days=-1)

    def test_explicit_replay_and_incomplete_override(self):
        self.assertEqual(resolve_window(7, "2026-08-01T00:00:00", "2026-08-08T00:00:00"),
                         ("2026-08-01T00:00:00", "2026-08-08T00:00:00"))
        with self.assertRaises(ValueError):
            resolve_window(7, "2026-08-01T00:00:00")
        with self.assertRaises(ValueError):
            resolve_window(0)

    def test_rejects_recent_day_truncated_at_two_am(self):
        with self.assertRaisesRegex(RuntimeError, "not supplied the full final day"):
            validate_latest_day(
                "2026-09-27T00:00:00",
                datetime(2026, 9, 26, 2, 6, 26),
                {date(2026, 9, 25): 10997, date(2026, 9, 26): 534},
            )

    def test_rejects_sparse_final_day_even_with_late_event(self):
        with self.assertRaisesRegex(RuntimeError, "source delivery may be incomplete"):
            validate_latest_day(
                "2026-09-27T00:00:00",
                datetime(2026, 9, 26, 23, 59),
                {date(2026, 9, 25): 10997, date(2026, 9, 26): 534},
            )

    def test_accepts_previous_fully_available_day(self):
        validate_latest_day(
            "2026-09-26T00:00:00",
            datetime(2026, 9, 25, 23, 59, 59),
            {date(2026, 9, 24): 10797, date(2026, 9, 25): 10997},
        )


if __name__ == "__main__":
    unittest.main()
