import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import fetch_keepa


class DealMemoryTests(unittest.TestCase):
    def test_parse_iso_datetime_normalizes_to_utc(self):
        parsed = fetch_keepa.parse_iso_datetime("2026-10-14T16:00:00-04:00")
        self.assertEqual(parsed, datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc))

    @patch("fetch_keepa.utc_now")
    def test_purge_keeps_recent_deals_and_removes_expired_deals(self, utc_now):
        utc_now.return_value = datetime(2026, 10, 14, 20, 37, tzinfo=timezone.utc)
        memory = {
            "RECENT": {"posted_at": "2026-10-14T20:08:00+00:00"},
            "EXPIRED": {"posted_at": "2026-10-13T20:00:00+00:00"},
        }

        kept, expired_count = fetch_keepa.purge_expired_deals(memory)

        self.assertEqual(set(kept), {"RECENT"})
        self.assertEqual(expired_count, 1)


if __name__ == "__main__":
    unittest.main()
