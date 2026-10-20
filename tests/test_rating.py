import unittest

from types import SimpleNamespace

from fetch_keepa import creator_rating_from_item, rating_from_product


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


if __name__ == "__main__":
    unittest.main()
