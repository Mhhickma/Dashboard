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

# Defaults are set for an approximately 12-hour full spreadsheet rotation.
# With a 15-minute workflow schedule, 48 scan windows/day checks about 300-331 ASINs per run.
BATCH_SIZE = int(os.getenv("KEEPA_BATCH_SIZE", "100"))
REQUEST_DELAY_SECONDS = int(os.getenv("KEEPA_REQUEST_DELAY_SECONDS", "30"))
RATE_LIMIT_WAIT_SECONDS = int(os.getenv("KEEPA_RATE_LIMIT_WAIT_SECONDS", "70"))
MAX_RETRIES = int(os.getenv("KEEPA_MAX_RETRIES", "5"))
SCAN_LIMIT_RAW = os.getenv("SCAN_LIMIT", "auto").strip().lower()
SCAN_RUNS_PER_DAY = max(1, int(os.getenv("SCAN_RUNS_PER_DAY", "48")))
SCAN_LIMIT_BUFFER_PERCENT = max(0, float(os.getenv("SCAN_LIMIT_BUFFER_PERCENT", "10")))
DEAL_TTL_HOURS = int(os.getenv("DEAL_TTL_HOURS", "24"))

# Keepa stats array price indexes. These are fallback tracks only.
# Prime Exclusive is parsed from offers[].isPrimeExcl + offers[].primeExclCSV.
PRICE_TRACKS = [
    {"type": "amazon", "label": "Amazon price", "index": 0, "source_suffix": "amazon"},
    {"type": "new", "label": "New price", "index": 1, "source_suffix": "new"},
    {"type": "new_fba_prime", "label": "New FBA / Prime price", "index": 10, "source_suffix": "new_fba_prime"},
    {"type": "buy_box", "label": "Buy Box price", "index": 18, "source_suffix": "buy_box"},
]

ASIN_CSV_URL = os.getenv("ASIN_CSV_URL", "").strip()
ASIN_FILE = Path("asins.csv")
OUTPUT_FILE = Path("data/deals.json")
STATE_FILE = Path("data/scan_state.json")
MEMORY_FILE = Path("data/deals_memory.json")
ASIN_RE = re.compile(r"\bB[0-9A-Z]{9}\b")
KEEPA_EPOCH = datetime(2011, 1, 1, tzinfo=timezone.utc)
NON_AMAZON_PRICE_TYPES = {track["type"] for track in PRICE_TRACKS if track["type"] != "amazon"}
NON_AMAZON_PRICE_TYPES.add("prime_exclusive_offer")


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
        raw = str(value or "").strip().upper()
        if not raw or raw in ("ASIN", "ASINS"):
            return
        match = ASIN_RE.search(raw)
        asin = match.group(0) if match else raw
        if len(asin) != 10:
            print(f"Skipping invalid ASIN value: {raw}")
            return
        if asin in seen:
            return
        seen.add(asin)
        asins.append(asin)

    max_columns = max(len(row) for row in rows)
    for column_index in range(max_columns):
        for row in rows[1:]:
            if len(row) > column_index:
                add_asin(row[column_index])

    print(f"Loaded {len(asins)} unique ASINs from {source_name}")
    print(f"ASIN scan order: all used columns left to right ({max_columns} columns)")
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


def load_json_file(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Could not read {path}; using fallback. Error: {exc}")
        return fallback


def load_scan_state():
    state = load_json_file(STATE_FILE, {"next_start_index": 0})
    if not isinstance(state, dict):
        return {"next_start_index": 0}
    if not isinstance(state.get("next_start_index"), int):
        state["next_start_index"] = 0
    return state


def save_scan_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_deal_memory():
    payload = load_json_file(MEMORY_FILE, {})
    if isinstance(payload, dict) and isinstance(payload.get("deals"), dict):
        return payload["deals"]
    if isinstance(payload, dict):
        return payload
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
        merged = {
            **previous,
            **deal,
            "posted_at": posted_at,
            "first_seen_at": posted_at,
            "last_checked_at": now_iso,
            "expires_at": expires_at,
        }
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
        params = {
            "key": KEEPA_API_KEY,
            "domain": DOMAIN_ID,
            "asin": ",".join(batch),
            "stats": 7,
            "history": 1,
        }
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


def normalize_keepa_csv(raw_csv):
    if not raw_csv:
        return []
    if isinstance(raw_csv, str):
        try:
            raw_csv = json.loads(raw_csv)
        except Exception:
            raw_csv = [part.strip() for part in raw_csv.split(",") if part.strip()]
    if not isinstance(raw_csv, list):
        return []
    values = []
    for item in raw_csv:
        try:
            values.append(int(float(item)))
        except Exception:
            continue
    return values


def decode_keepa_price_csv(raw_csv):
    values = normalize_keepa_csv(raw_csv)
    points = []
    for i in range(0, len(values) - 1, 2):
        dt = keepa_minutes_to_datetime(values[i])
        price_cents = values[i + 1]
        if not dt or price_cents is None or price_cents <= 0:
            continue
        points.append((dt, round(price_cents / 100, 2)))
    points.sort(key=lambda item: item[0])
    return points


def latest_price_from_points(points):
    if not points:
        return None
    return points[-1][1]


def window_stats_from_points(points, days):
    if not points:
        return None, None
    now = utc_now()
    start = now - timedelta(days=days)
    relevant = []
    carry_price = None
    carry_time = start

    for dt, price in points:
        if dt <= start:
            carry_price = price
            carry_time = start
        elif dt <= now:
            relevant.append((dt, price))

    segments = []
    if carry_price is not None:
        last_time = carry_time
        last_price = carry_price
    elif relevant:
        last_time = relevant[0][0]
        last_price = relevant[0][1]
        relevant = relevant[1:]
    else:
        last_time = points[-1][0]
        last_price = points[-1][1]

    for dt, price in relevant:
        duration = max(0, (dt - last_time).total_seconds())
        if duration > 0 and last_price and last_price > 0:
            segments.append((duration, last_price))
        last_time = dt
        last_price = price

    duration = max(0, (now - last_time).total_seconds())
    if duration > 0 and last_price and last_price > 0:
        segments.append((duration, last_price))

    if not segments:
        prices = [price for _, price in points if price and price > 0]
        if not prices:
            return None, None
        return round(sum(prices) / len(prices), 2), min(prices)

    total_seconds = sum(duration for duration, _ in segments)
    avg_price = sum(duration * price for duration, price in segments) / total_seconds if total_seconds else None
    min_price = min(price for _, price in segments)
    return round(avg_price, 2) if avg_price else None, round(min_price, 2)


def best_price_days_from_points(points, current_price):
    if not points or not current_price:
        return 0, None, None
    current_cents = int(round(current_price * 100))
    best_date = None
    best_price = None
    last_seen_date = None
    for dt, price in points:
        price_cents = int(round(price * 100))
        last_seen_date = dt
        if price_cents <= current_cents:
            best_date = dt
            best_price = price
    if not last_seen_date:
        return 0, None, None
    if not best_date:
        best_date = points[0][0]
    days = max(0, int((utc_now() - best_date).total_seconds() // 86400))
    return days, best_price, best_date.date().isoformat()


def best_price_days_for_track(product, track_index, current_price):
    csv_tracks = product.get("csv") or []
    if track_index >= len(csv_tracks) or not isinstance(csv_tracks[track_index], list):
        return 0, None, None
    points = decode_keepa_price_csv(csv_tracks[track_index])
    return best_price_days_from_points(points, current_price)


def prime_exclusive_offer_points(product):
    points = []
    offers = product.get("offers") or []
    if not isinstance(offers, list):
        return points
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        if not offer.get("isPrimeExcl"):
            continue
        prime_points = decode_keepa_price_csv(offer.get("primeExclCSV"))
        points.extend(prime_points)
    points.sort(key=lambda item: item[0])
    return points


def build_track_presence_summary(products):
    summary = []
    for track in PRICE_TRACKS:
        current_count = 0
        avg30_count = 0
        lower_than_amazon_count = 0
        sample_asins = []
        for product in products:
            stats = product.get("stats") or {}
            current = price_from_stats_array(stats, "current", track["index"])
            avg30 = price_from_stats_array(stats, "avg30", track["index"])
            amazon_current = price_from_stats_array(stats, "current", 0)
            if current:
                current_count += 1
                if len(sample_asins) < 5:
                    sample_asins.append({"asin": product.get("asin"), "current_price": current, "amazon_current_price": amazon_current})
                if amazon_current and current < amazon_current:
                    lower_than_amazon_count += 1
            if avg30:
                avg30_count += 1
        summary.append({
            "price_type": track["type"],
            "label": track["label"],
            "keepa_price_index": track["index"],
            "products_with_current_price": current_count,
            "products_with_avg30_price": avg30_count,
            "products_lower_than_amazon_current": lower_than_amazon_count,
            "sample_current_prices": sample_asins,
        })

    prime_current_count = 0
    prime_lower_than_amazon_count = 0
    prime_sample_asins = []
    for product in products:
        points = prime_exclusive_offer_points(product)
        current = latest_price_from_points(points)
        amazon_current = price_from_stats_array(product.get("stats") or {}, "current", 0)
        if current:
            prime_current_count += 1
            if len(prime_sample_asins) < 10:
                prime_sample_asins.append({"asin": product.get("asin"), "current_price": current, "amazon_current_price": amazon_current})
            if amazon_current and current < amazon_current:
                prime_lower_than_amazon_count += 1
    summary.append({
        "price_type": "prime_exclusive_offer",
        "label": "New, Prime Exclusive",
        "keepa_source": "offers[].isPrimeExcl + primeExclCSV",
        "products_with_current_price": prime_current_count,
        "products_with_avg30_price": prime_current_count,
        "products_lower_than_amazon_current": prime_lower_than_amazon_count,
        "sample_current_prices": prime_sample_asins,
    })
    return summary


def raw_keepa_diagnostics(products):
    sample_products = []
    products_with_stats = 0
    products_with_csv = 0
    products_with_offers = 0
    products_with_prime_exclusive_offer = 0

    for product in products:
        stats = product.get("stats") or {}
        csv_tracks = product.get("csv") or []
        offers = product.get("offers") or []
        has_stats = isinstance(stats, dict) and bool(stats)
        has_csv = isinstance(csv_tracks, list) and any(isinstance(track, list) and track for track in csv_tracks)
        has_offers = isinstance(offers, list) and bool(offers)
        has_prime_exclusive = has_offers and any(
            isinstance(offer, dict) and offer.get("isPrimeExcl")
            for offer in offers
        )

        products_with_stats += 1 if has_stats else 0
        products_with_csv += 1 if has_csv else 0
        products_with_offers += 1 if has_offers else 0
        products_with_prime_exclusive_offer += 1 if has_prime_exclusive else 0

        if len(sample_products) < 8:
            current = stats.get("current") if isinstance(stats, dict) else []
            avg = stats.get("avg") if isinstance(stats, dict) else []
            avg30 = stats.get("avg30") if isinstance(stats, dict) else []
            sample_products.append({
                "asin": product.get("asin"),
                "has_stats": has_stats,
                "has_csv": has_csv,
                "has_offers": has_offers,
                "has_prime_exclusive_offer": has_prime_exclusive,
                "raw_current_indexes": {
                    str(track["index"]): current[track["index"]] if isinstance(current, list) and len(current) > track["index"] else None
                    for track in PRICE_TRACKS
                },
                "raw_avg_indexes": {
                    str(track["index"]): avg[track["index"]] if isinstance(avg, list) and len(avg) > track["index"] else None
                    for track in PRICE_TRACKS
                },
                "raw_avg30_indexes": {
                    str(track["index"]): avg30[track["index"]] if isinstance(avg30, list) and len(avg30) > track["index"] else None
                    for track in PRICE_TRACKS
                },
                "csv_track_lengths": [
                    len(track) if isinstance(track, list) else 0
                    for track in (csv_tracks[:20] if isinstance(csv_tracks, list) else [])
                ],
                "offer_count": len(offers) if isinstance(offers, list) else 0,
            })

    diagnostics = {
        "products_returned": len(products),
        "products_with_stats": products_with_stats,
        "products_with_csv": products_with_csv,
        "products_with_offers": products_with_offers,
        "products_with_prime_exclusive_offer": products_with_prime_exclusive_offer,
        "sample_products": sample_products,
    }
    print(f"Raw Keepa diagnostics: {json.dumps(diagnostics)}")
    return diagnostics


def qualification_for_prices(current_price, avg_7_price, avg_30_price, best_price_days):
    drop_percent = round(((avg_7_price - current_price) / avg_7_price) * 100, 1)
    drop_30_percent = round(((avg_30_price - current_price) / avg_30_price) * 100, 1)
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
    return drop_percent, drop_30_percent, qualification_reasons


def base_deal(product, asin, title, current_price, avg_7_price, min_7_price, avg_30_price, drop_percent, drop_30_percent, qualification_reasons, source, price_type, price_type_label, amazon_current_price, best_price_days, previous_price, previous_date, keepa_price_index=None):
    checked_at = iso_now()
    return {
        "asin": asin,
        "title": title,
        "current_price": current_price,
        "avg_7_price": avg_7_price,
        "min_7_price": min_7_price,
        "avg_30_price": avg_30_price,
        "min_30_price": None,
        "drop_percent": drop_percent,
        "drop_30_percent": drop_30_percent,
        "price_stats_source": source,
        "image": get_product_image(product, asin),
        "amazon_url": f"https://www.amazon.com/dp/{asin}?tag={AMAZON_TAG}",
        "checked_at": checked_at,
        "last_checked_at": checked_at,
        "price_type": price_type,
        "price_type_label": price_type_label,
        "keepa_price_index": keepa_price_index,
        "amazon_current_price": amazon_current_price,
        "best_price_days": best_price_days,
        "best_price_message": f"best price in {best_price_days} days" if best_price_days else "",
        "best_price_previous_price": previous_price,
        "best_price_previous_date": previous_date,
        "qualification_reasons": qualification_reasons,
    }


def build_deal_candidate(product, track):
    asin = product.get("asin")
    title = product.get("title") or asin
    stats = product.get("stats") or {}
    price_index = track["index"]

    current_price = price_from_stats_array(stats, "current", price_index)
    avg_7_price = price_from_stats_array(stats, "avg", price_index)
    min_7_price = price_from_stats_array(stats, "minInInterval", price_index)
    avg_30_price = price_from_stats_array(stats, "avg30", price_index)
    amazon_current_price = price_from_stats_array(stats, "current", 0)

    if not current_price or not avg_7_price or not min_7_price or not avg_30_price:
        return None
    if current_price >= avg_30_price:
        return None

    best_price_days, previous_price, previous_date = best_price_days_for_track(product, price_index, current_price)
    qualified = qualification_for_prices(current_price, avg_7_price, avg_30_price, best_price_days)
    if not qualified:
        return None
    drop_percent, drop_30_percent, qualification_reasons = qualified

    return base_deal(
        product, asin, title, current_price, avg_7_price, min_7_price, avg_30_price,
        drop_percent, drop_30_percent, qualification_reasons,
        f"keepa_stats_30_day_threshold_{track['source_suffix']}",
        track["type"], track["label"], amazon_current_price, best_price_days,
        previous_price, previous_date, price_index,
    )


def build_prime_exclusive_offer_candidate(product):
    asin = product.get("asin")
    title = product.get("title") or asin
    points = prime_exclusive_offer_points(product)
    current_price = latest_price_from_points(points)
    if not current_price:
        return None

    avg_7_price, min_7_price = window_stats_from_points(points, 7)
    avg_30_price, _ = window_stats_from_points(points, 30)
    amazon_current_price = price_from_stats_array(product.get("stats") or {}, "current", 0)
    if not avg_7_price or not min_7_price or not avg_30_price:
        return None
    if current_price >= avg_30_price:
        return None

    best_price_days, previous_price, previous_date = best_price_days_from_points(points, current_price)
    qualified = qualification_for_prices(current_price, avg_7_price, avg_30_price, best_price_days)
    if not qualified:
        return None
    drop_percent, drop_30_percent, qualification_reasons = qualified

    return base_deal(
        product, asin, title, current_price, avg_7_price, min_7_price, avg_30_price,
        drop_percent, drop_30_percent, qualification_reasons,
        "keepa_offers_prime_exclusive_csv",
        "prime_exclusive_offer", "New, Prime Exclusive", amazon_current_price, best_price_days,
        previous_price, previous_date, None,
    )


def deal_rank(deal):
    price_type = deal.get("price_type")
    current = float(deal.get("current_price") or 0)
    amazon_current = float(deal.get("amazon_current_price") or current or 0)
    savings_vs_amazon = max(0, amazon_current - current)
    return (
        2 if price_type == "prime_exclusive_offer" else 1 if price_type in NON_AMAZON_PRICE_TYPES else 0,
        savings_vs_amazon,
        float(deal.get("drop_30_percent") or 0),
        float(deal.get("drop_percent") or 0),
        int(deal.get("best_price_days") or 0),
    )


def build_deal(product):
    candidates = []
    prime_offer_candidate = build_prime_exclusive_offer_candidate(product)
    if prime_offer_candidate:
        candidates.append(prime_offer_candidate)
    for track in PRICE_TRACKS:
        candidate = build_deal_candidate(product, track)
        if candidate:
            candidates.append(candidate)
    if not candidates:
        return None
    return max(candidates, key=deal_rank)


def main():
    print("Starting Keepa price scan with stats fallback price tracks...")

    all_asins = read_all_asins()
    asins, new_state, start_index, next_start_index = select_asins_for_run(all_asins)

    print(f"Loaded {len(all_asins)} total ASINs from source")
    print(f"Loaded {len(asins)} ASINs for this run")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Request delay seconds: {REQUEST_DELAY_SECONDS}")
    print(f"Scan windows per day: {SCAN_RUNS_PER_DAY}")
    print(f"ASIN source: {'Google Sheet CSV' if ASIN_CSV_URL else 'local asins.csv'}")

    memory = load_deal_memory()
    memory, expired_count = purge_expired_deals(memory)

    products = fetch_keepa_products(asins)
    print(f"Fetched {len(products)} products from Keepa")
    price_track_scan_summary = build_track_presence_summary(products)
    keepa_raw_diagnostics = raw_keepa_diagnostics(products)

    scan_deals = []
    skipped = 0
    missing_images = 0
    non_amazon_scan_deals = 0
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
            if deal.get("price_type") in NON_AMAZON_PRICE_TYPES:
                non_amazon_scan_deals += 1
            if deal.get("price_type") == "prime_exclusive_offer":
                prime_exclusive_scan_deals += 1
            scan_deals.append(deal)

    memory, added_count, updated_count = merge_deals_with_memory(memory, scan_deals)
    all_deals = list(memory.values())
    all_deals.sort(key=lambda item: item.get("posted_at") or item.get("checked_at") or "", reverse=True)
    non_amazon_active_deals = sum(1 for deal in all_deals if deal.get("price_type") in NON_AMAZON_PRICE_TYPES)
    prime_exclusive_active_deals = sum(1 for deal in all_deals if deal.get("price_type") == "prime_exclusive_offer")

    output_payload = {
        "updated_at": iso_now(),
        "asin_source": "Google Sheet CSV" if ASIN_CSV_URL else "local asins.csv",
        "comparison_window": "Deals qualify when Amazon, New, FBA/Prime, Buy Box, or Prime Exclusive offer pricing is at least 10% below the 30-day average, at least 7% below both the 7-day and 30-day averages, or at a best price in 90+ days",
        "deal_ttl_hours": DEAL_TTL_HOURS,
        "deal_count": len(all_deals),
        "new_scan_deal_count": len(scan_deals),
        "new_deals_added": added_count,
        "existing_deals_updated": updated_count,
        "expired_deals_removed": expired_count,
        "skipped_count": skipped,
        "missing_image_count": missing_images,
        "non_amazon_scan_deal_count": non_amazon_scan_deals,
        "non_amazon_active_deal_count": non_amazon_active_deals,
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
            "keepa_product_params": {"stats": 7, "history": 1},
            "keepa_price_tracks": [
                {"price_type": track["type"], "label": track["label"], "keepa_price_index": track["index"]}
                for track in PRICE_TRACKS
            ],
            "prime_exclusive_source": "offers[].isPrimeExcl + primeExclCSV",
        },
        "price_track_scan_summary": price_track_scan_summary,
        "keepa_raw_diagnostics": keepa_raw_diagnostics,
        "deals": all_deals,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    save_deal_memory(memory)
    save_scan_state(new_state)

    print(f"Found {len(scan_deals)} price drops in this scan")
    print(f"Non-Amazon price source deals in this scan: {non_amazon_scan_deals}")
    print(f"Prime Exclusive offer deals in this scan: {prime_exclusive_scan_deals}")
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
