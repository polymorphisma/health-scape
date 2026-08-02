# Architecture

## Directory Structure

```
health-scap/
├── docs/                            # Source of truth (this directory)
├── src/
│   ├── main.py                      # Pipeline orchestrator (runs all scrapers + processor + report)
│   ├── base_scraper.py              # Abstract JobScraper base class
│   ├── processor.py                 # Pandas ETL pipeline (load → dedup → window → CSV)
│   ├── report.py                    # Weekly DOCX summary report generator
│   └── scrapers/
│       ├── seek.py                  # SEEK JSON API scraper
│       ├── ethicaljobs.py           # EthicalJobs Next.js RSC payload scraper
│       ├── jora.py                  # Jora HTML listing scraper
│       ├── workforceaustralia.py    # Workforce Australia JSON API scraper
│       ├── indeed.py                # Indeed AU GraphQL API scraper
│       ├── careerone.py             # CareerOne REST API scraper
│       └── adzuna.py                # Adzuna AU developer API scraper
├── raw_dumps/                       # Per-scraper JSON dumps (one file per keyword per run)
├── output/                          # Final CSV + DOCX reports
├── logs/                            # Per-platform log files (daily rotation)
├── requirements.txt
├── run.sh                           # Cron wrapper (activates venv, runs pipeline)
└── README.md                        # Setup and deployment guide
```

---

## Data Flow

```
[SEEK API]               ──→  SeekScraper            ──→  raw_dumps/seek_raw_*.json
[EthicalJobs RSC]        ──→  EthicalJobsScraper      ──→  raw_dumps/ethicaljobs_raw_*.json
[Jora HTML]              ──→  JoraScraper             ──→  raw_dumps/jora_raw_*.json
[WorkforceAustralia API] ──→  WorkforceAustraliaScraper ──→ raw_dumps/workforceaustralia_raw_*.json
[Indeed GraphQL]         ──→  IndeedScraper           ──→  raw_dumps/indeed_raw_*.json
[CareerOne REST API]     ──→  CareerOneScraper        ──→  raw_dumps/careerone_raw_*.json
[Adzuna API]             ──→  AdzunaScraper           ──→  raw_dumps/adzuna_raw_*.json
                                                                       │
                                                                       ▼
                                                             DataProcessor.run()
                                                                       │
                                                    ┌──────────────────────────────────┐
                                                    │ 1. Load all raw_dumps/ JSONs     │
                                                    │ 2. Normalize to canonical schema  │
                                                    │ 3. URL dedup (strip query params) │
                                                    │ 4. Composite dedup (Fac+Title+St) │
                                                    │ 5. 7-day rolling window filter    │
                                                    │ 6. Export CSV                     │
                                                    └──────────────────────────────────┘
                                                                       │
                                                    ┌──────────────────────────────────┐
                                                    │ generate_report()                 │
                                                    │ Reads latest CSV                  │
                                                    │ Writes DOCX summary               │
                                                    └──────────────────────────────────┘
                                                                       │
                                              output/healthcare_jobs_report_YYYYMMDD_HHMM.csv
                                              output/healthcare_jobs_summary_YYYYMMDD_HHMM.docx
```

---

## Class Hierarchy

```
JobScraper (base_scraper.py)
├── __init__(platform_name, base_dir)
│     → sets up requests.Session, logging, directory paths
├── _setup_logging()
│     → per-platform daily log file + console handler
├── save_raw_data(data, identifier)
│     → writes JSON to raw_dumps/{platform}_raw_{identifier}_{timestamp}.json
├── _make_request(method, url, **kwargs)
│     → tenacity retry: 3 attempts, exponential backoff 2–10s
└── run(search_terms)
      → abstract; must be overridden by each scraper

SeekScraper(JobScraper)
└── run()  → paginates SEEK JSON API; saves full API response per page

EthicalJobsScraper(JobScraper)
├── run()                → fetches search results RSC, enriches with detail pages
├── _parse_listing_rsc() → extracts jobs from Next.js __next_f RSC payload
├── _enrich_with_detail()→ fetches each job's detail page for approvedAt date
├── _extract_detail_fields() → parses detail page RSC for full job object
└── _normalize()         → spreads **all** raw RSC fields + adds helpers

JoraScraper(JobScraper)
├── run()            → fetches HTML pages by keyword slug + ?p=N
├── _parse_listing() → finds div.job-card elements via BeautifulSoup
├── _extract_card()  → extracts fields from each card
└── _parse_relative_date() → converts "3d ago" → ISO date

WorkforceAustraliaScraper(JobScraper)
└── run()  → paginates JSON API via skip param; spreads full raw job + canonical fields

IndeedScraper(JobScraper)
├── run()          → cursor-based pagination via GraphQL
└── _fetch_page()  → POST GraphQL query, parse results + nextCursor

CareerOneScraper(JobScraper)
├── run()                  → fresh session on each call, then paginates REST API
├── _establish_session()   → GET /csrf-cookie → sets seekerapi_session + XSRF-TOKEN
└── _normalize()           → spreads full raw job + canonical fields

AdzunaScraper(JobScraper)
└── run()  → page-based pagination; spreads full raw job + canonical fields

DataProcessor (processor.py)
├── run()                          → full ETL pipeline
├── process_seek_file()            → SEEK JSON → canonical records
├── process_ethicaljobs_file()     → EthicalJobs JSON → canonical records
├── process_jora_file()            → Jora JSON → canonical records
├── process_workforceaustralia_file() → WFA JSON → canonical records
├── process_indeed_file()          → Indeed JSON → canonical records
├── process_careerone_file()       → CareerOne JSON → canonical records
├── process_adzuna_file()          → Adzuna JSON → canonical records
├── extract_state()                → location string → AU state abbreviation
└── city_to_state()                → city name lookup fallback → state
```

---

## Key Design Decisions

### 1. Raw Dump Before Processing
Every scraper saves raw data to `raw_dumps/` before any normalization. The processor is fully idempotent — you can re-process without re-scraping. All API scrapers preserve the full original response (`**job` spread) so no data is discarded at scrape time.

### 2. Platform Isolation + Fault Tolerance
Each scraper runs inside its own `try/except` in `main.py`. A failure on one platform (blocked, API change, network error) doesn't abort the rest of the pipeline. Errors are collected and reported at exit.

### 3. Retry Logic (tenacity)
`_make_request()` retries up to 3 times with exponential backoff (2–10s). This handles transient network errors, rate limiting, and brief API downtime without manual intervention.

### 4. Two-Pass Deduplication
- **Pass 1 (URL)**: strip query params, drop exact URL duplicates (same job scraped under multiple keywords or across multiple runs)
- **Pass 2 (composite)**: `Facility Name + Job Title + State` (lowercased) — catches the same job cross-posted on multiple platforms

### 5. 7-Day Rolling Window
Applied after dedup. Jobs with `Date Posted < today - 7 days` are dropped. Configurable via `days_window` arg to `DataProcessor`. Keeps the CSV relevant for weekly delivery.

### 6. City → State Fallback
If state extraction fails (returns "Unknown"), the processor checks the city name against a curated `CITY_STATE_MAP` covering ~60 common Australian cities. This recovers state for EthicalJobs and Jora records where only a suburb name is available.

### 7. Session Management
- **CareerOne**: `_establish_session()` is called at the top of every `run()` invocation — fresh CSRF token and session cookie obtained on every weekly run, no expiry risk.
- **Indeed**: Public mobile app API key in header — not a session, does not expire.
- **All others**: No auth required.

### 8. File Naming Convention
```
raw_dumps/{platform}_raw_{keyword}_{YYYYMMDD_HHMMSS}.json
output/healthcare_jobs_report_{YYYYMMDD_HHMM}.csv
output/healthcare_jobs_summary_{YYYYMMDD_HHMM}.docx
logs/{platform}_{YYYYMMDD}.log
```
