import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tg_keyword_trends.plotting import (
    build_graph_manifest_entry,
    calculate_7_day_rolling_percentage,
    calculate_percentage_over_time,
    calculate_total_daily_messages,
    extract_wordcloud_text,
    generate_pdf,
    generate_wordcloud_image,
    plot_percentage_over_time,
    plot_rolling_percentage_over_time,
    safe_graph_filename,
    save_matplotlib_figure,
)


class PlottingHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.addCleanup(plt.close, "all")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_safe_graph_filename_removes_path_and_reserved_characters(self):
        filename = safe_graph_filename("message count", 'war/peace: "term"?*', extension="png")

        self.assertEqual(filename, "message_count_war_peace_term.png")
        self.assertEqual(safe_graph_filename("", extension=".png"), "graph.png")
        self.assertEqual(safe_graph_filename("CON"), "graph_CON.png")
        self.assertEqual(safe_graph_filename("cafe\u0301"), "cafe.png")

    def test_manifest_entry_includes_graph_metadata(self):
        entry = build_graph_manifest_entry(
            "daily_percentage",
            self.output_dir / "graph.png",
            title="Daily %",
            search_term="alpha",
            scale="linear",
            rows=3,
        )

        self.assertEqual(entry["type"], "daily_percentage")
        self.assertEqual(entry["title"], "Daily %")
        self.assertEqual(entry["filename"], "graph.png")
        self.assertEqual(entry["search_term"], "alpha")
        self.assertEqual(entry["scale"], "linear")
        self.assertEqual(entry["rows"], 3)
        self.assertFalse(entry["skipped"])

    def test_save_matplotlib_figure_writes_file_and_closes_figure(self):
        fig, ax = plt.subplots()
        ax.plot([1, 2], [3, 4])
        figure_number = fig.number

        entry = save_matplotlib_figure(
            fig,
            self.output_dir / "nested" / "plot.png",
            graph_type="test_plot",
            title="Test Plot",
        )

        self.assertTrue((self.output_dir / "nested" / "plot.png").exists())
        self.assertNotIn(figure_number, plt.get_fignums())
        self.assertEqual(entry["filename"], "plot.png")
        self.assertEqual(entry["status"], "created")

    def test_percentage_helpers_calculate_daily_and_rolling_percentages(self):
        grouped_results = self._grouped_results_for_percentages()

        total_messages = calculate_total_daily_messages(grouped_results)
        daily_percentages = calculate_percentage_over_time(grouped_results)
        rolling_percentages = calculate_7_day_rolling_percentage(grouped_results)

        self.assertEqual(total_messages.loc[pd.Timestamp("2026-01-01")], 10)

        alpha_day_one = daily_percentages[
            (daily_percentages["search_term"] == "alpha")
            & (daily_percentages["date"] == pd.Timestamp("2026-01-01"))
        ].iloc[0]
        alpha_day_eight = daily_percentages[
            (daily_percentages["search_term"] == "alpha")
            & (daily_percentages["date"] == pd.Timestamp("2026-01-08"))
        ].iloc[0]
        rolling_alpha_day_eight = rolling_percentages[
            (rolling_percentages["search_term"] == "alpha")
            & (rolling_percentages["date"] == pd.Timestamp("2026-01-08"))
        ].iloc[0]

        self.assertEqual(alpha_day_one["mentions"], 1)
        self.assertEqual(alpha_day_one["total_messages"], 10)
        self.assertEqual(alpha_day_one["percentage"], 10)
        self.assertEqual(alpha_day_eight["mentions"], 2)
        self.assertEqual(alpha_day_eight["percentage"], 20)
        self.assertEqual(rolling_alpha_day_eight["rolling_mentions"], 8)
        self.assertEqual(rolling_alpha_day_eight["rolling_total_messages"], 70)
        self.assertAlmostEqual(rolling_alpha_day_eight["rolling_percentage"], 8 / 70 * 100)

    def test_extract_wordcloud_text_skips_empty_values(self):
        class Message:
            message = "object text"

        frame = pd.DataFrame({"message": [" hello ", "", None, Message()]})

        self.assertEqual(extract_wordcloud_text({"alpha": [frame]}), "hello\nobject text")

    def test_generate_wordcloud_image_skips_empty_text(self):
        entry = generate_wordcloud_image(
            {"alpha": [pd.DataFrame({"message": ["", "   ", None]})]},
            self.output_dir,
            search_term="alpha",
            wordcloud_cls=FakeWordCloud,
        )

        self.assertEqual(entry["status"], "skipped")
        self.assertEqual(entry["reason"], "empty_text")
        self.assertEqual(entry["text_length"], 0)
        self.assertEqual(list(self.output_dir.iterdir()), [])

    def test_generate_wordcloud_image_uses_injected_wordcloud_and_closes_figure(self):
        FakeWordCloud.last_text = None
        grouped_results = {"alpha/unsafe": [pd.DataFrame({"message": ["alpha beta", "gamma"]})]}

        entry = generate_wordcloud_image(
            grouped_results,
            self.output_dir,
            search_term="alpha/unsafe",
            wordcloud_cls=FakeWordCloud,
        )

        self.assertEqual(entry["status"], "created")
        self.assertEqual(entry["filename"], "wordcloud_alpha_unsafe.png")
        self.assertTrue(Path(entry["path"]).exists())
        self.assertEqual(FakeWordCloud.last_text, "alpha beta\ngamma")
        self.assertEqual(plt.get_fignums(), [])

    def test_percentage_plot_helpers_write_manifest_files(self):
        grouped_results = self._grouped_results_for_percentages()

        daily_entry = plot_percentage_over_time(grouped_results, self.output_dir)
        rolling_entry = plot_rolling_percentage_over_time(grouped_results, self.output_dir)

        self.assertEqual(daily_entry["status"], "created")
        self.assertEqual(rolling_entry["status"], "created")
        self.assertTrue(Path(daily_entry["path"]).exists())
        self.assertTrue(Path(rolling_entry["path"]).exists())
        self.assertEqual(plt.get_fignums(), [])

    def test_generate_pdf_uses_graph_manifest_entries(self):
        fig, ax = plt.subplots()
        ax.plot([1, 2], [1, 3])
        graph_entry = save_matplotlib_figure(
            fig,
            self.output_dir / "graph.png",
            graph_type="test_graph",
            title="Test Graph",
        )
        all_results = pd.DataFrame(
            [{"time": pd.Timestamp("2026-01-01"), "message": "alpha", "message_id": 1, "channel_id": 100}]
        )

        generate_pdf(
            all_results,
            self.output_dir,
            {},
            "20260101_000000",
            graph_manifest=[graph_entry],
        )

        self.assertTrue((self.output_dir / "Telegram_Keyword_Trends_Report_20260101_000000.pdf").exists())

    def _grouped_results_for_percentages(self):
        start = pd.Timestamp("2026-01-01")
        alpha_rows = []
        beta_rows = []

        for offset in range(8):
            date = start + pd.Timedelta(days=offset)
            alpha_message_ids = [1, 2] if offset == 7 else [1]

            for message_id in alpha_message_ids:
                alpha_rows.append(
                    {
                        "time": date,
                        "message": f"alpha {message_id}",
                        "message_id": message_id,
                        "channel_id": 100,
                    }
                )

            beta_rows.append(
                {
                    "time": date,
                    "message": "beta",
                    "message_id": 10,
                    "channel_id": 100,
                }
            )

        return {
            "alpha": [pd.DataFrame(alpha_rows)],
            "beta": [pd.DataFrame(beta_rows)],
        }


class FakeWordCloud:
    last_text = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def generate(self, text):
        FakeWordCloud.last_text = text
        return self

    def to_array(self):
        return np.zeros((4, 4, 3), dtype=np.uint8)


if __name__ == "__main__":
    unittest.main()
