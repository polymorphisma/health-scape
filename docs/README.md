# Health-Scap — Documentation Index

This `docs/` directory is the single source of truth for the project.

## Files

| File | Purpose |
|------|---------|
| `README.md` | This file — index and navigation |
| `project_status.md` | Milestone tracker — what's done, what's left |
| `architecture.md` | System design, data flow, class hierarchy, design decisions |
| `api_reference.md` | Endpoint details, headers, response schemas for all 7 platforms |
| `data_schema.md` | Canonical output schema, field mapping, dedup strategy |
| `known_issues.md` | Resolved issues, workarounds, open observations |
| `case_study.md` | Client project case study — for portfolio and LinkedIn |

## Project Summary

**Goal**: Automated ETL pipeline that scrapes Australian healthcare job postings from 7 job boards weekly, deduplicates, filters to the last 7 days, exports a clean CSV, and generates a formatted DOCX summary report.

**Stack**: Python 3, `requests`, `BeautifulSoup`, `pandas`, `tenacity`, `python-docx`

**Platforms scraped**: SEEK · EthicalJobs · Jora · Workforce Australia · Indeed AU · CareerOne · Adzuna AU

**Output**:
- `output/healthcare_jobs_report_YYYYMMDD_HHMM.csv` — deduplicated job listings
- `output/healthcare_jobs_summary_YYYYMMDD_HHMM.docx` — weekly summary report

**Run**: `python -m src.main` from project root

## Quick Status

| Component | Status |
|-----------|--------|
| SEEK scraper | ✅ Working |
| EthicalJobs scraper | ✅ Working |
| Jora scraper | ✅ Working |
| Workforce Australia scraper | ✅ Working |
| Indeed AU scraper | ✅ Working |
| CareerOne scraper | ✅ Working |
| Adzuna AU scraper | ✅ Working |
| DataProcessor (ETL) | ✅ Working |
| Weekly DOCX report | ✅ Working |
| Cron automation | ✅ Configured (`run.sh`) |
| Documentation | ✅ Complete |
