# On-demand Film Research scans

1. Start the local research service and open Film Research from the dashboard.
2. Set the funnel filters above the scan panel. Checked requirements and entered numeric limits are hard filters. A score never bypasses them. Blank limits are not requirements. For the original sales rule, enter **10** under Sales growth minimum %. For fewer than five videos, enter **4** under Total videos maximum. Main video and identified merchant video are separate signals.
3. Choose the ASIN count (default 100, maximum 1,000), batch size (default 10, maximum 100), and per-run token budget (default 100, maximum 1,000).
4. Click **Start new scan**. This explicitly authorizes the bounded token spend. Merely opening/filtering the page does not call Keepa.
5. The status panel polls GitHub. After checkpoint/result upload, click **Show scan matches** to show only products passing that scan's funnel. Other scanned products remain stored, with rejection reasons in the report. CSV export respects the selected scan and filters.
6. If paused, **Resume paused scan** keeps the same ASIN cohort and frozen funnel. Its token budget is a new per-run allowance. Once that batch finishes, **Start new scan** takes the next previously unscanned CC ASINs. A new ASIN count is not a promise of that many matches.

## Source and cost

The worker starts from uploaded CSVs in `data/creator-connections`, resolves latest campaign records and expands/deduplicates ASINs. CC activity and minimum commission are checked before Keepa where required. Products already in the durable cache or any prior on-demand cohort are skipped for new cohorts. ISBN-format Books are also screened before querying when Books is excluded; other categories and product-specific criteria require product data. Selection is deterministic ASIN order, not random Amazon discovery.

The GitHub workflow `Scan Film Research` uses the existing `KEEPA_API_KEY` Actions secret. The local Python service uses the existing Git credential manager (or server-side GH_TOKEN/GITHUB_TOKEN) to dispatch/read Actions. It never exposes credentials in browser code. The account needs repository Actions read/write permission. A sign-in/permission failure is shown in the panel; no key copying into the browser is required.

Requests use `/product` with `stats=90`, `history=1`, `videos=1`, `update=-1`. Keepa documents a basic cost of one token per product, with video metadata having no additional cost. `update=-1` uses Keepa's stored data; this can be old. No offers/rating/buybox add-ons or paid video refresh are requested. Missing ASINs may return no product and consume zero tokens. Source: [Keepa Product Request](https://keepa.com/api-docs/product.html).

Each attempted batch reserves its maximum basic token cost, including retries. Reported tokens consumed and remaining balance come from the API; missing usage remains Unknown. Exponential backoff honors refill/Retry-After information, then pauses if insufficient budget, balance or run time remains. The count and budget are upper bounds; low token balance, failed ASINs or an exhausted CC pool can produce fewer results. Tokens are not charged for matches only.

## State and recovery

The worker has a 15-minute processing window within a 30-minute GitHub job. CSV parsing, selection and results use indexed SQLite on the runner. The serialized `film-research-checkpoint` artifact survives individual runs, including normal pauses and scanner failures. Initial runs seed from the existing retired scanner checkpoint to preserve its cache. Missing/expired checkpoints stop the worker before spending; they do not silently reset the cache. Artifacts retain 90 days. GitHub Actions concurrency serializes scans; the local database prevents duplicate dispatches. An uncertain dispatch is checked by its unique ticket, never automatically dispatched again.

Completed products are committed to SQLite after each batch. Resumes only query pending cohort members. Failed/missing products are recorded separately. A network failure with an unknown response may require retrying a batch; reservations account for every attempt within that run. A workflow/checkpoint failure needs inspection before starting another paid run. Scan results and checkpoint artifacts may be visible to users with repository Actions access; personal shortlist notes are never uploaded.

Results return through a named artifact, not public commits. The local service imports raw product data and campaign records, preserving existing shortlist notes. Run status and membership persist in local `jobs` and `research_scan_results` tables. Keep this PC running to see status/results immediately; reopening it can retrieve a completed job later. No scheduled scans, outreach, or paid final video refresh are enabled.

The legacy Video Opportunities page remains removed. The scanner belongs to Film Research. Current tests mock Keepa and cover limits, >9% campaign eligibility, unknown growth, frozen resume settings, cached progress, retry budgets and the no-refresh request parameters. Live token spending is deliberately left to the user's Start scan action.
