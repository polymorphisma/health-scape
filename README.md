# Health-Scap

Australian healthcare job scraper and reporting pipeline.

Scrapes 7 job boards, deduplicates, applies a 7-day rolling window, exports a clean CSV, and generates a formatted DOCX summary report — all in one command.

---

## Quick Start

```bash
# 1. Clone / upload project to your server
cd /path/to/health-scap

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the full pipeline
python -m src.main
```

Outputs land in `output/`:
- `healthcare_jobs_report_YYYYMMDD_HHMM.csv` — deduplicated job listings
- `healthcare_jobs_summary_YYYYMMDD_HHMM.docx` — weekly summary report

---

## Project Structure

```
health-scap/
├── src/
│   ├── main.py                      # Pipeline orchestrator
│   ├── base_scraper.py              # JobScraper base class (retry, logging, raw dumps)
│   ├── processor.py                 # ETL: load → dedup → filter → CSV
│   ├── report.py                    # Weekly DOCX report generator
│   └── scrapers/
│       ├── seek.py                  # SEEK (JSON API)
│       ├── ethicaljobs.py           # EthicalJobs (Next.js RSC payload)
│       ├── jora.py                  # Jora (HTML scraping)
│       ├── workforceaustralia.py    # Workforce Australia (JSON API)
│       ├── indeed.py                # Indeed AU (GraphQL API)
│       ├── careerone.py             # CareerOne (REST API)
│       └── adzuna.py                # Adzuna AU (official developer API)
├── raw_dumps/                       # Raw scraper output (JSON, one file per keyword)
├── output/                          # Final CSV + DOCX reports
├── logs/                            # Per-day log files
├── docs/                            # Architecture, API reference, schema docs
├── requirements.txt
├── run.sh                           # Cron wrapper script
└── README.md                        # This file
```

---

## Job Boards

| Platform            | Method          | Jobs/keyword | Auth needed   |
|---------------------|-----------------|-------------|---------------|
| SEEK                | JSON API        | 100 (5 × 20) | None          |
| EthicalJobs         | Next.js RSC     | ~30–200      | None          |
| Jora                | HTML scraping   | ~50–100      | None          |
| Workforce Australia | JSON API        | 100 (5 × 20) | None          |
| Indeed AU           | GraphQL API     | 500 (5 × 100)| Public app key|
| CareerOne           | REST API        | 100 (5 × 20) | Session cookie|
| Adzuna AU           | Developer API   | 250 (5 × 50) | app_id/app_key|

---

## Search Keywords

Each scraper runs these keywords: `nurse`, `aged care`, `disability support`, `allied health`, `support worker`

Mapped to 4 canonical categories:

| Keyword            | Category           |
|--------------------|--------------------|
| nurse              | Nursing            |
| aged care          | Aged Care          |
| disability support | Disability Support |
| support worker     | Disability Support |
| allied health      | Allied Health      |

---

## Output Schema

Both the CSV and DOCX report use these 8 columns:

| Column        | Description                              |
|---------------|------------------------------------------|
| Platform      | Source job board                         |
| Facility Name | Employer / hiring organisation           |
| Job Title     | Raw job title                            |
| Job Category  | Nursing / Aged Care / Disability Support / Allied Health |
| State         | AU state abbreviation (NSW, VIC, …)      |
| City          | Suburb or city                           |
| Date Posted   | ISO date (YYYY-MM-DD)                    |
| Job URL       | Direct link to the job listing           |

---

## Deduplication

1. **URL dedup** — strip query params, drop duplicate URLs across all platforms
2. **Composite dedup** — drop `Facility Name + Job Title + State` duplicates (case-insensitive)
3. **7-day window** — drop jobs posted more than 7 days ago (configurable)

---

## VPS Setup

### Requirements

- Ubuntu 22.04+ (or any Linux with Python 3.10+)
- Python 3.10 or higher
- ~500 MB disk (raw dumps + output accumulate over time)

### First-time setup

```bash
# Install Python if needed
sudo apt update && sudo apt install python3 python3-venv python3-pip -y

# Clone or upload the project
cd ~
git clone <repo-url> health-scap   # or scp/rsync your files
cd health-scap

# Create venv and install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Test run
python -m src.main
```

### Cron Configuration

Run every Monday at 6 AM server time:

```bash
crontab -e
```

Add this line:

```
0 6 * * 1 /path/to/health-scap/run.sh >> /path/to/health-scap/logs/cron.log 2>&1
```

Replace `/path/to/health-scap` with the absolute path on your server (e.g. `/home/ubuntu/health-scap`).

To verify it's registered:

```bash
crontab -l
```

### Checking logs

```bash
# Latest processor log
ls -lt logs/ | head -5
tail -50 logs/processor_$(date +%Y%m%d).log

# Cron output
tail -100 logs/cron.log
```

---

## Manual Run

```bash
cd /path/to/health-scap
source venv/bin/activate
python -m src.main
```

Or use the wrapper (same as cron):

```bash
bash run.sh
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: src` | Running `python src/main.py` instead of `python -m src.main` | Use `python -m src.main` from project root |
| `No output CSV found` when running report standalone | Processor hasn't run yet | Run full pipeline first |
| 0 jobs after weekly window filter | `Date Posted` not parsing — check raw dump dates | Inspect `raw_dumps/` for that platform |
| Indeed returns 400 | `indeed-co` header must be uppercase `AU` | Already set in `src/scrapers/indeed.py` |
| CareerOne returns empty | Session cookie expired mid-run | `_establish_session()` refreshes automatically on each `run()` call |

---

## Dependencies

```
requests==2.31.0
pandas==2.2.1
tenacity==8.2.3
python-docx==1.1.2
```

Install: `pip install -r requirements.txt`
