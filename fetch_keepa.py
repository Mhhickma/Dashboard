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
MIN_DROP_PERCENT = float(os.getenv("MIN_DROP_PERCENT", "5"))

BATCH_SIZE = int(os.getenv("KEEPA_BATCH_SIZE", "50"))
REQUEST_DELAY_SECONDS = int(os.getenv("KEEPA_REQUEST_DELAY_SECONDS", "2"))
RATE_LIMIT_WAIT_SECONDS = int(os.getenv("KEEPA_RATE_LIMIT_WAIT_SECONDS", "70"))
MAX_RETRIES = int(os.getenv("KEEPA_MAX_RETRIES", "5"))
SCAN_LIMIT = int(os.getenv("SCAN_LIMIT", "100"))
DEAL_TTL_HOURS = int(os.getenv("DEAL_TTL_HOURS", "24"))

CREATOR_CONNECTIONS_REPO = os.getenv("CREATOR_CONNECTIONS_REPO", "Mhhickma/influencer-prospects")
CREATOR_CONNECTIONS_PATH = os.getenv("CREATOR_CONNECTIONS_PATH", "creator-connections")
CREATOR_CONNECTIONS_REF = os.getenv("CREATOR_CONNECTIONS_REF", "main")
CREATOR_CONNECTIONS_MAX_FILES = int(os.getenv("CREATOR_CONNECTIONS_MAX_FILES", "40"))
CREATOR_CONNECTIONS_MAX_FILE_AGE_DAYS = int(os.getenv("CREATOR_CONNECTIONS_MAX_FILE_AGE_DAYS", "45"))

ASIN_CSV_URL = os.getenv("ASIN_CSV_URL", "").strip()
ASIN_FILE = Path("asins.csv")
OUTPUT_FILE = Path("data/deals.json")
STATE_FILE = Path("data/scan_state.json")
MEMORY_FILE = Path("data/deals_memory.json")
ASIN_RE = re.compile(r"\bB[0-9A-Z]{9}\b")


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


def parse_campaign_date(value):
    value = str(value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
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


def price_from_stats_array(stats, key, price_index=0):
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

    for row in rows[1:]:
        if len(row) > 0:
            add_asin(row[0])

    for row in rows[1:]:
        if len(row) > 1:
            add_asin(row[1])

    print(f"Loaded {len(asins)} unique ASINs from {source_name}")
    print("ASIN scan order: Column A first, then Column B")
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
        json.dumps(
            {
                "updated_at": iso_now(),
                "deal_ttl_hours": DEAL_TTL_HOURS,
                "deals": memory,
            },
            indent=2,
        ),
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

    limit = SCAN_LIMIT if SCAN_LIMIT > 0 else total
    limit = min(limit, total)
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

    print(
        f"Rotating scan: total ASINs={total}, start row={start_index + 2}, "
        f"count={len(selected)}, next start row={next_start_index + 2}"
    )
    if wrapped:
        print("Rotating scan wrapped back to the top of the sheet.")

    return selected, new_state, start_index, next_start_index


def normalize_commission(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.endswith("%"):
        number = raw[:-1].strip()
    else:
        number = raw
    try:
        numeric = float(number)
        if numeric.is_integer():
            return f"{int(numeric)}%"
        return f"{numeric:g}%"
    except ValueError:
        return raw


def commission_number(value):
    text = normalize_commission(value).replace("%", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def campaign_from_row(row, today):
    start_date = parse_campaign_date(row.get("Campaign Start Date"))
    end_date = parse_campaign_date(row.get("Campaign End Date"))
    active = (start_date is None or start_date <= today) and (end_date is None or end_date >= today)
    recommended = str(row.get("Recommended", "")).strip().lower() == "true"

    return {
        "campaign_id": str(row.get("Campaign Id", "")).strip(),
        "campaign_name": str(row.get("Campaign Name", "")).strip(),
        "campaign_brand": str(row.get("Brand Name", "")).strip(),
        "commission_rate": normalize_commission(row.get("Commission Rate", "")),
        "campaign_start_date": str(row.get("Campaign Start Date", "")).strip(),
        "campaign_end_date": str(row.get("Campaign End Date", "")).strip(),
        "recommended": recommended,
        "active": active,
    }


def campaign_rank(campaign):
    return (
        1 if campaign.get("recommended") else 0,
        commission_number(campaign.get("commission_rate")),
        campaign.get("campaign_end_date") or "",
    )


def github_api_get(url, timeout=45):
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response


def creator_connection_file_commit_date(path):
    api_url = (
        f"https://api.github.com/repos/{CREATOR_CONNECTIONS_REPO}/commits"
        f"?path={path}&sha={CREATOR_CONNECTIONS_REF}&per_page=1"
    )
    try:
        commits = github_api_get(api_url).json()
        if not commits:
            return None
        commit = commits[0].get("commit", {})
        author = commit.get("author", {})
        return parse_iso_datetime(author.get("date"))
    except Exception as exc:
        print(f"Could not read Creator Connections commit date for {path}: {exc}")
        return None


def creator_connection_file_urls():
    api_url = (
        f"https://api.github.com/repos/{CREATOR_CONNECTIONS_REPO}/contents/"
        f"{CREATOR_CONNECTIONS_PATH}?ref={CREATOR_CONNECTIONS_REF}"
    )
    files = github_api_get(api_url).json()
    csv_files = []
    for item in files:
        if item.get("type") == "file" and item.get("name", "").lower().endswith(".csv"):
            download_url = item.get("download_url")
            path = item.get("path")
            if download_url and path:
                csv_files.append(
                    {
                        "name": item.get("name", ""),
                        "path": path,
                        "download_url": download_url,
                        "updated_at": creator_connection_file_commit_date(path),
                    }
                )

    csv_files.sort(key=lambda item: item.get("updated_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    latest_updated_at = csv_files[0].get("updated_at") if csv_files else None
    cutoff = utc_now() - timedelta(days=CREATOR_CONNECTIONS_MAX_FILE_AGE_DAYS)
    selected = [
        item for item in csv_files
        if item.get("updated_at") is None or item.get("updated_at") >= cutoff
    ][:CREATOR_CONNECTIONS_MAX_FILES]

    return selected, {
        "files_available": len(csv_files),
        "files_selected": len(selected),
        "latest_csv_file": csv_files[0].get("name") if csv_files else "",
        "latest_csv_updated_at": latest_updated_at.isoformat() if latest_updated_at else "",
        "max_files": CREATOR_CONNECTIONS_MAX_FILES,
        "max_file_age_days": CREATOR_CONNECTIONS_MAX_FILE_AGE_DAYS,
    }


def find_creator_campaigns_for_asins(target_asins):
    target_asins = {str(asin).strip().upper() for asin in target_asins if asin}
    if not target_asins:
        return {}, {"files_scanned": 0, "rows_scanned": 0, "asins_matched": 0}

    today = utc_now().date()
    matches = {}
    files_scanned = 0
    rows_scanned = 0

    try:
        files, file_stats = creator_connection_file_urls()
    except Exception as exc:
        print(f"Could not list Creator Connections files: {exc}")
        return matches, {"files_scanned": 0, "rows_scanned": 0, "asins_matched": 0}

    print(f"Checking Creator campaign status for {len(target_asins)} dashboard ASINs...")
    if file_stats.get("latest_csv_updated_at"):
        print(
            "Latest Creator Connections CSV update: "
            f"{file_stats['latest_csv_updated_at']} ({file_stats.get('latest_csv_file', '')})"
        )

    for item in files:
        files_scanned += 1
        url = item.get("download_url")
        print(f"Scanning Creator Connections file {files_scanned}/{len(files)}: {item.get('name', '')}")
        try:
            with requests.get(url, stream=True, timeout=180) as response:
                response.raise_for_status()
                lines = response.iter_lines(decode_unicode=True)
                reader = csv.DictReader(lines)
                for row in reader:
                    rows_scanned += 1
                    asin_list = row.get("ASIN List", "")
                    row_asins = set(ASIN_RE.findall(asin_list.upper()))
                    relevant_asins = target_asins.intersection(row_asins)
                    if not relevant_asins:
                        continue

                    campaign = campaign_from_row(row, today)
                    if not campaign.get("active"):
                        continue

                    for asin in relevant_asins:
                        existing = matches.get(asin)
                        if existing and campaign_rank(existing) >= campaign_rank(campaign):
                            continue
                        matches[asin] = campaign
        except Exception as exc:
            print(f"Could not scan Creator Connections file {url}: {exc}")

    print(
        f"Creator Connections: matched {len(matches)} ASINs "
        f"from {files_scanned} files and {rows_scanned} rows"
    )
    return matches, {
        "files_scanned": files_scanned,
        "rows_scanned": rows_scanned,
        "asins_matched": len(matches),
        **file_stats,
    }


def apply_creator_campaigns(memory, campaign_by_asin):
    matched = 0
    for asin, deal in memory.items():
        campaign = campaign_by_asin.get(str(asin).upper())
        if campaign:
            deal["has_creator_campaign"] = True
            deal["creator_campaign"] = campaign
            deal["creator_commission_rate"] = campaign.get("commission_rate", "")
            matched += 1
        else:
            deal.pop("has_creator_campaign", None)
            deal.pop("creator_campaign", None)
            deal.pop("creator_commission_rate", None)
    return matched


def fetch_keepa_batch(url, params, batch_number):
    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(url, params=params, timeout=60)

        if response.status_code == 429:
            wait_seconds = RATE_LIMIT_WAIT_SECONDS * attempt
            print(
                f"Keepa rate limit on batch {batch_number}. "
                f"Waiting {wait_seconds} seconds before retry {attempt}/{MAX_RETRIES}..."
            )
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


def build_deal(product):
    asin = product.get("asin")
    title = product.get("title") or asin
    stats = product.get("stats") or {}

    current_price = price_from_stats_array(stats, "current")
    avg_7_price = price_from_stats_array(stats, "avg")
    min_7_price = price_from_stats_array(stats, "minInInterval")
    avg_30_price = price_from_stats_array(stats, "avg30")
    min_30_price = None

    if not current_price or not avg_7_price or not min_7_price:
        return None
    if current_price >= avg_7_price:
        return None

    drop_percent = round(((avg_7_price - current_price) / avg_7_price) * 100, 1)
    if drop_percent < MIN_DROP_PERCENT:
        return None

    drop_30_percent = None
    if avg_30_price and current_price < avg_30_price:
        drop_30_percent = round(((avg_30_price - current_price) / avg_30_price) * 100, 1)

    image = get_product_image(product, asin)
    amazon_url = f"https://www.amazon.com/dp/{asin}?tag={AMAZON_TAG}"
    checked_at = iso_now()

    return {
        "asin": asin,
        "title": title,
        "current_price": current_price,
        "avg_7_price": avg_7_price,
        "min_7_price": min_7_price,
        "avg_30_price": avg_30_price,
        "min_30_price": min_30_price,
        "drop_percent": drop_percent,
        "drop_30_percent": drop_30_percent,
        "price_stats_source": "keepa_stats_7_days",
        "image": image,
        "amazon_url": amazon_url,
        "checked_at": checked_at,
        "last_checked_at": checked_at,
    }


def main():
    print("Starting Keepa price scan with rotating ASIN window and 24-hour deal memory...")

    all_asins = read_all_asins()
    asins, new_state, start_index, next_start_index = select_asins_for_run(all_asins)

    print(f"Loaded {len(all_asins)} total ASINs from source")
    print(f"Loaded {len(asins)} ASINs for this run")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Normal delay between batches: {REQUEST_DELAY_SECONDS} seconds")
    print(f"Rate-limit retry wait: {RATE_LIMIT_WAIT_SECONDS} seconds")
    print(f"Scan limit: {SCAN_LIMIT if SCAN_LIMIT > 0 else 'off'}")
    print(f"Deal TTL: {DEAL_TTL_HOURS} hours")
    print("Keepa stats=7 is used: avg = 7-day average, minInInterval = 7-day low")
    print(f"ASIN source: {'Google Sheet CSV' if ASIN_CSV_URL else 'local asins.csv'}")

    memory = load_deal_memory()
    memory, expired_count = purge_expired_deals(memory)

    campaign_target_asins = set(asins) | set(memory.keys())
    campaign_by_asin, campaign_stats = find_creator_campaigns_for_asins(campaign_target_asins)

    products = fetch_keepa_products(asins)
    print(f"Fetched {len(products)} products from Keepa")

    scan_deals = []
    skipped = 0
    missing_images = 0

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
            scan_deals.append(deal)

    memory, added_count, updated_count = merge_deals_with_memory(memory, scan_deals)
    creator_campaign_deal_count = apply_creator_campaigns(memory, campaign_by_asin)

    all_deals = list(memory.values())
    all_deals.sort(key=lambda item: item.get("posted_at") or item.get("checked_at") or "", reverse=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "updated_at": iso_now(),
                "asin_source": "Google Sheet CSV" if ASIN_CSV_URL else "local asins.csv",
                "comparison_window": "Keepa stats=7 for 7-day average and 7-day low",
                "deal_ttl_hours": DEAL_TTL_HOURS,
                "deal_count": len(all_deals),
                "new_scan_deal_count": len(scan_deals),
                "new_deals_added": added_count,
                "existing_deals_updated": updated_count,
                "expired_deals_removed": expired_count,
                "skipped_count": skipped,
                "missing_image_count": missing_images,
                "creator_campaign_deal_count": creator_campaign_deal_count,
                "creator_connections": {
                    "repo": CREATOR_CONNECTIONS_REPO,
                    "path": CREATOR_CONNECTIONS_PATH,
                    "ref": CREATOR_CONNECTIONS_REF,
                    **campaign_stats,
                },
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
                    "scan_limit": SCAN_LIMIT,
                    "deal_ttl_hours": DEAL_TTL_HOURS,
                    "keepa_stats_days": 7,
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
    print(f"Added {added_count} new deals and updated {updated_count} existing deals")
    print(f"Marked {creator_campaign_deal_count} active deals with Creator campaign commission data")
    print(f"Saved {len(all_deals)} active 24-hour deals to {OUTPUT_FILE}")
    print(f"Saved deal memory to {MEMORY_FILE}")
    print(f"Saved next scan start index {new_state['next_start_index']} to {STATE_FILE}")

    if skipped:
        print(f"Skipped {skipped} products because their Keepa data format was incomplete or unexpected")
    if missing_images:
        print(f"{missing_images} deals did not include an image from Keepa or Amazon fallback")


if __name__ == "__main__":
    main()
