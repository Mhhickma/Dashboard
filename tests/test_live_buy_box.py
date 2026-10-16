import unittest

import fetch_keepa


def price_array(index, cents):
    values = [-1] * 34
    values[index] = cents
    return values


class LiveBuyBoxTests(unittest.TestCase):
    def test_usage_logger_accepts_buy_box_request_category(self):
        before = dict(fetch_keepa.KEEPA_RUN_USAGE)
        try:
            fetch_keepa.record_keepa_response({"tokensConsumed": 3}, "product_buybox_verification")
            self.assertEqual(fetch_keepa.KEEPA_RUN_USAGE["product_buybox_verification_tokens"], 3)
        finally:
            fetch_keepa.KEEPA_RUN_USAGE.clear()
            fetch_keepa.KEEPA_RUN_USAGE.update(before)

    def product(self):
        return {
            "asin": "B08TPGCXWW",
            "title": "Prime test product",
            "stats": {
                "current": price_array(1, 999),
                "avg": price_array(1, 1200),
                "minInInterval": price_array(1, 1100),
                "avg30": price_array(1, 1200),
            },
            "csv": [[] for _ in range(34)],
        }

    def test_discounted_new_price_is_selected_for_buy_box_verification(self):
        self.assertEqual(
            fetch_keepa.buy_box_verification_asins([self.product()]),
            ["B08TPGCXWW"],
        )

    def test_verified_fba_buy_box_can_qualify(self):
        product = self.product()
        product["stats"]["buyBoxIsFBA"] = True
        for key, cents in (("current", 900), ("avg", 1200), ("minInInterval", 1100), ("avg30", 1200)):
            product["stats"][key][18] = cents

        deal = fetch_keepa.build_deal(product)

        self.assertIsNotNone(deal)
        self.assertEqual(deal["price_type"], "buy_box")
        self.assertEqual(deal["current_price"], 9.00)

    def test_unverified_buy_box_is_rejected(self):
        product = self.product()
        for key, cents in (("current", 900), ("avg", 1200), ("minInInterval", 1100), ("avg30", 1200)):
            product["stats"][key][18] = cents

        self.assertIsNone(fetch_keepa.build_verified_buy_box_candidate(product))

    def test_live_buy_box_survives_memory_filter(self):
        memory, removed = fetch_keepa.keep_only_qualifying_price_types({
            "B08TPGCXWW": {"price_type": "buy_box"},
        })

        self.assertEqual(removed, 0)
        self.assertIn("B08TPGCXWW", memory)


if __name__ == "__main__":
    unittest.main()
