# Local Film Research workspace

## Run on this PC

Double-click `start-research.cmd`, keep its terminal open, then open http://127.0.0.1:8765. Close the terminal to stop. No hosting subscription or Keepa credentials are needed for this saved-data workspace. It is not available from other devices. Notes are stored in `.research/research.sqlite`, excluded from Git. Back up that file while the service is stopped. It is not encrypted; Windows account and disk access controls protect it.

The page currently imports 425 saved scanned products from `data/influencer/page-*.json` and campaign detail files. These are research candidates, **not all qualified products**. The old Video Opportunities page and its scanner workflows have been retired. A research score never changes its hard filters.

Restart after updating the repository's saved scan files to import newer results. This does not synchronize GitHub automatically, run a scan, or refresh Keepa. Existing private shortlist records survive imports. The complete CC dataset remains in the existing import/checkpoint storage; the local feed initially contains only previously enriched ASINs.

For richer existing cached data, run `python research_server.py --checkpoint PATH_TO_EXISTING_SQLITE_CHECKPOINT`. This opens the source read-only, imports raw Keepa cache and matching campaigns, and reuses existing trend calculations. It uses the shared `research_keepa.py` normalizer and makes no network requests. Do not place checkpoint files in publicly served or tracked directories.

## Inspected architecture and integration

The existing frontend is static HTML, vanilla JavaScript and CSS, published on GitHub Pages. Python scanners run through GitHub Actions. Apps Script handles CC CSV uploads and commits chunks to the shared `data/creator-connections` folder. The price and video scanners share those uploads.

The existing pipeline's SQLite checkpoint uses `sources`, `campaigns`, `links`, `cache`, `selected`, `failures` and `finder_shortlists`. Its public output is paginated JSON plus ASIN campaign details. There was no general application backend or private notes database. Existing strict rules include active campaigns at least 10%, apparel/books exclusions, observed merchant video, fewer than five videos, and current monthly sold at least 110% of its 90-day average; BSR does not substitute for unavailable sales history.

Keepa's `KEEPA_API_KEY` stays in the existing GitHub Actions secret. Apps Script's GitHub credential stays in Script Properties. This service neither retrieves nor requires either credential. The retired video-specific Product Finder and batch scanner have been removed; no replacement paid scan is enabled here. Research browsing performs no Keepa requests.

The extension adds `research_server.py` (standard-library loopback HTTP service), `research_model.py` (normalization, provider contract and score), `research.html`, `research.js`, `research.css`, `research-config.json`, and the local launcher. It reuses existing saved data and calculations without replacing working pages or deployment.

## Local additive schema and routes

Schema migration 1 creates indexed `products`, `product_campaigns`, `shortlist`, `settings`, `target_brands`, `events`, and `jobs`. Product payloads retain base scan fields and optional raw cached products; campaign rows preserve their full source payload. Shortlist records are separate from imported products. Indexes cover ASIN, score, active CC/commission and category. Events record local workflow changes; no delivery integrations run. Jobs reserve a model for future refresh orchestration, not an active scheduler.

GET `/api/products` uses server-side filtering and pagination (50 default, 100 maximum). GET `/api/products/ASIN` returns details. GET `/api/export` respects the same filters and escapes spreadsheet formula prefixes. GET/POST `/api/settings` reads/saves scoring defaults. POST `/api/shortlist/ASIN` saves private workflow fields. Only four explicit page assets are served; arbitrary repository files are not exposed. Writes require a session CSRF token and same-origin checks; binding is loopback only.

## Scoring and filters

The new research feed defaults to active CC, commission **strictly greater than 9%**, apparel excluded and Books excluded (the user's previous preference). Lower commissions and inactive campaigns stay stored when present in the source; changing filters can reveal them. Preferences for merchant video, sales growth and low competition affect scores rather than mandatory exclusion. Numeric filters reject Unknown values.

Weights and thresholds are configurable in Settings. Initial documented component formulas, each capped at its weight:

| Component | Weight | Full points / calculation |
|---|---:|---|
| Sales volume | 30 | Monthly sold / 1,000 |
| Sales trend | 20 | Positive growth / 50% |
| Influencer competition | 20 | 0–3 observed classified influencer videos: full; 4–5: half; over 5: zero |
| Active CC commission | 15 | Commission / 30% |
| Merchant video | 10 | Observed true: full; false: zero |
| Earning potential | 5 | Estimated CC per sale / $20 |

Missing components receive no awarded points and remain explicitly Unknown. Coverage is the sum of component weights with available evidence; scores are not rescaled to pretend full coverage. The score is a research heuristic, not an earnings forecast. Estimated CC per sale is current price × commission / 100, rounded to cents; it excludes other commission programs and assumes eligibility.

Sales growth reuses `(current monthly sold / full 90-day time-weighted average - 1) × 100`; missing coverage remains Unknown. Monthly-sold values are Amazon purchase brackets/lower bounds. Labels: at least +30% accelerating, above +5% rising, ±5% stable, below -5% declining, at most -30% rapidly declining. BSR improvement is `(1 - current rank / historical average rank) × 100`; positive is improvement because lower rank is better. It remains diagnostic, not a substitute for sales growth. Saved calculation timestamps reflect the original scan, not a new observation.

## Source limits

Raw checkpoint import can expose Keepa statistics (price averages, BSR averages, rating/review counts), observed offers/variants and available images. The compact public feed does not retain all these fields, so they initially display Unknown. Offer/variant counts can be partial; these are observed counts, not guaranteed Amazon-wide totals. Price averages prefer Buy Box, then Amazon, then new-price tracks and may differ from the selected current price source.

`VideoProvider` provides a replaceable normalization interface. The Keepa adapter only counts usable observed `videos` metadata, deduplicates URLs, labels source/confidence and uses the shared extra-information update timestamp if available. `Main` does not establish seller/brand identity and prevents an exact influencer classification. Missing/failed metadata does not become zero. Finder's main-video filter does not provide per-product seller identity or exact influencer counts. An additional authorized provider returning video identities, creator classification, scope and timestamps is needed for dependable exact counts. No Amazon scraping was added.

## Phase status

Phase 1 provides the research feed, CC matching, configurable filters/scoring, saved Keepa enrichment, honest video interfaces, details, private shortlist and filtered CSV export. Low Competition and Trending are filtered views. Outreach, Film and Published views use local shortlist states; they do not send communications. Launch, Seasonal and Deals are explicitly marked future-provider sections; target brands and event/job tables prepare for later integration. Automatic refresh, launch discovery and alerts are not enabled.

Validation: offline unit tests cover commission boundaries, pagination, shortlist persistence, unknown video handling, score coverage, settings rollback and SQL parameterization; existing pipeline tests are retained. Browser verification checks the actual saved-data feed and detail panel. Local notes and databases must never be committed or deployed to Pages.

Retirement: the dedicated Video Opportunities page, CSS/JavaScript, scanner, Finder, checkpoint transfer helper, workflows, old documentation and page-specific tests were removed. Saved product pages and campaign details in data/influencer remain shared Film Research inputs. Creator Connection uploads, price scanning and private shortlist data are preserved.
