import unittest
from datetime import datetime, timedelta, timezone
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

    @patch("fetch_keepa.utc_now")
    def test_expiration_starts_fixed_forty_eight_hour_cooldown(self, utc_now):
        first_seen = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        utc_now.return_value = first_seen + timedelta(hours=25)
        cooldowns = {}

        kept, expired_count = fetch_keepa.purge_expired_deals(
            {"B000000001": {"posted_at": first_seen.isoformat()}},
            cooldowns,
        )

        self.assertEqual(kept, {})
        self.assertEqual(expired_count, 1)
        expected = first_seen + timedelta(hours=24 + 48)
        self.assertEqual(fetch_keepa.parse_iso_datetime(cooldowns["B000000001"]), expected)

    @patch("fetch_keepa.utc_now")
    def test_rescan_does_not_extend_original_expiration(self, utc_now):
        first_seen = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        utc_now.return_value = first_seen + timedelta(hours=20)
        memory = {"B000000001": {"posted_at": first_seen.isoformat(), "title": "Old"}}

        merged, _, updated = fetch_keepa.merge_deals_with_memory(
            memory,
            [{"asin": "B000000001", "title": "Refreshed"}],
        )

        self.assertEqual(updated, 1)
        expected = first_seen + timedelta(hours=24)
        self.assertEqual(fetch_keepa.parse_iso_datetime(merged["B000000001"]["expires_at"]), expected)


if __name__ == "__main__":
    unittest.main()
