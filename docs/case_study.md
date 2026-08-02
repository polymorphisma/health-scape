# Case Study: Automated Healthcare Job Intelligence Pipeline

**Project**: Health-Scap
**Domain**: Healthcare Recruitment / Data Engineering
**Stack**: Python · requests · BeautifulSoup · pandas · python-docx · tenacity
**Deliverable**: Fully automated weekly scraping pipeline covering 7 Australian job boards

---

## The Problem

A healthcare recruitment client needed weekly visibility into job postings across the Australian market — specifically roles in nursing, aged care, disability support, and allied health. Their existing process was fully manual: staff visited each job board, copied listings into a spreadsheet, deduplicated by hand, and assembled a summary report. This took several hours every week and was prone to missed listings and inconsistent formatting.

They needed a system that would:
- Scrape 6–8 publicly accessible job boards automatically
- Extract structured data for every healthcare role found
- Remove duplicates (same job posted on multiple platforms)
- Standardise location data to state abbreviations
- Keep only listings from the past 7 days
- Export a clean CSV and a formatted summary report
- Run automatically every week without manual intervention

---

## The Solution

A modular Python ETL pipeline with a dedicated scraper per platform, a shared processing layer, and automated weekly execution via cron.

### Architecture Overview

```
7 scrapers → raw_dumps/ → DataProcessor → CSV + DOCX report
```

Each scraper runs independently, saves its raw data to disk, and exits. The processor loads all raw dumps, applies normalisation and deduplication, and exports the final outputs. If any scraper fails, the rest of the pipeline continues.

### Platforms Integrated

| Platform | Integration Method |
|----------|--------------------|
| SEEK | Reverse-engineered JSON search API (`/api/jobsearch/v5/search`) |
| EthicalJobs | Next.js RSC payload parsing (`__next_f` chunks) + detail page enrichment |
| Jora | HTML scraping (`div.job-card` elements via BeautifulSoup) |
| Workforce Australia | Public government JSON API (no auth) |
| Indeed AU | Internal GraphQL API with public mobile app key |
| CareerOne | REST JSON API with CSRF session (auto-refreshed per run) |
| Adzuna AU | Official developer API (free tier) |

---

## Technical Challenges & How They Were Solved

### 1. EthicalJobs — No Public API, Complex Frontend

EthicalJobs is built on Next.js and renders all content server-side. Initial attempts to parse HTML structure (`<h2>` tags, sibling `<div>` elements) yielded partial data with no dates and unreliable locations.

**Solution**: Discovered that Next.js RSC (React Server Components) embeds the full structured data payload inside inline `<script>` tags as `self.__next_f.push([1, "..."])` chunks. By concatenating and decoding these chunks, the complete job object — including `organisationName`, `locations`, `slug`, and `expiresAt` — could be extracted as clean JSON without any HTML parsing. The `approvedAt` date (actual posting date) was only available on the individual job detail page, so an additional request was made per job with a 0.5s delay.

**Key insight**: `json.JSONDecoder().raw_decode()` was required rather than `json.loads()` because the RSC payload embeds raw HTML (including newlines and special characters) inside JSON string values, which breaks standard line-by-line JSON parsing.

### 2. Jora — Page 2 Returned 403

The initial pagination attempt used the `/j` endpoint (`au.jora.com/j?q=...&p=2`), which requires a cryptographic `tk` token generated on the listing page and is protected by Cloudflare.

**Solution**: Pages 2+ work identically to page 1 by appending `&p=N` to the same keyword slug URL (`au.jora.com/{Keyword}-jobs?p=N`). No token required.

**Secondary bug**: `data-job-id` attributes appeared on `<button>` (save job) elements, not on card containers. Fixed to `div.job-card` class selector.

**Bonus quirk**: Jora duplicates the title text inside the link's inner DOM (e.g., `"Registered Nurse Registered Nurse"`). Detected by checking `words[:half] == words[half:]` and keeping only the first half.

### 3. CareerOne — JavaScript-Rendered SPA

CareerOne is a Nuxt.js (Vue SSR) application. The initial HTML response contained no job data — all content was rendered client-side.

**Solution**: Found a clean REST API endpoint (`/api/v1/search-job`) by inspecting network traffic. The API requires a session cookie (`seekerapi_session`) and CSRF token, but these are issued automatically by a single GET to `/csrf-cookie` — no login credentials required. The session is refreshed on every pipeline run, so there is no expiry risk across weekly executions.

### 4. Indeed AU — Authentication Header Case Sensitivity

The initial `indeed-co: au` header returned HTTP 400: "Request country au does not correspond to a valid Indeed site."

**Solution**: The header value must be uppercase: `indeed-co: AU`. One character difference, 30 minutes of debugging.

### 5. Cross-Platform Deduplication

The same job frequently appears on multiple platforms simultaneously. A simple URL dedup was insufficient because different platforms use completely different URL formats for the same listing.

**Solution**: Two-pass deduplication:
1. URL dedup (query params stripped first — `?keywords=nurse` artifacts removed)
2. Composite key: `Facility Name + Job Title + State` (lowercased) — catches the same job cross-posted across platforms

### 6. Inconsistent Location Data

Each platform exposes location differently:
- SEEK: `"Hawthorn, Melbourne VIC"` (city + state in one string)
- EthicalJobs: `"Regional NT"`, `"Sydney"` (location names, not state codes)
- Jora: `"Brisbane QLD"` (city + state abbreviation)
- Workforce Australia: `suburb: "SYDNEY"` + `state: "NSW"` (separate fields, suburb ALL CAPS)
- Indeed: `location.admin1Code` (clean state code) + `location.city`
- CareerOne: `location_state_code` (clean) + `location_level_1_label` (city)
- Adzuna: `location.area` array — `["Australia", "Queensland", "Brisbane Region", "Brisbane", "South Brisbane"]`

**Solution**: Each scraper handles its own location normalisation. The processor applies a shared `extract_state()` regex function, with a `city_to_state()` fallback lookup (~60 common Australian cities) for platforms that only provide suburb names.

### 7. Raw Data Preservation

Early versions of the pipeline discarded the full API response in favour of normalized fields only. This meant that potentially useful fields (salary ranges, employment type, contract type, job descriptions) could not be recovered later without re-scraping.

**Solution**: All API-based scrapers use `{**job, ...canonical_fields}` — spreading the full original API job object and then applying canonical field overrides on top. Raw dumps contain the complete API payload for every job. SEEK saves the full API response object per page. EthicalJobs saves the complete RSC job object including all detail page fields.

---

## Results

| Metric | Value |
|--------|-------|
| Platforms integrated | 7 |
| Job categories covered | 4 (Nursing, Aged Care, Disability Support, Allied Health) |
| Search keywords | 5 per platform |
| Jobs collected per run (estimate) | 2,000–4,000 before dedup |
| Deduplication rate | ~30–40% (significant cross-posting across platforms) |
| Weekly window filter | 7 days (configurable) |
| Pipeline runtime | ~15–20 minutes (EthicalJobs detail page requests dominate) |
| Output formats | CSV + DOCX |
| Manual effort required | Zero — fully automated via cron |

---

## Deliverables

- `src/scrapers/` — 7 independent scraper modules
- `src/processor.py` — ETL pipeline with dedup, window filter, CSV export
- `src/report.py` — DOCX weekly summary report (platform/category/state breakdown, top facilities)
- `src/main.py` — Orchestrator with per-scraper fault isolation
- `run.sh` — Cron wrapper
- `requirements.txt` — Pinned dependencies
- `README.md` — Full VPS setup, cron config, troubleshooting guide
- `docs/` — Architecture, API reference, data schema, known issues

---

## Key Technical Decisions

**Python over Scrapy**: The client's target sites were a mix of JSON APIs, GraphQL endpoints, and HTML pages. Scrapy's Spider model adds overhead for API-based sources and doesn't simplify the GraphQL/RSC parsing work. Plain `requests` with a shared base class gave cleaner per-platform control.

**Raw dump before processing**: Every scraper writes to disk before any processing. The processor is fully idempotent — you can re-process, change normalisation logic, or add new fields without re-scraping. This separation also makes debugging straightforward: inspect the raw dump to verify what the scraper saw.

**Fault isolation**: Each scraper runs in its own `try/except`. A blocked platform doesn't abort the pipeline — the other 6 scrapers continue, errors are logged, and a non-zero exit code signals the cron log that something needs attention.

**Session safety**: The only session-dependent scraper (CareerOne) calls `_establish_session()` at the start of every `run()`. No session state persists between weekly executions, so there is no cookie-expiry failure mode.

---

## Platforms Evaluated But Excluded

| Platform | Reason |
|----------|--------|
| HealthcareLink | Requires authenticated login — no public session endpoint |
| QLD Health SmartJobs | Oracle Taleo — fully JS-rendered portal, all API calls return 404 without an active session |
| HealthKite | Placeholder site with no content (114-byte response) |

---

*All data scraped is publicly accessible job listings. No authentication credentials were bypassed, no paywalls were circumvented, and no personal data was collected.*
