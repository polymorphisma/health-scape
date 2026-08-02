# Project Status

Last updated: 2026-03-10

## Overall: Milestone 1 POC — ~70% Complete

---

## Completed

### Infrastructure
- [x] Directory structure: `src/`, `raw_dumps/`, `output/`, `logs/`
- [x] `requirements.txt` with pinned deps (`requests==2.31.0`, `pandas==2.2.1`, `tenacity==8.2.3`)
- [x] `src/base_scraper.py` — `JobScraper` base class with retry logic, logging, raw dump saving

### SEEK Scraper (`src/scrapers/seek.py`)
- [x] Reverse-engineered SEEK JSON API (`/api/jobsearch/v5/search`)
- [x] Pagination (up to 5 pages per keyword, controlled by `max_pages`)
- [x] Confirmed working — raw dumps exist for "nurse" (5 pages) and "support worker" (5 pages)
- [x] Each page has 20 jobs; total available: ~8,191 (nurse), ~14,856 (support worker)

### EthicalJobs Scraper (`src/scrapers/ethicaljobs.py`)
- [x] Rebuilt to parse Next.js RSC (`__next_f`) payload — structured JSON, no HTML parsing
- [x] Keyword-based search; category inferred from keyword (`nurse`→Nursing, `aged care`→Aged Care, etc.)
- [x] Proper pagination using `total` field from RSC (30 jobs/page)
- [x] State from `locations[0].name` via `LOCATION_STATE_MAP` (e.g. "Regional NT"→NT, "Sydney"→NSW)
- [x] City from `locations[0].locality` (e.g. "Campbelltown", "Malmsbury")
- [x] Job URL built from slug: `https://www.ethicaljobs.com.au/members/{slug}`
- [x] Confirmed: nurse=45 jobs/2 pages, aged care=189 jobs/5 pages

### Data Processor (`src/processor.py`)
- [x] Loads all `raw_dumps/` JSON files
- [x] Maps SEEK schema → canonical output columns
- [x] Maps EthicalJobs schema → canonical output columns
- [x] State standardization (NSW, VIC, QLD, WA, SA, TAS, ACT, NT)
- [x] Primary deduplication on `Job URL`
- [x] Secondary deduplication on `Facility Name + Job Title + State` composite (lowercased)
- [x] Exports to `output/healthcare_jobs_report_YYYYMMDD_HHMM.csv`

---

## Milestone 2 — In Progress

### 1. Weekly Window Filter (processor)
- [ ] Add 7-day rolling cutoff in `DataProcessor.run()` — drop any job where `Date Posted < today - 7 days`
- [ ] Make cutoff configurable (default 7, override via env var or arg)

### 2. Fix "Unknown" Fields (processor)
- [ ] City → State fallback: if state is "Unknown" but city is known, look up via city→state map
- [ ] Facility Name: strip whitespace/encoding artifacts (e.g. `Each ` trailing space already seen)

### 3. EthicalJobs Title Validation (scraper)
- [ ] After enrichment, filter out jobs where title contains none of the healthcare indicator keywords
- [ ] Keyword list: nurse, care, health, disability, support, allied, medical, aged, therapy, clinical, welfare

### 4. Additional Job Boards (4–6 more)
- [x] Jora (`src/scrapers/jora.py`) — COMPLETE
  - Listing page HTML parsing (div.job-card), no description API needed
  - Pagination via `/{keyword}-jobs?p=N` (slug URL + page param)
  - Relative date parsing: "3h ago" / "2d ago" → ISO date
  - Location parsing: "Brisbane QLD" → city + state
  - 36 nurse jobs scraped, all 7 fields, state distribution confirmed
- [x] WorkforceAustralia (`src/scrapers/workforceaustralia.py`) — COMPLETE
  - Clean JSON API at `/api/v1/global/vacancies/` — no auth required
  - Pagination via `skip` param (20 results/page), up to 5 pages/keyword
  - Fields: title, employerName, suburb (title-cased), state, creationDate, vacancyId
  - Job URL: `https://www.workforceaustralia.gov.au/individuals/jobs/{vacancyId}`
  - 100 nurse jobs scraped, all 7 fields confirmed
- [x] Indeed AU (`src/scrapers/indeed.py`) — COMPLETE
  - Internal GraphQL API at `apis.indeed.com/graphql` (public mobile app key)
  - `indeed-co: AU`, cursor-based pagination, 100 results/page × 5 pages = 500/keyword
  - Fields: title, employer.name, location.city, location.admin1Code (state), datePublished→ISO
  - Job URL: `https://au.indeed.com/viewjob?jk={key}`
  - 500 nurse jobs confirmed
- [ ] Skipped: HealthcareLink (auth required), QLD Health (JS rendered), HealthKite (placeholder site)
- [x] CareerOne (`src/scrapers/careerone.py`) — COMPLETE
  - REST API at `/api/v1/search-job?url=/nurse-jobs/in-australia`
  - Fresh session via `/csrf-cookie` (no login, no cf_clearance needed)
  - Pagination via `page=N`, 20 results/page × 5 pages = 100/keyword
  - Fields: job_title, company_name, location_state_code (clean), location_level_1_label (city), activates_at (date), URL slug
  - 100 nurse jobs confirmed
- [x] Adzuna AU (`src/scrapers/adzuna.py`) — COMPLETE
  - Official developer REST API (`api.adzuna.com/v1/api/jobs/au/search/{page}`)
  - `app_id` + `app_key` auth (free tier), 50 results/page × 5 pages = 250/keyword
  - Fields: title, company.display_name, location.area[1]→state, location.area[-1]→city, created[:10]→date, redirect_url
  - State extracted from full name in location.area[1] via STATE_NAME_MAP
  - REST API at `/api/v1/search-job?url=/nurse-jobs/in-australia`
  - Fresh session via `/csrf-cookie` (no login, no cf_clearance needed)
  - Pagination via `page=N`, 20 results/page × 5 pages = 100/keyword
  - Fields: job_title, company_name, location_state_code (clean), location_level_1_label (city), activates_at (date), URL slug
  - 100 nurse jobs confirmed

### 5. Weekly Summary Report
- [x] `src/report.py` — COMPLETE (`python-docx==1.1.2`)
  - Reads latest output CSV automatically
  - Sections: jobs by platform, by category, by state, platform×state cross-tab, top 10 facilities, top 5 per category
  - Styled tables (alternating row shading, blue headers)
  - Exported to `output/healthcare_jobs_summary_YYYYMMDD_HHMM.docx`
  - Wired into `main.py` as final step (step 10)

### 6. Documentation
- [x] Root `README.md` — VPS setup, venv, cron config, first run instructions, troubleshooting

---

## Milestone 1 — Complete ✓
- SEEK scraper + EthicalJobs scraper working
- 784 deduplicated records, all 7 required fields
- Real posting dates from detail pages (EthicalJobs)
- SEEK categories mapped to client's 4 canonical categories
- `main.py` + `run.sh` complete

---

## Test Files (Exploratory — not production code)
These were used during development/debugging and are not part of the pipeline:

| File | Purpose |
|------|---------|
| `src/test_api_seek.py` | Early SEEK API exploration |
| `src/test_cloudscraper.py` | Tested cloudscraper library (not adopted) |
| `src/test_ethicaljobs.py` | First EthicalJobs HTML scraping attempt |
| `src/test_ethicaljobs2.py` | Second attempt |
| `src/test_ethicaljobs3.py` | Third attempt — confirmed H2-based job card extraction |
| `src/test_ethicaljobs_detail.py` | First detail page exploration |
| `src/test_ethicaljobs_detail2.py` | Explored `dt/dd` metadata structure |
| `src/test_ethicaljobs_detail3.py` | Searched for Location/Sector text blocks on detail page |
