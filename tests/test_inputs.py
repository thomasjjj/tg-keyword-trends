import sys
import unittest
from datetime import datetime, time, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tg_keyword_trends.inputs import (
    DateRange,
    SearchTermGroup,
    flatten_search_term_groups,
    normalize_channel_entry,
    parse_channel_entries,
    parse_date_bound,
    parse_date_range,
    parse_date_value,
    parse_search_term_groups,
    prompt_date_range,
)


class DateInputTests(unittest.TestCase):
    def test_parse_date_value_accepts_blank_values(self):
        self.assertIsNone(parse_date_value(""))
        self.assertIsNone(parse_date_value("   "))

    def test_parse_date_bound_wraps_date_value_parser(self):
        self.assertEqual(parse_date_bound("01/02/2026"), datetime(2026, 2, 1, tzinfo=timezone.utc))

    def test_parse_date_range_uses_full_day_boundaries(self):
        date_range = parse_date_range("01/02/2026", "03/02/2026")

        self.assertEqual(date_range.start, datetime(2026, 2, 1, tzinfo=timezone.utc))
        self.assertEqual(date_range.end, datetime.combine(datetime(2026, 2, 3).date(), time.max, tzinfo=timezone.utc))

    def test_parse_date_range_accepts_open_ended_range(self):
        self.assertEqual(parse_date_range("", "03/02/2026").start, None)
        self.assertEqual(parse_date_range("01/02/2026", "").end, None)

    def test_parse_date_range_rejects_invalid_date_format(self):
        with self.assertRaisesRegex(ValueError, "dd/mm/yyyy"):
            parse_date_range("2026-02-01", "")

    def test_parse_date_range_rejects_start_after_end(self):
        with self.assertRaisesRegex(ValueError, "Start date"):
            parse_date_range("04/02/2026", "03/02/2026")

    def test_prompt_date_range_retries_after_validation_error(self):
        answers = iter(["bad", "", "01/02/2026", ""])
        errors = []

        date_range = prompt_date_range(lambda prompt: next(answers), error_func=errors.append)

        self.assertEqual(date_range, DateRange(start=datetime(2026, 2, 1, tzinfo=timezone.utc), end=None))
        self.assertEqual(len(errors), 1)

    def test_date_range_can_be_unpacked_for_legacy_callers(self):
        start, end = parse_date_range("01/02/2026", "")

        self.assertEqual(start, datetime(2026, 2, 1, tzinfo=timezone.utc))
        self.assertIsNone(end)


class SearchTermInputTests(unittest.TestCase):
    def test_parse_search_term_groups_ignores_blank_and_comment_lines(self):
        groups = parse_search_term_groups(["", "  # comment", "alpha", "   ", "Beta Group: beta | b "])

        self.assertEqual(
            groups,
            [
                SearchTermGroup(label="alpha", terms=("alpha",)),
                SearchTermGroup(label="Beta Group", terms=("beta", "b")),
            ],
        )

    def test_plain_search_term_line_becomes_single_term_group(self):
        self.assertEqual(parse_search_term_groups(["single term"]), [SearchTermGroup("single term", ("single term",))])

    def test_grouped_search_term_line_splits_terms_on_pipe(self):
        self.assertEqual(
            parse_search_term_groups(["Locations: Kyiv | Kiev | Kyyiv"]),
            [SearchTermGroup("Locations", ("Kyiv", "Kiev", "Kyyiv"))],
        )

    def test_grouped_search_term_line_rejects_blank_label(self):
        with self.assertRaisesRegex(ValueError, "label"):
            parse_search_term_groups([": alpha | beta"])

    def test_grouped_search_term_line_rejects_empty_term_list(self):
        with self.assertRaisesRegex(ValueError, "at least one term"):
            parse_search_term_groups(["Group: | "])

    def test_flatten_search_term_groups_preserves_group_order(self):
        groups = [
            SearchTermGroup("Group A", ("alpha", "a")),
            SearchTermGroup("beta", ("beta",)),
        ]

        self.assertEqual(flatten_search_term_groups(groups), ["alpha", "a", "beta"])


class ChannelInputTests(unittest.TestCase):
    def test_normalize_channel_entry_accepts_usernames(self):
        self.assertEqual(normalize_channel_entry("example_channel"), "example_channel")
        self.assertEqual(normalize_channel_entry("@example_channel"), "example_channel")

    def test_normalize_channel_entry_accepts_telegram_links(self):
        self.assertEqual(normalize_channel_entry("t.me/example_channel"), "example_channel")
        self.assertEqual(normalize_channel_entry("https://t.me/example_channel"), "example_channel")
        self.assertEqual(normalize_channel_entry("https://t.me/example_channel/123"), "example_channel")

    def test_normalize_channel_entry_accepts_numeric_ids(self):
        self.assertEqual(normalize_channel_entry("123456789"), 123456789)
        self.assertEqual(normalize_channel_entry("-100123456789"), -100123456789)

    def test_normalize_channel_entry_accepts_private_channel_links(self):
        self.assertEqual(normalize_channel_entry("https://t.me/c/123456789/42"), -100123456789)

    def test_parse_channel_entries_ignores_blank_and_comment_lines(self):
        entries = parse_channel_entries(["", "# comment", " @alpha ", "https://t.me/beta", "-100123"])

        self.assertEqual(entries, ["alpha", "beta", -100123])

    def test_normalize_channel_entry_rejects_unsupported_values(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            normalize_channel_entry("https://example.com/channel")


if __name__ == "__main__":
    unittest.main()
