import unittest

from src.validate_raw import failed_expectations


class ValidationDiagnosticsTests(unittest.TestCase):
    def test_failed_expectations_report_names_columns_and_counts_without_examples(self):
        result = {
            "results": [
                {
                    "success": False,
                    "expectation_config": {
                        "type": "expect_column_values_to_be_unique",
                        "kwargs": {"column": "unique_key"},
                    },
                    "result": {
                        "unexpected_count": 3,
                        "partial_unexpected_list": ["private_request_id"],
                    },
                },
                {
                    "success": False,
                    "expectation_config": {
                        "type": "expect_table_row_count_to_be_between",
                        "kwargs": {"min_value": 50000},
                    },
                    "result": {"observed_value": 12},
                },
                {"success": True, "expectation_config": {"type": "passing_check"}},
            ]
        }

        failures = failed_expectations(result)

        self.assertEqual(
            failures,
            [
                "expect_column_values_to_be_unique(unique_key): unexpected_count=3",
                "expect_table_row_count_to_be_between: observed_count=12",
            ],
        )
        self.assertNotIn("private_request_id", str(failures))


if __name__ == "__main__":
    unittest.main()
