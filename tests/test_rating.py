import unittest

from types import SimpleNamespace

from fetch_keepa import creator_rating_from_item, low_rated_product_asins, rating_from_product


class RatingTests(unittest.TestCase):
    def test_decodes_keepa_tenths_rating(self):
        current = [-1] * 17
        current[16] = 38
        self.assertEqual(rating_from_product({"stats": {"current": current}}), 3.8)

    def test_missing_rating_stays_unknown(self):
        self.assertIsNone(rating_from_product({"stats": {"current": []}}))

    def test_reads_creator_rating(self):
        item = SimpleNamespace(customer_reviews=SimpleNamespace(star_rating=SimpleNamespace(value=3.8)))
        self.assertEqual(creator_rating_from_item(item), 3.8)

    def test_only_confirmed_ratings_below_cutoff_are_removed(self):
        def product(asin, rating):
            current = [-1] * 17
            if rating is not None:
                current[16] = round(rating * 10)
            return {"asin": asin, "stats": {"current": current}}

        products = [
            product("B000000001", 3.7),
            product("B000000002", 3.8),
            product("B000000003", None),
        ]
        self.assertEqual(low_rated_product_asins(products), {"B000000001"})


if __name__ == "__main__":
    unittest.main()
