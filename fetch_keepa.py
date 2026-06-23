import csv
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(1024 * 1024 * 1024)

KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
AMAZON_TAG = os.getenv("AMAZON_TAG") or "simplewoodsho-20"
DOMAIN_ID = int(os.getenv("KEEPA_DOMAIN_ID", "1"))
MIN_DROP_PERCENT = float(os.getenv("MIN_DROP_PERCENT", "0"))

BATCH_SIZE = int(os.getenv("KEEPA_BATCH_SIZE", "25"))
REQUEST_DELAY_SECONDS = int(os.getenv("KEEPA_REQUEST_DELAY_SECONDS", "60"))
RATE_LIMIT_WAIT_SECONDS = int(os.getenv("KEEPA_RATE_LIMIT_WAIT_SECONDS", "70"))
MAX_RETRIES = int(os.getenv("KEEPA_MAX_RETRIES", "5"))
SCAN_LIMIT_RAW = os.getenv("SCAN_LIMIT", "auto").strip().lower()
SCAN_RUNS_PER_DAY = max(1, int(os.getenv("SCAN_RUNS_PER_DAY", "96")))
SCAN_LIMIT_BUFFER_PERCENT = max(0, float(os.getenv("SCAN_LIMIT_BUFFER_PERCENT", "10")))
DEAL_TTL_HOURS = int(os.getenv("DEAL_TTL_HOURS", "24"))

# Keepa stats array price indexes.
# 0 = Amazon price. 32 is the configurable track for New, Prime Exclusive pricing.
PRIME_EXCLUSIVE_PRICE_INDEX = int(os.getenv("KEEPA_PRIME_EXCLUSIVE_PRICE_INDEX", "32"))
PRICE_TRACKS = [
    {"type": "amazon", "label": "Amazon price", "index": 0, "source_suffix": "amazon"},
    {"type": "prime_exclusive_new", "label": "New, Prime Exclusive", "index": PRIME_EXCLUSIVE_PRICE_INDEX, "source_suffix": "prime_exclusive_new"},
]

ASIN_CSV_URL = os.getenv("ASIN_CSV_URL", "").strip()
ASIN_FILE = Path("asins.csv")
OUTPUT_FILE = Path("data/deals.json")
STATE_FILE = Path("data/scan_state.json")
MEMORY_FILE = Path("data/deals_memory.json")
ASIN_RE = re.compile(r"\bB[0-9A-Z]{9}\b")
KEEPA_EPOCH = datetime(2011, 1, 1, tzinfo=timezone.utc)


def utc_now():
    return datetime.now(timezone.utc)


def iso_now():
    return utc_now().isoformat()


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def keepa_to_dollars(value):
    if value is None:
        return None
    if isinstance(value, list):
        numeric_values = [item for item in value if isinstance(item, (int, float))]
        if not numeric_values:
            return None
        value = numeric_values[-1]
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return round(value / 100, 2)


def price_from_stats_array(stats, key, price_index):
    values = stats.get(key) or []
    if len(values) <= price_index:
        return None
    return keepa_to_dollars(values[price_index])


def amazon_image_fallback(asin):
    if not asin:
        return None
    return (
        "https://ws-na.amazon-adsystem.com/widgets/q?"
        f"_encoding=UTF8&ASIN={asin}&Format=_SL500_&ID=AsinImage"
        "&MarketPlace=US&ServiceVersion=20070822"
    )


def get_product_image(product, asin):
    images_csv = product.get("imagesCSV") or ""
    if images_csv:
        first_image = images_csv.split(",")[0].strip()
        if first_image:
            if first_image.startswith("http"):
                return first_image
            return f"https://images-na.ssl-images-amazon.com/images/I/{first_image}"
    return amazon_image_fallback(asin)


def asins_from_csv_text(csv_text, source_name):
    asins = []
    seen = set()
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        raise ValueError(f"No rows found in {source_name}")

    def add_asin(value):
        asin = str(value or "").strip().upper()
        if not asin or asin in ("ASIN", "ASINS"):
            return
        if len(asin) != 10:
            print(f"Skipping invalid ASIN value: {asin}")
            return
        if asin in seen:
            return
        seen.add(asin)
        asins.append(asin)

    for column_index in range(3):
        for row in rows[1:]:
            if len(row) > column_index:
                add_asin(row[column_index])

    print(f"Loaded {len(asins)} unique ASINs from {source_name}")
    print("ASIN scan order: Column A first, then Column B, then Column C")
    return asins


def read_asins_from_google_sheet():
    print(f"Reading ASINs from Google Sheet CSV: {ASIN_CSV_URL}")
    response = requests.get(ASIN_CSV_URL, timeout=45)
    response.raise_for_status()
    return asins_from_csv_text(response.text, "Google Sheet CSV")


def read_asins_from_local_file():
    if not ASIN_FILE.exists():
        raise FileNotFoundError("Missing asins.csv")
    return asins_from_csv_text(ASIN_FILE.read_text(encoding="utf-8"), "asins.csv")


def read_all_asins():
    try:
        return read_asins_from_google_sheet() if ASIN_CSV_URL else read_asins_from_local_file()
    except Exception as exc:
        if ASIN_CSV_URL:
            print(f"Could not read Google Sheet CSV: {exc}")
            print("Falling back to local asins.csv")
            return read_asins_from_local_file()
        raise


def load_scan_state():
    if not STATE_FILE.exists():
        return {"next_start_index": 0}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(state.get("next_start_index"), int):
            state["next_start_index"] = 0
        return state
    except Exception as exc:
        print(f"Could not read scan state; starting from top. Error: {exc}")
        return {"next_start_index": 0}


def save_scan_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_deal_memory():
    if not MEMORY_FILE.exists():
        return {}
    try:
        payload = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("deals"), dict):
            return payload["deals"]
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        print(f"Could not read deal memory; starting new memory. Error: {exc}")
    return {}


def save_deal_memory(memory):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(
        json.dumps({"updated_at": iso_now(), "deal_ttl_hours": DEAL_TTL_HOURS, "deals": memory}, indent=2),
        encoding="utf-8",
    )


def purge_expired_deals(memory):
    cutoff = utc_now() - timedelta(hours=DEAL_TTL_HOURS)
    kept = {}
    expired_count = 0
    for asin, deal in memory.items():
        posted_at = parse_iso_datetime(deal.get("posted_at") or deal.get("first_seen_at") or deal.get("checked_at"))
        if posted_at and posted_at > cutoff:
            kept[asin] = deal
        else:
            expired_count += 1
    if expired_count:
        print(f"Purged {expired_count} expired deals older than {DEAL_TTL_HOURS} hours")
    return kept, expired_count


def merge_deals_with_memory(memory, new_deals):
    now_iso = iso_now()
    expires_at = (utc_now() + timedelta(hours=DEAL_TTL_HOURS)).isoformat()
    added_count = 0
    updated_count = 0
    for deal in new_deals:
        asin = deal.get("asin")
        if not asin:
            continue
        previous = memory.get(asin, {})
        posted_at = previous.get("posted_at") or previous.get("first_seen_at") or now_iso
        merged = {**previous, **deal, "posted_at": posted_at, "first_seen_at": posted_at, "last_checked_at": now_iso, "expires_at": expires_at}
        if asin in memory:
            updated_count += 1
        else:
            added_count += 1
        memory[asin] = merged
    return memory, added_count, updated_count


def select_asins_for_run(all_asins):
    total = len(all_asins)
    if total == 0:
        return [], {"next_start_index": 0}, 0, 0
    if SCAN_LIMIT_RAW in ("auto", "dynamic"):
        daily_buffer = 1 + (SCAN_LIMIT_BUFFER_PERCENT / 100)
        limit = int((total * daily_buffer + SCAN_RUNS_PER_DAY - 1) // SCAN_RUNS_PER_DAY)
        print(f"Auto scan limit: {limit} ASINs per run for {total} total ASINs")
    else:
        limit = int(SCAN_LIMIT_RAW)
    limit = min(limit if limit > 0 else total, total)
    state = load_scan_state()
    start_index = state.get("next_start_index", 0)
    if start_index >= total or start_index < 0:
        start_index = 0
    end_index = start_index + limit
    wrapped = end_index > total
    if wrapped:
        selected = all_asins[start_index:] + all_asins[: end_index % total]
        next_start_index = end_index % total
    else:
        selected = all_asins[start_index:end_index]
        next_start_index = 0 if end_index >= total else end_index
    new_state = {
        "next_start_index": next_start_index,
        "last_start_index": start_index,
        "last_end_index": next_start_index if wrapped else end_index,
        "last_scan_limit": limit,
        "last_total_asins": total,
        "last_wrapped": wrapped,
        "last_scan_at": iso_now(),
    }
    print(f"Rotating scan: total ASINs={total}, start row={start_index + 2}, count={len(selected)}, next start row={next_start_index + 2}")
    return selected, new_state, start_index, next_start_index


def fetch_keepa_batch(url, params, batch_number):
    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(url, params=params, timeout=60)
        if response.status_code == 429:
            wait_seconds = RATE_LIMIT_WAIT_SECONDS * attempt
            print(f"Keepa rate limit on batch {batch_number}. Waiting {wait_seconds} seconds before retry {attempt}/{MAX_RETRIES}...")
            time.sleep(wait_seconds)
            continue
        if response.status_code >= 400:
            print(f"Keepa error {response.status_code} on batch {batch_number}: {response.text[:500]}")
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"Keepa rate limit did not clear after {MAX_RETRIES} retries on batch {batch_number}")


def fetch_keepa_products(asins):
    if not KEEPA_API_KEY:
        raise RuntimeError("Missing KEEPA_API_KEY environment variable")
    url = "https://api.keepa.com/product"
    all_products = []
    for i in range(0, len(asins), BATCH_SIZE):
        batch = asins[i : i + BATCH_SIZE]
        batch_number = (i // BATCH_SIZE) + 1
        print(f"Fetching batch {batch_number}: {len(batch)} ASINs")
        params = {"key": KEEPA_API_KEY, "domain": DOMAIN_ID, "asin": ",".join(batch), "stats": 7, "history": 1}
        payload = fetch_keepa_batch(url, params, batch_number)
        all_products.extend(payload.get("products", []))
        tokens_left = payload.get("tokensLeft")
        refill_in = payload.get("refillIn")
        if tokens_left is not None:
            print(f"Keepa tokens left after batch {batch_number}: {tokens_left}")
        if refill_in is not None:
            print(f"Keepa refill in: {refill_in} ms")
        if i + BATCH_SIZE < len(asins):
            print(f"Waiting {REQUEST_DELAY_SECONDS} seconds before next batch...")
            time.sleep(REQUEST_DELAY_SECONDS)
    return all_products


def keepa_minutes_to_datetime(minutes):
    if not isinstance(minutes, (int, float)):
        return None
    return KEEPA_EPOCH + timedelta(minutes=minutes)


def best_price_days_for_track(product, track_index, current_price):
    csv_tracks = product.get("csv") or []
    if track_index >= len(csv_tracks) or not isinstance(csv_tracks[track_index], list):
        return 0, None, None
    history = csv_tracks[track_index]
    if len(history) < 2:
        return 0, None, None

    current_cents = int(round(current_price * 100))
    best_date = None
    best_price = None
    last_seen_date = None
    for i in range(0, len(history) - 1, 2):
        keepa_minute = history[i]
        price_cents = history[i + 1]
        if not isinstance(price_cents, (int, float)) or price_cents <= 0:
            continue
        point_date = keepa_minutes_to_datetime(keepa_minute)
        if not point_date:
            continue
        last_seen_date = point_date
        if price_cents <= current_cents:
            best_date = point_date
            best_price = round(price_cents / 100, 2)

    if not last_seen_date:
        return 0, None, None
    if not best_date:
        best_date = keepa_minutes_to_datetime(history[0]) or last_seen_date
    days = max(0, int((utc_now() - best_date).total_seconds() // 86400))
    return days, best_price, best_date.date().isoformat()


def build_deal_candidate(product, track):
    asin = product.get("asin")
    title = product.get("title") or asin
    stats = product.get("stats") or {}
    price_index = track["index"]

    current_price = price_from_stats_array(stats, "current", price_index)
    avg_7_price = price_from_stats_array(stats, "avg", price_index)
    min_7_price = price_from_stats_array(stats, "minInInterval", price_index)
    avg_30_price = price_from_stats_array(stats, "avg30", price_index)

    if not current_price or not avg_7_price or not min_7_price or not avg_30_price:
        return None
    if current_price >= avg_30_price:
        return None

    drop_percent = round(((avg_7_price - current_price) / avg_7_price) * 100, 1)
    drop_30_percent = round(((avg_30_price - current_price) / avg_30_price) * 100, 1)
    best_price_days, previous_price, previous_date = best_price_days_for_track(product, price_index, current_price)

    qualification_reasons = []
    if drop_30_percent >= 10:
        qualification_reasons.append("10%+ below 30-day average")
    if drop_percent >= 7 and drop_30_percent >= 7:
        qualification_reasons.append("7%+ below both 7-day and 30-day averages")
    if best_price_days >= 90:
        qualification_reasons.append("best price in 90+ days")
    if drop_30_percent < MIN_DROP_PERCENT and not qualification_reasons:
        return None
    if not qualification_reasons:
        return None

    checked_at = iso_now()
    deal = {
        "asin": asin,
        "title": title,
        "current_price": current_price,
        "avg_7_price": avg_7_price,
        "min_7_price": min_7_price,
        "avg_30_price": avg_30_price,
        "min_30_price": None,
        "drop_percent": drop_percent,
        "drop_30_percent": drop_30_percent,
        "price_stats_source": f"keepa_stats_30_day_threshold_{track['source_suffix']}",
        "image": get_product_image(product, asin),
        "amazon_url": f"https://www.amazon.com/dp/{asin}?tag={AMAZON_TAG}",
        "checked_at": checked_at,
        "last_checked_at": checked_at,
        "price_type": track["type"],
        "price_type_label": track["label"],
        "keepa_price_index": price_index,
        "best_price_days": best_price_days,
        "best_price_message": f"best price in {best_price_days} days" if best_price_days else "",
        "best_price_previous_price": previous_price,
        "best_price_previous_date": previous_date,
        "qualification_reasons": qualification_reasons,
    }
    return deal


def deal_rank(deal):
    return (
        1 if deal.get("price_type") == "prime_exclusive_new" else 0,
        float(deal.get("drop_30_percent") or 0),
        float(deal.get("drop_percent") or 0),
        int(deal.get("best_price_days") or 0),
    )


def build_deal(product):
    candidates = []
    for track in PRICE_TRACKS:
        candidate = build_deal_candidate(product, track)
        if candidate:
            candidates.append(candidate)
    if not candidates:
        return None
    return max(candidates, key=deal_rank)


def main():
    print("Starting Keepa price scan with Amazon and New, Prime Exclusive price tracks...")
    print(f"Prime Exclusive Keepa price index: {PRIME_EXCLUSIVE_PRICE_INDEX}")

    all_asins = read_all_asins()
    asins, new_state, start_index, next_start_index = select_asins_for_run(all_asins)

    print(f"Loaded {len(all_asins)} total ASINs from source")
    print(f"Loaded {len(asins)} ASINs for this run")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"ASIN source: {'Google Sheet CSV' if ASIN_CSV_URL else 'local asins.csv'}")

    memory = load_deal_memory()
    memory, expired_count = purge_expired_deals(memory)

    products = fetch_keepa_products(asins)
    print(f"Fetched {len(products)} products from Keepa")

    scan_deals = []
    skipped = 0
    missing_images = 0
    prime_exclusive_scan_deals = 0

    for product in products:
        try:
            deal = build_deal(product)
        except Exception as exc:
            skipped += 1
            print(f"Skipped {product.get('asin', 'unknown ASIN')}: {exc}")
            continue
        if deal:
            if not deal.get("image"):
                missing_images += 1
                print(f"No image found for {deal.get('asin')}")
            if deal.get("price_type") == "prime_exclusive_new":
                prime_exclusive_scan_deals += 1
            scan_deals.append(deal)

    memory, added_count, updated_count = merge_deals_with_memory(memory, scan_deals)
    all_deals = list(memory.values())
    all_deals.sort(key=lambda item: item.get("posted_at") or item.get("checked_at") or "", reverse=True)
    prime_exclusive_active_deals = sum(1 for deal in all_deals if deal.get("price_type") == "prime_exclusive_new")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "updated_at": iso_now(),
                "asin_source": "Google Sheet CSV" if ASIN_CSV_URL else "local asins.csv",
                "comparison_window": "Deals qualify when Amazon or New, Prime Exclusive price is at least 10% below the 30-day average, at least 7% below both the 7-day and 30-day averages, or at a best price in 90+ days",
                "deal_ttl_hours": DEAL_TTL_HOURS,
                "deal_count": len(all_deals),
                "new_scan_deal_count": len(scan_deals),
                "new_deals_added": added_count,
                "existing_deals_updated": updated_count,
                "expired_deals_removed": expired_count,
                "skipped_count": skipped,
                "missing_image_count": missing_images,
                "prime_exclusive_scan_deal_count": prime_exclusive_scan_deals,
                "prime_exclusive_active_deal_count": prime_exclusive_active_deals,
                "creator_campaign_deal_count": 0,
                "scan_window": {
                    "total_asins": len(all_asins),
                    "start_index": start_index,
                    "start_sheet_row": start_index + 2,
                    "next_start_index": next_start_index,
                    "next_start_sheet_row": next_start_index + 2,
                    "scan_count": len(asins),
                },
                "settings": {
                    "min_drop_percent": MIN_DROP_PERCENT,
                    "batch_size": BATCH_SIZE,
                    "request_delay_seconds": REQUEST_DELAY_SECONDS,
                    "rate_limit_wait_seconds": RATE_LIMIT_WAIT_SECONDS,
                    "scan_limit": SCAN_LIMIT_RAW,
                    "scan_runs_per_day": SCAN_RUNS_PER_DAY,
                    "scan_limit_buffer_percent": SCAN_LIMIT_BUFFER_PERCENT,
                    "deal_ttl_hours": DEAL_TTL_HOURS,
                    "keepa_stats_days": 7,
                    "keepa_price_tracks": [
                        {"price_type": track["type"], "label": track["label"], "keepa_price_index": track["index"]}
                        for track in PRICE_TRACKS
                    ],
                    "keepa_prime_exclusive_price_index": PRIME_EXCLUSIVE_PRICE_INDEX,
                },
                "deals": all_deals,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    save_deal_memory(memory)
    save_scan_state(new_state)

    print(f"Found {len(scan_deals)} price drops in this scan")
    print(f"Prime Exclusive deals in this scan: {prime_exclusive_scan_deals}")
    print(f"Prime Exclusive active deals: {prime_exclusive_active_deals}")
    print(f"Added {added_count} new deals and updated {updated_count} existing deals")
    print(f"Saved {len(all_deals)} active 24-hour deals to {OUTPUT_FILE}")
    print(f"Saved deal memory to {MEMORY_FILE}")
    print(f"Saved next scan start index {new_state['next_start_index']} to {STATE_FILE}")
    if skipped:
        print(f"Skipped {skipped} products because their Keepa data format was incomplete or unexpected")
    if missing_images:
        print(f"{missing_images} deals did not include an image from Keepa or Amazon fallback")


if __name__ == "__main__":
    main()
