import datetime
import unittest
from unittest.mock import Mock

import pytz

from tg_keyword_trends.inputs import parse_date_bound, parse_date_range, prompt_date_range


class DateInputTests(unittest.TestCase):
    def test_blank_date_bound_returns_none(self):
        self.assertIsNone(parse_date_bound(""))
        self.assertIsNone(parse_date_bound("   "))

    def test_parse_start_date_returns_utc_start_of_day(self):
        result = parse_date_bound("24/06/2026")

        self.assertEqual(result, datetime.datetime(2026, 6, 24, 0, 0, tzinfo=pytz.UTC))

    def test_parse_end_date_returns_utc_end_of_day(self):
        result = parse_date_bound("24/06/2026", is_end=True)

        self.assertEqual(result, datetime.datetime(2026, 6, 24, 23, 59, 59, 999999, tzinfo=pytz.UTC))

    def test_invalid_date_format_raises(self):
        with self.assertRaisesRegex(ValueError, "dd/mm/yyyy"):
            parse_date_bound("2026-06-24")

    def test_reversed_date_range_raises(self):
        with self.assertRaisesRegex(ValueError, "Start date"):
            parse_date_range("25/06/2026", "24/06/2026")

    def test_prompt_date_range_reprompts_until_valid(self):
        responses = iter(["bad", "", "24/06/2026", "25/06/2026"])
        output = Mock()

        start_date, end_date = prompt_date_range(input_func=lambda _: next(responses), output_func=output)

        self.assertEqual(start_date, datetime.datetime(2026, 6, 24, 0, 0, tzinfo=pytz.UTC))
        self.assertEqual(end_date, datetime.datetime(2026, 6, 25, 23, 59, 59, 999999, tzinfo=pytz.UTC))
        output.assert_called_once()


if __name__ == "__main__":
    unittest.main()
