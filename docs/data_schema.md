# Data Schema

## Canonical Output Schema

All 7 scrapers normalize to this schema before the processor writes the CSV.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `Platform` | string | Source job board | `SEEK`, `Indeed`, `Adzuna` |
| `Facility Name` | string | Employer / hiring organisation | `Medi-Corp` |
| `Job Title` | string | Position title | `Registered Nurse` |
| `Job Category` | string | One of 4 canonical categories | `Nursing` |
| `State` | string | AU state abbreviation | `NSW`, `VIC`, `Unknown` |
| `City` | string | Suburb or city | `Hawthorn` |
| `Date Posted` | string | ISO date `YYYY-MM-DD` | `2026-03-10` |
| `Job URL` | string | Direct link to listing | `https://www.seek.com.au/job/90673439` |

---

## Job Categories

All job listings are mapped to one of 4 canonical categories:

| Category | Keywords / Sources |
|----------|--------------------|
| `Nursing` | `nurse` keyword; SEEK nursing subclassifications |
| `Aged Care` | `aged care` keyword |
| `Disability Support` | `disability support`, `support worker` keywords |
| `Allied Health` | `allied health` keyword; SEEK allied health subclassifications |

### SEEK Category Map
SEEK returns a `subclassification.description` which is mapped to a canonical category:

| SEEK Subclassification | Canonical Category |
|------------------------|-------------------|
| `Nursing - General Medical & Surgical` | Nursing |
| `Nursing - Community, Maternal & Child Health` | Nursing |
| `Nursing - A&E, Critical Care & ICU` | Nursing |
| `Nursing - Aged Care` | Nursing |
| `Nursing - Theatre & Recovery` | Nursing |
| `Nursing - High Acuity` | Nursing |
| `Nursing - Psych, Forensic & Correctional Health` | Nursing |
| `Nursing - Management` | Nursing |
| `Nursing - Educators & Facilitators` | Nursing |
| `Nursing - Neonatal, Paediatric & Child Health` | Nursing |
| `Nursing - Midwifery, Neo-Natal, Mothers & Babies` | Nursing |
| `Aged Care` | Aged Care |
| `Aged & Disability Support` | Disability Support |
| `Disability Support` | Disability Support |
| `Allied Health` | Allied Health |
| `Physiotherapy, OTep & Rehabilitation` | Allied Health |
| `Psychology, Counselling & Social Work` | Allied Health |
| `Medical Imaging` | Allied Health |
| `Occupational Therapy` | Allied Health |
| `Speech Pathology` | Allied Health |
| `Pharmacy` | Allied Health |
| `Chiropractic & Osteopathic` | Allied Health |
| `Optical` | Allied Health |
| `Dietetics & Nutrition` | Allied Health |

---

## State Standardisation

`DataProcessor.extract_state()` applies a word-boundary regex (`\b{key}\b`) against the lowercased location string:

| Input | Output |
|-------|--------|
| `new south wales`, `nsw` | `NSW` |
| `victoria`, `vic` | `VIC` |
| `queensland`, `qld` | `QLD` |
| `western australia`, `wa` | `WA` |
| `south australia`, `sa` | `SA` |
| `tasmania`, `tas` | `TAS` |
| `australian capital territory`, `act` | `ACT` |
| `northern territory`, `nt` | `NT` |
| anything else | `Unknown` |

### City → State Fallback
If `extract_state()` returns `Unknown` but a city name is present, `city_to_state()` checks a curated map of ~60 common Australian cities/suburbs:

```python
CITY_STATE_MAP = {
    'sydney': 'NSW', 'newcastle': 'NSW', 'parramatta': 'NSW', ...
    'melbourne': 'VIC', 'geelong': 'VIC', 'ballarat': 'VIC', ...
    'brisbane': 'QLD', 'gold coast': 'QLD', 'townsville': 'QLD', ...
    'perth': 'WA', 'fremantle': 'WA', 'bunbury': 'WA', ...
    'adelaide': 'SA', 'darwin': 'NT', 'hobart': 'TAS', 'canberra': 'ACT', ...
}
```

This recovers state for EthicalJobs, Jora, and Adzuna records where the API only returns a suburb name.

---

## Deduplication Strategy

Applied in order by `DataProcessor.run()` after loading all raw dumps.

### Pass 1: URL Deduplication
```python
df['_url_key'] = df['Job URL'].apply(lambda u: re.sub(r'\?.*$', '', str(u)))
df = df.drop_duplicates(subset=['_url_key'])
```
Query params stripped first (e.g. `?keywords=nurse`) so the same job scraped under different keywords deduplicates correctly.

### Pass 2: Composite Key Deduplication
```python
df['_composite'] = (df['Facility Name'] + '_' + df['Job Title'] + '_' + df['State']).str.lower()
df = df.drop_duplicates(subset=['_composite'])
```
Catches the same job cross-posted on multiple platforms. Case-insensitive. Temporary columns dropped before CSV export.

### Pass 3: 7-Day Rolling Window
```python
cutoff = datetime.now() - timedelta(days=self.days_window)   # default: 7
df = df[pd.to_datetime(df['Date Posted'], errors='coerce') >= cutoff]
```
Drops jobs older than 7 days. Configurable via `DataProcessor(days_window=N)`.

---

## EthicalJobs Title Filter

EthicalJobs search returns broad results (not all healthcare). A keyword filter is applied at the processor stage — the job title must contain at least one of these terms to be kept:

```
nurse, nursing, midwi, aged care, disability, support worker, care worker,
care coordinator, allied health, physiother, occupational therap, speech,
patholog, dietit, nutrition, pharmacy, pharmacist, psycholog, counsell,
mental health, social work, case manager, medical, clinical, health worker,
health coordinator, health manager, doctor, physician, dental, optom,
radiol, care assistant, personal care, home care
```

---

## Raw Dump File Naming

```
raw_dumps/{platform}_raw_{keyword_or_identifier}_{YYYYMMDD_HHMMSS}.json
```

Examples:
```
seek_raw_nurse_p1_20260310_162501.json
seek_raw_aged_care_p3_20260310_162510.json
ethicaljobs_raw_nurse_p1_20260310_163529.json
jora_raw_disability_support_p2_20260310_164001.json
workforceaustralia_raw_nurse_20260310_164230.json
indeed_raw_support_worker_20260310_165001.json
careerone_raw_allied_health_20260310_165430.json
adzuna_raw_nurse_20260310_170001.json
```

### Raw Dump Format
```json
{
  "category": "Nursing",
  "data": [
    {
      /* canonical fields */
      "title": "Registered Nurse",
      "facility_name": "Medi-Corp",
      "state": "NSW",
      "city": "Sydney",
      "date_posted": "2026-03-10",
      "url": "https://...",
      /* PLUS all original API fields preserved via **job spread */
      "salary_min": 85000,
      "salary_max": 105000,
      "contract_time": "full_time",
      "description": "..."
    }
  ]
}
```

**Note**: SEEK saves the entire API response object (not just `data`), so raw dumps also include `totalCount`, `solMetadata`, etc. EthicalJobs saves the full RSC job object. All API-based scrapers (WorkforceAustralia, CareerOne, Adzuna) spread `**job` so no fields are discarded.

---

## Output File Naming

```
output/healthcare_jobs_report_{YYYYMMDD_HHMM}.csv
output/healthcare_jobs_summary_{YYYYMMDD_HHMM}.docx
```

---

## DOCX Report Structure

Generated by `src/report.py` from the latest output CSV:

1. **Title block** — report date, posting date range, total job count
2. **Section 1** — Jobs by Platform
3. **Section 2** — Jobs by Category
4. **Section 3** — Jobs by State
5. **Section 4** — Platform × State cross-tab
6. **Section 5** — Top 10 Hiring Facilities (all platforms)
7. **Section 6** — Top 5 Facilities per Category (Nursing / Aged Care / Disability Support / Allied Health)
