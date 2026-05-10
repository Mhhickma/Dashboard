# Keepa Price Dashboard

A personal Amazon deal dashboard that scans ASINs with Keepa, keeps recent price drops active for 24 hours, and displays clickable deal cards in a static web page.

## What It Does

- Reads ASINs from a Google Sheet CSV when `ASIN_CSV_URL` is configured, otherwise from `asins.csv`
- Scans the ASIN list in rotating windows so large lists can be checked over multiple runs
- Uses Keepa pricing stats to find products below their recent average price
- Keeps active deals in `data/deals_memory.json` until their 24-hour TTL expires
- Writes dashboard data to `data/deals.json`
- Tracks the next scan position in `data/scan_state.json`
- Displays searchable, sortable deal cards in `index.html`

## Repository Layout

- `fetch_keepa.py` - Keepa scanner, deal detection, memory cleanup, and scan-state rotation
- `index.html` - Static dashboard page
- `app.js` - Dashboard filtering, sorting, posting helpers, hide/remove actions, and image fallbacks
- `styles.css` - Dashboard styling
- `asins.csv` - Local fallback ASIN list
- `data/deals.json` - Current dashboard data
- `data/deals_memory.json` - 24-hour active deal memory
- `data/scan_state.json` - Rotating scan position
- `.github/workflows/keepa-rotating-scan.yml` - Manual/external-trigger scanner workflow

## Required Setup

Do not put API keys directly in the code.

Add this GitHub Actions secret:

- `KEEPA_API_KEY` - your Keepa API key

Optional GitHub Actions secrets:

- `AMAZON_TAG` - your Amazon affiliate tag, such as `simplewoodsho-20`
- `ASIN_CSV_URL` - published CSV URL for the Google Sheet ASIN source

If `ASIN_CSV_URL` is not set, the scanner uses `asins.csv` in this repository.

## How The Scan Runs

The active workflow is `Keepa Rotating Price Scan` in `.github/workflows/keepa-rotating-scan.yml`.

It is intentionally configured with `workflow_dispatch` only. That means it can be started manually from GitHub Actions or triggered by an external scheduler such as cron-job.org. The workflow comments currently expect an external trigger every 15 minutes.

Each run:

1. Installs Python and `requests`.
2. Runs `python fetch_keepa.py`.
3. Updates `data/deals.json`, `data/deals_memory.json`, and `data/scan_state.json`.
4. Commits those data changes back to `main` when anything changed.

## Daily Scan Coverage

With a 15-minute external trigger, the workflow can run 96 times per day.

The current `SCAN_LIMIT` is `80`, which covers up to 7,680 ASINs per day. That is intended to scan the current list of about 7,407 ASINs once per day, with a small buffer for growth.

## Keepa Token Use

The current settings are designed for a Keepa refill rate of 25 tokens per minute.

Each scheduled run scans 80 ASINs, split into batches of 25 with a 60-second delay between batches. That keeps requests paced near the token refill rate while still averaging only about 5.3 ASINs per minute across the full day.

## Current Scan Settings

The workflow currently sets:

- `SCAN_LIMIT`: `80`
- `KEEPA_BATCH_SIZE`: `25`
- `KEEPA_REQUEST_DELAY_SECONDS`: `60`
- `KEEPA_RATE_LIMIT_WAIT_SECONDS`: `70`
- `KEEPA_MAX_RETRIES`: `5`
- `DEAL_TTL_HOURS`: `24`

The scanner defaults to a 5 percent minimum drop and Amazon US unless those values are changed with environment variables.

## Local Testing

```bash
pip install requests
export KEEPA_API_KEY="your_key_here"
export AMAZON_TAG="simplewoodsho-20"
python fetch_keepa.py
```

Then open `index.html` in your browser.

On Windows PowerShell, set temporary environment variables like this:

```powershell
$env:KEEPA_API_KEY="your_key_here"
$env:AMAZON_TAG="simplewoodsho-20"
python fetch_keepa.py
```

## Notes

The `data/*.json` files are committed on purpose so the static dashboard can load the latest generated deal data without a separate backend.
