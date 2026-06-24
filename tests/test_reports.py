import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tg_keyword_trends.inputs import SearchTermGroup
from tg_keyword_trends.reports import generate_txt_report


class TxtReportTests(unittest.TestCase):
    def test_generate_txt_report_includes_grouped_terms_and_channel_titles(self):
        all_results = pd.DataFrame(
            [
                {
                    "time": pd.Timestamp("2026-01-01"),
                    "channel_id": 123,
                    "channel_title": "News",
                    "message": "alpha",
                },
                {
                    "time": pd.Timestamp("2026-01-02"),
                    "channel_id": 123,
                    "channel_title": "News",
                    "message": "beta",
                },
            ]
        )
        search_terms = [
            SearchTermGroup(label="Locations", terms=("Kyiv", "Kiev")),
            SearchTermGroup(label="single", terms=("single",)),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            generate_txt_report(
                all_results,
                [SimpleNamespace(title="News")],
                search_terms,
                temp_dir,
                "20260102_030405",
            )
            report = Path(temp_dir, "report_20260102_030405.txt").read_text(encoding="utf-8")

        self.assertIn("Locations: Kyiv | Kiev", report)
        self.assertIn("single", report)
        self.assertIn("Channel: News (123), Count: 2", report)

    def test_generate_txt_report_handles_empty_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            generate_txt_report(
                pd.DataFrame(),
                [],
                [],
                temp_dir,
                "20260102_030405",
            )
            report = Path(temp_dir, "report_20260102_030405.txt").read_text(encoding="utf-8")

        self.assertIn("Number of results: 0", report)
        self.assertIn("Date range of results: None - None", report)


if __name__ == "__main__":
    unittest.main()
