"""Run the documented SQL on representative fact and dimension rows."""

import sqlite3
import unittest
from pathlib import Path


GUIDE = Path(__file__).resolve().parents[2] / "docs" / "dashboard-guide.md"
SQL_DIRECTORY = Path(__file__).resolve().parents[2] / "dashboard" / "sql"
CARDS = (
    "Total Requests",
    "Average Resolution Days",
    "Complaint Volume Over Time",
    "Top Complaint Types by Borough",
    "Complaint Heatmap by Time of Day",
)
FILES = {
    "Total Requests": "total_requests.sql",
    "Average Resolution Days": "average_resolution_days.sql",
    "Complaint Volume Over Time": "complaint_volume_over_time.sql",
    "Top Complaint Types by Borough": "top_complaint_types_by_borough.sql",
    "Complaint Heatmap by Time of Day": "complaint_heatmap_by_time_of_day.sql",
}


def card_sql(name: str, date: str | None = None, borough: str | None = None) -> str:
    sql = (SQL_DIRECTORY / FILES[name]).read_text(encoding="utf-8")
    substitutions = {"request_date": date, "borough": borough}
    for key, value in substitutions.items():
        clause = f"[[AND {{{{{key}}}}}]]"
        sql = sql.replace(
            clause,
            f"AND dev_marts.fct_requests.{key} = ?" if value is not None else "",
        )
    if "{{" in sql or "[[" in sql:
        raise AssertionError(f"Unresolved Metabase parameter in {name}")
    return sql


class DashboardSQLTests(unittest.TestCase):
    def test_versioned_sql_matches_guide(self):
        guide = GUIDE.read_text(encoding="utf-8")
        for name in CARDS:
            with self.subTest(card=name):
                section = guide.split(f"## {name}\n", 1)[1]
                documented = section.split("```sql\n", 1)[1].split("```", 1)[0]
                versioned = (SQL_DIRECTORY / FILES[name]).read_text(encoding="utf-8")
                self.assertEqual(documented, versioned)

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("ATTACH DATABASE ':memory:' AS dev_marts")
        self.connection.executescript(
            """
            CREATE TABLE dev_marts.fct_requests (
                complaint_type_key TEXT, borough TEXT, request_date TEXT,
                has_valid_resolution INTEGER, resolution_hours REAL,
                has_valid_borough INTEGER, request_day_name TEXT, request_hour INTEGER
            );
            CREATE TABLE dev_marts.dim_complaint_type (
                complaint_type_key TEXT, complaint_type TEXT
            );
            INSERT INTO dev_marts.dim_complaint_type VALUES ('a','Noise'),('b','Parking');
            INSERT INTO dev_marts.fct_requests VALUES
                ('a','BROOKLYN','2026-09-20',1,24,1,'Sunday',10),
                ('a','QUEENS','2026-09-20',1,48,1,'Sunday',11),
                ('b','BROOKLYN','2026-09-21',0,NULL,1,'Monday',10),
                ('a','UNSPECIFIED','2026-09-21',0,NULL,0,'Monday',12);
            """
        )

    def tearDown(self):
        self.connection.close()

    def query(self, card, date=None, borough=None):
        parameters = [value for value in (date, borough) if value is not None]
        return self.connection.execute(card_sql(card, date, borough), parameters).fetchall()

    def test_each_card_runs_with_and_without_filters(self):
        for card in CARDS:
            with self.subTest(card=card):
                self.assertTrue(self.query(card))
                self.assertTrue(self.query(card, "2026-09-20", "BROOKLYN"))

    def test_metrics_join_and_heatmap_agree(self):
        self.assertEqual(self.query("Total Requests"), [(4,)])
        self.assertEqual(self.query("Average Resolution Days"), [(1.5,)])
        self.assertEqual(self.query("Total Requests", "2026-09-20", "BROOKLYN"), [(1,)])
        self.assertEqual(self.query("Complaint Volume Over Time"),
                         [("2026-09-20", 2), ("2026-09-21", 2)])
        self.assertEqual(self.query("Top Complaint Types by Borough"),
                         [("Noise", "BROOKLYN", 1), ("Noise", "QUEENS", 1),
                          ("Parking", "BROOKLYN", 1)])
        heatmap = self.query("Complaint Heatmap by Time of Day")
        self.assertEqual(len(heatmap), 2)
        self.assertEqual(sum(row[1] for row in heatmap), 0)
        self.assertEqual(sum(sum(row[1:]) for row in heatmap), 4)


if __name__ == "__main__":
    unittest.main()
