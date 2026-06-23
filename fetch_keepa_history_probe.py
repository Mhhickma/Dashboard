import copy
import os
from datetime import datetime, timezone, timedelta

import fetch_keepa

KEEPA_TIME_BASE = datetime(2011, 1, 1, tzinfo=timezone.utc)
PRIME_EXCLUSIVE_PRICE_INDEX = int(os.getenv("KEEPA_PRIME_EXCLUSIVE_PRICE_INDEX", "32"))
PRICE_TRACKS = (
    {"code": "amazon", "label": "Amazon price", "index": 0},
    {"code": "new_prime_exclusive", "label": "New, Prime Exclusive", "index": PRIME_EXCLUSIVE_PRICE_INDEX},
)

_original_build_deal = fetch_keepa.build_deal
_original_fetch_keepa_products = fetch_keepa.fetch_keepa_products


def clone_product_with_price_track(product, price_index):
    cloned = copy.deepcopy(product)
    stats = cloned.get("stats") or {}
    for key in ("current", "avg", "minInInterval", "avg30"):
        values = stats.get(key) or []
        if len(values) <= price_index:
            return None
        copied = list(values)
        if not copied:
            return None
        copied[0] = copied[price_index]
        stats[key] = copied
    cloned["stats"] = stats
    return cloned


def keepa_minutes_to_datetime(value):
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return KEEPA_TIME_BASE + timedelta(minutes=value)


def parse_price_history(product, history_index):
    csv_data = product.get("csv") or []
    if len(csv_data) <= history_index or not isinstance(csv_data[history_index], list):
        return []
    raw_values = csv_data[history_index]
    entries = []
    for i in range(0, len(raw_values) - 1, 2):
        changed_at = keepa_minutes_to_datetime(raw_values[i])
        price = fetch_keepa.keepa_to_dollars(raw_values[i + 1])
        if changed_at and price:
            entries.append((changed_at, price))
    return entries


def add_best_price_age(deal, product):
    if not deal or not deal.get("current_price"):
        return deal
    cutoff = fetch_keepa.utc_now() - timedelta(hours=24)
    history_index = int(deal.get("keepa_price_index") or 0)
    matches = []
    for changed_at, price in parse_price_history(product, history_index):
        if changed_at < cutoff and price <= deal["current_price"]:
            matches.append((changed_at, price))
    if not matches:
        deal["best_price_days"] = None
        deal["best_price_message"] = "best price in available Keepa history"
        return deal
    changed_at, price = max(matches, key=lambda item: item[0])
    age_days = max(1, (fetch_keepa.utc_now() - changed_at).days)
    deal["best_price_days"] = age_days
    deal["best_price_message"] = f"best price in {age_days} days"
    deal["best_price_previous_price"] = price
    deal["best_price_previous_date"] = changed_at.date().isoformat()
    return deal


def build_deal_for_track(product, track):
    track_product = product if track["index"] == 0 else clone_product_with_price_track(product, track["index"])
    if not track_product:
        return None
    deal = _original_build_deal(track_product)
    if not deal:
        return None
    deal["price_type"] = track["code"]
    deal["price_type_label"] = track["label"]
    deal["keepa_price_index"] = track["index"]
    deal["price_stats_source"] = f"keepa_stats_30_day_threshold_{track['code']}"
    return add_best_price_age(deal, product)


def deal_rank(deal):
    savings = max(0, float(deal.get("avg_7_price") or 0) - float(deal.get("current_price") or 0))
    prime_bonus = 1 if deal.get("price_type") == "new_prime_exclusive" else 0
    return (
        float(deal.get("drop_30_percent") or 0),
        float(deal.get("drop_percent") or 0),
        savings,
        prime_bonus,
    )


def build_deal(product):
    candidates = []
    for track in PRICE_TRACKS:
        deal = build_deal_for_track(product, track)
        if deal:
            candidates.append(deal)
    if not candidates:
        return None
    return max(candidates, key=deal_rank)


def fetch_keepa_products(asins):
    print(
        "Keepa price tracks: Amazon price plus New, Prime Exclusive "
        f"index {PRIME_EXCLUSIVE_PRICE_INDEX} when available."
    )
    return _original_fetch_keepa_products(asins)


fetch_keepa.build_deal = build_deal
fetch_keepa.fetch_keepa_products = fetch_keepa_products
fetch_keepa.main()
