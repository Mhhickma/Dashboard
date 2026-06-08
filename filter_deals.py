import json
from pathlib import Path

DEALS_FILE = Path("data/deals.json")
MEMORY_FILE = Path("data/deals_memory.json")

MIN_30_DAY_DROP = 10.0
MIN_COMBINED_DROP = 7.0
MIN_RARE_PRICE_DAYS = 90
QUALIFICATION_DESCRIPTION = (
    "Deals qualify when they are at least 10% below the 30-day average, "
    "at least 7% below both the 7-day and 30-day averages, or at a best price in 90+ days"
)


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def qualification_reasons(deal):
    reasons = []
    drop_7 = number(deal.get("drop_percent"))
    drop_30 = number(deal.get("drop_30_percent"))
    best_price_days = number(deal.get("best_price_days"))

    if drop_30 >= MIN_30_DAY_DROP:
        reasons.append("10%+ below 30-day average")
    if drop_7 >= MIN_COMBINED_DROP and drop_30 >= MIN_COMBINED_DROP:
        reasons.append("7%+ below both 7-day and 30-day averages")
    if best_price_days >= MIN_RARE_PRICE_DAYS:
        reasons.append("best price in 90+ days")

    return reasons


def qualify(deal):
    reasons = qualification_reasons(deal)
    if not reasons:
        return False
    deal["qualification_reasons"] = reasons
    return True


def filter_memory():
    payload = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    memory = payload.get("deals", {})
    before = len(memory)
    filtered = {asin: deal for asin, deal in memory.items() if qualify(deal)}
    payload["deals"] = filtered
    payload["qualification_rules"] = QUALIFICATION_DESCRIPTION
    MEMORY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return filtered, before - len(filtered)


def filter_dashboard(filtered_memory, removed_count):
    payload = json.loads(DEALS_FILE.read_text(encoding="utf-8"))
    ordered_asins = [deal.get("asin") for deal in payload.get("deals", [])]
    ordered_deals = [filtered_memory[asin] for asin in ordered_asins if asin in filtered_memory]
    remaining_asins = set(filtered_memory) - set(ordered_asins)
    ordered_deals.extend(filtered_memory[asin] for asin in remaining_asins)

    payload["comparison_window"] = QUALIFICATION_DESCRIPTION
    payload["qualification_rules"] = {
        "min_30_day_drop_percent": MIN_30_DAY_DROP,
        "min_both_7_and_30_day_drop_percent": MIN_COMBINED_DROP,
        "min_rare_price_days": MIN_RARE_PRICE_DAYS,
        "logic": "any rule may qualify a deal",
    }
    payload["deal_count"] = len(ordered_deals)
    payload["qualification_filter_removed"] = removed_count
    payload["deals"] = ordered_deals
    DEALS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    filtered_memory, removed_count = filter_memory()
    filter_dashboard(filtered_memory, removed_count)
    print(f"Qualification filter kept {len(filtered_memory)} deals and removed {removed_count} weak deals.")
    print(QUALIFICATION_DESCRIPTION)


if __name__ == "__main__":
    main()
