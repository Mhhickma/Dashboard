import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fetch_keepa import PRICE_TRACKS, build_deal_candidate, qualification_for_prices, window_weighted_median_from_points


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

    def test_one_time_coupon_can_make_product_qualify(self):
        stats = {
            "current": [9500] + [-1] * 18,
            "avg": [10000] + [-1] * 18,
            "minInInterval": [9500] + [-1] * 18,
            "avg30": [10000] + [-1] * 18,
        }
        product = {"asin": "B012345678", "title": "Coupon tool", "stats": stats, "coupon": [-10, 0]}

        deal = build_deal_candidate(product, PRICE_TRACKS[0])

        self.assertIsNotNone(deal)
        self.assertEqual(deal["current_price"], 95)
        self.assertEqual(deal["after_coupon_price"], 85.5)
        self.assertEqual(deal["qualification_price"], 85.5)
        self.assertTrue(deal["coupon_qualified"])
        self.assertFalse(deal["coupon_verified"])
        self.assertEqual(deal["coupon_source"], "keepa")
        self.assertIn("possible 10% coupon", deal["qualification_reasons"][0])

    def test_subscribe_and_save_coupon_cannot_qualify_product(self):
        stats = {
            "current": [9500] + [-1] * 18,
            "avg": [10000] + [-1] * 18,
            "minInInterval": [9500] + [-1] * 18,
            "avg30": [10000] + [-1] * 18,
        }
        product = {"asin": "B012345678", "title": "Subscription tool", "stats": stats, "coupon": [0, -20]}

        self.assertIsNone(build_deal_candidate(product, PRICE_TRACKS[0]))


if __name__ == "__main__":
    unittest.main()
