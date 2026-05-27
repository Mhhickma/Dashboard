import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import fetch_keepa

HISTORY_EXAMPLE_LIMIT = 5
KEEPA_TIME_BASE = datetime(2011, 1, 1, tzinfo=timezone.utc)
# Keepa product csv indexes: 0 Amazon, 1 Marketplace New, 10 New FBA, 17 Buy Box with shipping.
PRICE_HISTORY_INDEXES = (0, 1, 10, 17)
PERFORMANCE_FILE = Path("data/asin_performance.json")

_original_read_all_asins = fetch_keepa.read_all_asins
_original_load_deal_memory = fetch_keepa.load_deal_memory
_original_fetch_keepa_products = fetch_keepa.fetch_keepa_products
_original_build_deal = fetch_keepa.build_deal
_original_select_asins_for_run = fetch_keepa.select_asins_for_run
_original_merge_deals_with_memory = fetch_keepa.merge_deals_with_memory
_product_history_by_asin = {}
_selected_asins_for_run = []
_all_source_asins = set()


def read_all_asins_with_source_capture():
    asins = _original_read_all_asins()
    _all_source_asins.clear()
    _all_source_asins.update(str(asin or "").strip().upper() for asin in asins if asin)
    return asins


def load_deal_memory_without_removed_asins():
    memory = _original_load_deal_memory()
    if not _all_source_asins:
        return memory

    pruned_memory = {
        asin: deal
        for asin, deal in memory.items()
        if str(asin or "").strip().upper() in _all_source_asins
    }
    removed_count = len(memory) - len(pruned_memory)

    if removed_count:
        print(
            f"Removed {removed_count} stale deal(s) from data/deals_memory.json "
            "because their ASINs are no longer in the source sheet."
        )

    return pruned_memory


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


def best_price_age(product, current_price):
    """Return how long it has been since this ASIN was at or below today's price."""
    if not current_price:
        return None

    cutoff = fetch_keepa.utc_now() - timedelta(hours=24)
    matches = []

    for history_index in PRICE_HISTORY_INDEXES:
        for changed_at, price in parse_price_history(product, history_index):
            if changed_at >= cutoff:
                continue
            if price <= current_price:
                matches.append((changed_at, price, history_index))

    if not matches:
        return {
            "days": None,
            "message": "best price in available Keepa history",
            "prior_price": None,
            "prior_date": None,
        }

    changed_at, price, history_index = max(matches, key=lambda item: item[0])
    age_days = max(1, (fetch_keepa.utc_now() - changed_at).days)

    return {
        "days": age_days,
        "message": f"best price in {age_days} days",
        "prior_price": price,
        "prior_date": changed_at.date().isoformat(),
        "history_index": history_index,
    }


def add_best_price_age_to_deal(deal, product):
    if not deal:
        return deal

    age = best_price_age(product, deal.get("current_price"))
    if not age:
        return deal

    deal["best_price_days"] = age.get("days")
    deal["best_price_message"] = age.get("message")
    deal["best_price_previous_price"] = age.get("prior_price")
    deal["best_price_previous_date"] = age.get("prior_date")
    return deal


def build_deal_with_best_price_age(product):
    deal = _original_build_deal(product)
    return add_best_price_age_to_deal(deal, product)


def print_history_examples(products, limit=HISTORY_EXAMPLE_LIMIT):
    examples = []

    for product in products:
        stats = product.get("stats") or {}
        current_price = fetch_keepa.price_from_stats_array(stats, "current")
        age = best_price_age(product, current_price)
        if current_price and age:
            examples.append((product.get("asin"), current_price, age))
        if len(examples) >= limit:
            break

    print("Keepa history probe: requested history=1 with the normal scanner request.")
    print("Keepa history probe: this wrapper does not make an extra Keepa request.")
    print("Keepa history probe examples:")

    if not examples:
        print("  No usable price-history examples found in this run's history data.")
        return

    for asin, current_price, age in examples:
        line = f"  {asin}: current ${current_price:.2f}; {age['message']}"
        if age.get("prior_price") and age.get("prior_date"):
            line += f"; last at/below this price ${age['prior_price']:.2f} on {age['prior_date']}"
        print(line)


def fetch_keepa_products_with_history_probe(asins):
    print(
        "Keepa token probe: this run will request "
        f"{len(asins)} ASINs through the normal product endpoint."
    )
    print(
        "Keepa token probe: expected cost is about "
        f"{len(asins)} tokens, same as the current scanner."
    )

    products = _original_fetch_keepa_products(asins)
    _product_history_by_asin.clear()
    _product_history_by_asin.update({product.get("asin"): product for product in products if product.get("asin")})
    print_history_examples(products)
    return products


def select_asins_for_run_with_performance_capture(all_asins):
    selected, new_state, start_index, next_start_index = _original_select_asins_for_run(all_asins)
    _selected_asins_for_run.clear()
    _selected_asins_for_run.extend(selected)
    return selected, new_state, start_index, next_start_index


def load_asin_performance():
    if not PERFORMANCE_FILE.exists():
        return {}
    try:
        payload = json.loads(PERFORMANCE_FILE.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("asins"), dict):
            return payload["asins"]
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        print(f"Could not read ASIN performance file; starting fresh. Error: {exc}")
    return {}


def save_asin_performance(performance):
    PERFORMANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PERFORMANCE_FILE.write_text(
        json.dumps(
            {
                "updated_at": fetch_keepa.iso_now(),
                "description": "Long-term ASIN scan performance used to identify which products produce postable deals.",
                "asins": performance,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def score_100_point(deal):
    current = float(deal.get("current_price") or 0)
    avg7 = float(deal.get("avg_7_price") or 0)
    savings = max(0, avg7 - current) if current and avg7 else 0
    drop7 = float(deal.get("drop_percent") or 0)
    drop30 = float(deal.get("drop_30_percent") or 0)
    best_days = float(deal.get("best_price_days") or 0)

    drop7_points = min(25, (drop7 / 25) * 25) if drop7 > 0 else 0
    drop30_points = min(25, (drop30 / 25) * 25) if drop30 > 0 else 0
    savings_points = min(30, (savings / 100) * 30) if savings > 0 else 0
    rarity_points = min(15, (min(best_days, 90) / 90) * 15) if best_days > 0 else 0
    return round(drop7_points + drop30_points + savings_points + rarity_points, 1)


def suggested_priority(record):
    best_score = float(record.get("best_score_seen") or 0)
    times_scanned = int(record.get("times_scanned") or 0)
    times_deal_found = int(record.get("times_deal_found") or 0)

    if best_score >= 70 or times_deal_found >= 3:
        return "A"
    if best_score >= 50 or times_deal_found >= 1:
        return "B"
    if times_scanned >= 20:
        return "D"
    return "C"


def update_asin_performance(scanned_asins, new_deals):
    performance = load_asin_performance()
    now = fetch_keepa.iso_now()
    deals_by_asin = {str(deal.get("asin", "")).upper(): deal for deal in new_deals if deal.get("asin")}

    for asin in scanned_asins:
        asin = str(asin or "").strip().upper()
        if not asin:
            continue
        record = performance.setdefault(
            asin,
            {
                "asin": asin,
                "times_scanned": 0,
                "times_deal_found": 0,
                "times_selected": 0,
                "times_posted": 0,
                "best_score_seen": 0,
                "priority": "C",
            },
        )
        record["times_scanned"] = int(record.get("times_scanned") or 0) + 1
        record["last_scanned_at"] = now

        deal = deals_by_asin.get(asin)
        if deal:
            score = score_100_point(deal)
            record["times_deal_found"] = int(record.get("times_deal_found") or 0) + 1
            record["last_deal_date"] = now
            record["last_title"] = deal.get("title")
            record["last_price"] = deal.get("current_price")
            record["last_drop_percent"] = deal.get("drop_percent")
            record["last_drop_30_percent"] = deal.get("drop_30_percent")
            record["last_best_price_days"] = deal.get("best_price_days")
            record["last_score_seen"] = score
            record["best_score_seen"] = max(float(record.get("best_score_seen") or 0), score)

        record["priority"] = suggested_priority(record)

    save_asin_performance(performance)
    print(f"Saved ASIN performance for {len(performance)} ASINs to {PERFORMANCE_FILE}")


def merge_deals_with_performance(memory, new_deals):
    result = _original_merge_deals_with_memory(memory, new_deals)
    update_asin_performance(_selected_asins_for_run, new_deals)
    return result


fetch_keepa.read_all_asins = read_all_asins_with_source_capture
fetch_keepa.load_deal_memory = load_deal_memory_without_removed_asins
fetch_keepa.select_asins_for_run = select_asins_for_run_with_performance_capture
fetch_keepa.fetch_keepa_products = fetch_keepa_products_with_history_probe
fetch_keepa.build_deal = build_deal_with_best_price_age
fetch_keepa.merge_deals_with_memory = merge_deals_with_performance
fetch_keepa.main()
