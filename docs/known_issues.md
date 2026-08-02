# Known Issues & Engineering Notes

## Resolved Issues

### ~~EJ-001: EthicalJobs State "Unknown"~~
- **Resolved**: EthicalJobs scraper now reads `locations[0].name` from RSC payload and maps it via `LOCATION_STATE_MAP` (e.g. `"Regional NT"` → `NT`, `"Sydney"` → `NSW`). City-state fallback in the processor also recovers state from suburb names.

### ~~EJ-002: EthicalJobs Date Posted Missing~~
- **Resolved**: Scraper now fetches each job's detail page and extracts `approvedAt` from the RSC payload. Falls back to parsing `"Job posted on: 3rd Feb 2026"` from HTML.

### ~~EJ-003: EthicalJobs Low Job Volume~~
- **Resolved**: Switched to keyword-based scraping (`nurse`, `aged care`, `disability support`, `allied health`). Nurse returns 45 jobs, aged care returns 189 jobs over 5 pages.

### ~~EJ-004: EthicalJobs URL Contains Search Keywords~~
- **Resolved**: Processor strips query params from all URLs before deduplication (`re.sub(r'\?.*$', '', url)`).

### ~~ORCH-001: main.py Empty~~
- **Resolved**: `main.py` fully wired — all 7 scrapers + processor + report in sequence with per-step error handling.

### ~~ORCH-002: run.sh Empty~~
- **Resolved**: `run.sh` activates venv and runs `python -m src.main` from the project root.

### ~~ORCH-003: run.sh Used Wrong Module Invocation~~
- **Resolved**: Changed `python src/main.py` to `python -m src.main` (required for relative imports within `src/` package).

### ~~Jora Page 2 Returned 403~~
- **Resolved**: The `/j` endpoint requires a `tk` token and is blocked by Cloudflare. Pages 2+ use the same slug URL (`/{Keyword}-jobs?p=N`) which works without a token.

### ~~Jora `data-job-id` Found 0 Jobs~~
- **Resolved**: `data-job-id` is on `<button>` (save) elements, not card containers. Fixed to `div.job-card`.

### ~~CareerOne Appeared JS-Rendered~~
- **Resolved**: Found clean REST API at `/api/v1/search-job`. Session established via `/csrf-cookie` — no login required, auto-sets `seekerapi_session`.

### ~~Indeed `indeed-co: 'au'` Returned 400~~
- **Resolved**: Header value must be uppercase: `indeed-co: AU`.

### ~~Raw Dumps Discarded API Fields~~
- **Resolved**: WorkforceAustralia, CareerOne, and Adzuna scrapers now spread `**job` in `_normalize()` before applying canonical field overrides. All original API fields are preserved in raw dumps.

---

## Platforms Evaluated But Skipped

| Platform | Reason Skipped |
|----------|----------------|
| HealthcareLink | Requires authenticated session (`PHPSESSID`) — no way to obtain without login |
| QLD Health (SmartJobs) | Oracle Taleo portal — fully JS-rendered, all API endpoints return 404 without a session |
| HealthKite | Placeholder site — 114-byte response redirecting to `/lander` with no content |

---

## Active Observations (Low Priority)

### OBS-001: Indeed API Key Is Hardcoded Public Key
- **Detail**: The API key `161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8` is extracted from the Indeed iOS app and is widely used in open-source scrapers (e.g. JobSpy). It is not a session token and does not expire, but Indeed could rotate it.
- **Mitigation**: If Indeed scraper starts returning `401`, update the key from the latest JobSpy release or extract fresh from an iOS network capture.
- **Risk**: Low — key has been stable across public usage for 2+ years.

### OBS-002: SEEK May Add Bot Protection
- **Detail**: SEEK API currently requires no auth and only a browser User-Agent. If SEEK adds Cloudflare or requires an auth token, the scraper will need updating.
- **Mitigation**: SEEK is the most important platform. Monitor for `403` or empty `data` arrays in logs.
- **Risk**: Low — no change observed since 2024.

### OBS-003: CareerOne API Is Nuxt.js / Shared With Adzuna Group
- **Detail**: CareerOne's backend (`seekerapi_session`) shares infrastructure with other Adzuna Group job boards. If the session cookie name or CSRF flow changes, `_establish_session()` will need updating.
- **Mitigation**: If scraper returns empty results, check whether `/csrf-cookie` still sets the same cookie names in a fresh browser session.

### OBS-004: Jora Rate Limiting at Scale
- **Detail**: Jora has 2s page delays. For 5 keywords × 5 pages = 25 requests per run. This is well within safe limits. If keywords are expanded significantly, consider increasing delay.

### OBS-005: EthicalJobs Detail Page Requests
- **Detail**: EthicalJobs fetches a detail page per job (0.5s delay) to get `approvedAt`. For 5 keywords × 5 pages × 30 jobs = up to 750 detail page requests per run. This is the slowest part of the pipeline (~6–7 minutes for EthicalJobs alone).
- **Mitigation**: Detail page fetching is wrapped in `try/except` — failure on individual pages doesn't abort the scrape. Scrape date is used as fallback.

---

## Open Questions (For Client)

1. **Output delivery**: Should the CSV and DOCX be emailed after each run, or saved locally for manual collection?
2. **max_pages scaling**: Current cap is 5 pages per keyword per platform. SEEK has 8,191 nurse results — we retrieve ~100. Should this be increased for production?
3. **Additional keywords**: Are there other role types to add beyond the current 5 (`nurse`, `aged care`, `disability support`, `allied health`, `support worker`)?
4. **Raw dump retention**: Raw dumps accumulate over time. Should old dumps be pruned automatically (e.g., keep last 4 weeks only)?
