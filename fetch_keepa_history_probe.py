from datetime import datetime, timezone, timedelta

import fetch_keepa

HISTORY_EXAMPLE_LIMIT = 5
KEEPA_TIME_BASE = datetime(2011, 1, 1, tzinfo=timezone.utc)
# Keepa product csv indexes: 0 Amazon, 1 Marketplace New, 10 New FBA, 17 Buy Box with shipping.
PRICE_HISTORY_INDEXES = (0, 1, 10, 17)
_original_fetch_keepa_products = fetch_keepa.fetch_keepa_products


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
    print_history_examples(products)
    return products


fetch_keepa.fetch_keepa_products = fetch_keepa_products_with_history_probe
fetch_keepa.main()
