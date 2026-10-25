import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fetch_keepa import qualification_for_prices, window_weighted_median_from_points


class DealQualificationTests(unittest.TestCase):
    def test_requires_eight_percent_drop(self):
        self.assertIsNone(qualification_for_prices(93, 100, 100, 0, 100))
        self.assertIsNotNone(qualification_for_prices(92, 100, 100, 0, 100))

    def test_rejects_return_to_normal_after_short_spike(self):
        self.assertIsNone(qualification_for_prices(100, 100, 110, 2, 100))

    def test_short_spike_does_not_raise_typical_price(self):
        now = datetime(2026, 10, 25, tzinfo=timezone.utc)
        points = [
            (now - timedelta(days=30), 100),
            (now - timedelta(days=2), 120),
            (now, 100),
        ]
        with patch("fetch_keepa.utc_now", return_value=now):
            self.assertEqual(window_weighted_median_from_points(points, 30), 100)

    def test_keeps_genuine_ninety_day_low_exception(self):
        result = qualification_for_prices(95, 100, 100, 90, 95)
        self.assertIn("best price in 90+ days", result[2])


if __name__ == "__main__":
    unittest.main()
