import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.time import local_day_bounds_utc, to_local, to_utc


class TimeConversionTests(unittest.TestCase):
    def test_to_utc_converts_aware_datetime(self):
        local_value = datetime(2026, 11, 4, 20, 0, tzinfo=ZoneInfo("Europe/Moscow"))
        result = to_utc(local_value)

        self.assertEqual(result, datetime(2026, 11, 4, 17, 0, tzinfo=timezone.utc))
        self.assertEqual(result.utcoffset().total_seconds(), 0)

    def test_to_utc_rejects_naive_datetime(self):
        with self.assertRaises(ValueError):
            to_utc(datetime(2026, 11, 4, 20, 0))

    def test_local_day_bounds_are_utc_and_cover_one_local_day(self):
        with patch("app.core.time.local_timezone", return_value=ZoneInfo("Europe/Moscow")):
            start, end = local_day_bounds_utc(datetime(2026, 11, 4).date())

        self.assertEqual(start, datetime(2026, 11, 3, 21, 0, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 11, 4, 21, 0, tzinfo=timezone.utc))

    def test_to_local_rejects_naive_datetime(self):
        with self.assertRaises(ValueError):
            to_local(datetime(2026, 11, 4, 20, 0))


if __name__ == "__main__":
    unittest.main()
