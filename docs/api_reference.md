# API Reference

All 7 platforms — endpoints, headers, auth, pagination, field mapping.

---

## 1. SEEK

**Status**: ✅ Working
**Method**: JSON API (reverse-engineered, no auth required)

### Endpoint
```
GET https://www.seek.com.au/api/jobsearch/v5/search
```

### Headers
```
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15
```

### Query Parameters
| Parameter | Value | Notes |
|-----------|-------|-------|
| `siteKey` | `AU-Main` | Required |
| `sourcesystem` | `houston` | Required |
| `where` | `All Australia` | Broadest scope |
| `page` | `1, 2, ...` | 1-indexed |
| `seekSelectAllPages` | `true` | Required for pagination |
| `keywords` | `nurse` | Search term |
| `include` | `seodata` | Adds extra metadata |
| `locale` | `en-AU` | Required |

### Response (key fields)
```json
{
  "data": [
    {
      "id": "90673439",
      "title": "Clinic Nurse",
      "advertiser": { "description": "Nectar Brands" },
      "listingDate": "2026-03-03T00:35:25Z",
      "locations": [{ "label": "Hawthorn, Melbourne VIC" }],
      "classifications": [{
        "subclassification": { "description": "Nursing - General Medical & Surgical" }
      }]
    }
  ],
  "totalCount": 8191,
  "solMetadata": { "pageSize": 20 }
}
```

### Field Mapping
| Canonical | SEEK field |
|-----------|-----------|
| Facility Name | `advertiser.description` |
| Job Title | `title` |
| Job Category | `classifications[0].subclassification.description` → SEEK_CATEGORY_MAP |
| State | regex match on `locations[0].label` |
| City | `locations[0].label` split on `,` → first part |
| Date Posted | `listingDate[:10]` |
| Job URL | `https://www.seek.com.au/job/{id}` |

### Pagination
- `pageSize` from `solMetadata.pageSize` (default 20)
- Stop when `page >= ceil(totalCount / pageSize)` or `page >= max_pages` (5)
- Full raw API response saved per page (not per keyword) — ~20 jobs per file

---

## 2. EthicalJobs

**Status**: ✅ Working
**Method**: HTML scraping — Next.js RSC (`__next_f`) payload parsing

### Endpoint
```
GET https://www.ethicaljobs.com.au/jobs?keywords={keyword}&page={page}
```

### Headers
```
accept: text/html,...
accept-language: en-GB,en;q=0.8
user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/145.0.0.0
```

### Parsing Approach
The page is Next.js SSR. Job data is embedded in inline `<script>` tags:
```javascript
self.__next_f.push([1, "...encoded RSC payload..."])
```
Each chunk is decoded and concatenated. The target JSON chunk contains `expiresAt`, `organisationName`, and `locations` keys. The `"job":{}` object is extracted using `json.JSONDecoder().raw_decode()` (required because the payload contains embedded HTML).

### Detail Page Enrichment
Each job's detail page is fetched (0.5s delay) to extract `approvedAt` (actual posting date). The full job object from the detail RSC is merged into the listing object.

### Field Mapping
| Canonical | EthicalJobs field |
|-----------|-------------------|
| Facility Name | `organisationName` |
| Job Title | `title` (strip ` - location` suffix if present) |
| Job Category | inferred from search keyword |
| State | `locations[0].name` → LOCATION_STATE_MAP |
| City | `locations[0].locality` |
| Date Posted | `approvedAt[:10]` (from detail page) |
| Job URL | `https://www.ethicaljobs.com.au/members/{slug}` |

### Pagination
- `total` field from RSC payload, 30 jobs/page
- `total_pages = ceil(total / 30)`, capped at `max_pages` (5)

---

## 3. Jora

**Status**: ✅ Working
**Method**: HTML scraping (BeautifulSoup)

### Endpoint
```
GET https://au.jora.com/{Keyword}-jobs?disallow=true&sp=recent_homepage&pt=unseen
GET https://au.jora.com/{Keyword}-jobs?disallow=true&sp=recent_homepage&pt=unseen&p={N}
```
Note: `{Keyword}` is title-cased with hyphens (e.g. `Aged-Care`, `Support-Worker`). Pages 2+ use `&p=N` on the same slug URL. **Do not use the `/j` endpoint for pagination — it requires a `tk` token and returns 403.**

### Headers
```
accept: text/html,...
accept-language: en-AU,en;q=0.9
user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/124.0.0.0
referer: https://au.jora.com/{Keyword}-jobs
```

### Card Selector
```python
cards = soup.find_all('div', class_='job-card')
# Fallback: div[id^="r_"] (hex ID pattern)
```
**Note**: `data-job-id` is on `<button>` (save) elements, not card containers — don't use it.

### Title De-duplication
Jora duplicates the title text in the link's inner DOM. Detected by checking if `words[:half] == words[half:]`.

### Field Extraction
| Canonical | Jora element |
|-----------|-------------|
| Facility Name | `span.job-company` |
| Job Title | `h2.job-title a` (de-duplicated) |
| State | last word of `a.job-location` text if in AU state set |
| City | remaining words of `a.job-location` text |
| Date Posted | `span.job-listed-date` → relative date → ISO (`"3d ago"` → `today - 3 days`) |
| Job URL | `h2.job-title a[href]` path → prefixed with `https://au.jora.com` |

### Pagination
- `"Page X of Y"` text extracted to find `total_pages`
- Capped at `max_pages` (5)

---

## 4. Workforce Australia

**Status**: ✅ Working
**Method**: JSON API (no auth required)

### Endpoint
```
GET https://www.workforceaustralia.gov.au/api/v1/global/vacancies/
```

### Headers
```
Accept: application/json, text/plain, */*
Accept-Language: en-AU,en;q=0.9
X-Requested-With: XMLHttpRequest
cache-control: no-cache
User-Agent: Mozilla/5.0 ...
```

### Query Parameters
| Parameter | Value |
|-----------|-------|
| `searchText` | `nurse` |
| `skip` | `0, 20, 40, ...` |

### Response (key fields)
```json
{
  "totalCount": 847,
  "results": [
    {
      "result": {
        "vacancyId": "123456",
        "title": "Registered Nurse",
        "employerName": "Aged Care Facility",
        "suburb": "SYDNEY",
        "state": "NSW",
        "creationDate": "2026-03-10T09:00:00",
        "occupation": { "label": "Registered Nurse" }
      }
    }
  ]
}
```

### Field Mapping
| Canonical | WFA field |
|-----------|----------|
| Facility Name | `employerName` |
| Job Title | `title` |
| State | `state` (already clean abbreviation) |
| City | `suburb` — converted from ALL CAPS to Title Case |
| Date Posted | `creationDate[:10]` |
| Job URL | `https://www.workforceaustralia.gov.au/individuals/jobs/{vacancyId}` |

### Pagination
- `skip` increments by 20 per page
- Stop when `skip + 20 >= totalCount` or `page >= max_pages` (5)

---

## 5. Indeed AU

**Status**: ✅ Working
**Method**: Internal GraphQL API (public mobile app key)

### Endpoint
```
POST https://apis.indeed.com/graphql
```

### Headers
```
content-type: application/json
indeed-api-key: 161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8
indeed-co: AU          ← must be uppercase
indeed-locale: en-AU
user-agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 ...) Indeed App 193.1
indeed-app-info: appv=193.1; appid=com.indeed.jobsearch; osv=16.6.1; os=ios; dtype=phone
```

**Note**: `indeed-co: au` (lowercase) returns HTTP 400. Must be `AU`.

### GraphQL Query
```graphql
query {
  jobSearch(
    what: "nurse"
    location: {where: "Australia", radius: 100, radiusUnit: MILES}
    limit: 100
    sort: DATE
    cursor: "..."   # omit on first page
  ) {
    pageInfo { nextCursor }
    results {
      job {
        key
        title
        datePublished
        location { admin1Code city countryCode }
        employer { name }
      }
    }
  }
}
```

### Field Mapping
| Canonical | Indeed field |
|-----------|-------------|
| Facility Name | `employer.name` |
| Job Title | `title` |
| State | `location.admin1Code` (e.g. `NSW`) |
| City | `location.city` |
| Date Posted | `datetime.fromtimestamp(datePublished / 1000).strftime('%Y-%m-%d')` |
| Job URL | `https://au.indeed.com/viewjob?jk={key}` |

### Pagination
- Cursor-based: `nextCursor` from `pageInfo`
- 100 results per page, up to 5 pages = 500/keyword
- `verify=False` used (SSL suppressed via `warnings.filterwarnings('ignore')`)

---

## 6. CareerOne

**Status**: ✅ Working
**Method**: REST JSON API + session via CSRF cookie

### Session Establishment (called on every `run()`)
```
GET https://www.careerone.com.au/csrf-cookie
```
Auto-sets `seekerapi_session` cookie and `XSRF-TOKEN` cookie. No login required. The XSRF token is extracted and added as `x-xsrf-token` header for subsequent requests.

### Search Endpoint
```
GET https://www.careerone.com.au/api/v1/search-job
```

### Headers
```
accept: application/json
accept-language: en-AU,en;q=0.9
platform-code: careerone
site-code: careerone
user-agent: Mozilla/5.0 ...
x-xsrf-token: {token from csrf-cookie}
```

### Query Parameters
| Parameter | Value | Notes |
|-----------|-------|-------|
| `url` | `/nurse-jobs/in-australia` | Keyword-specific slug (see KEYWORD_URL_MAP) |
| `locale` | `AU` | Required |
| `allow_backfill` | `true` | Allows broader results |
| `page` | `2, 3, ...` | Omit on page 1 |

### Keyword → URL Slug Map
| Keyword | Slug |
|---------|------|
| nurse | `/nurse-jobs/in-australia` |
| aged care | `/aged-care-jobs/in-australia` |
| disability support | `/disability-support-worker-jobs/in-australia` |
| allied health | `/allied-health-jobs/in-australia` |
| support worker | `/support-worker-jobs/in-australia` |

### Field Mapping
| Canonical | CareerOne field |
|-----------|----------------|
| Facility Name | `company_name` (fallback: `account_name`) |
| Job Title | `job_title` |
| State | `location_state_code` (already clean abbreviation) |
| City | `location_level_1_label` |
| Date Posted | `activates_at[:10]` (fallback: `refreshed_at`) |
| Job URL | `https://www.careerone.com.au/{URL}` |

### Pagination
- `page=N` param, 20 results/page, up to 5 pages = 100/keyword
- Stop when `len(all_jobs) >= job_count` (from `search_results.job_count`)

---

## 7. Adzuna AU

**Status**: ✅ Working
**Method**: Official developer REST API (free tier)

### Credentials
```
app_id:  fef86366
app_key: a4f2dcf93901b959d42323d5029cfdb0
```

### Endpoint
```
GET https://api.adzuna.com/v1/api/jobs/au/search/{page}
```
Pages are 1-indexed.

### Query Parameters
| Parameter | Value |
|-----------|-------|
| `app_id` | `fef86366` |
| `app_key` | `a4f2dcf93901b959d42323d5029cfdb0` |
| `results_per_page` | `50` |
| `what` | `nurse` |
| `sort_by` | `date` |

### Response (key fields)
```json
{
  "count": 17526,
  "results": [
    {
      "id": 5662172144,
      "title": "Registered Nurse",
      "company": { "display_name": "Medi-Corp" },
      "location": {
        "display_name": "South Brisbane, Queensland",
        "area": ["Australia", "Queensland", "Brisbane Region", "Brisbane", "South Brisbane"]
      },
      "created": "2026-03-12T09:50:44Z",
      "redirect_url": "https://www.adzuna.com.au/details/5662172144?utm_medium=api&utm_source=fef86366",
      "description": "...",
      "contract_time": "full_time",
      "salary_min": 85000,
      "salary_max": 105000
    }
  ]
}
```

### Field Mapping
| Canonical | Adzuna field |
|-----------|-------------|
| Facility Name | `company.display_name` |
| Job Title | `title` |
| State | `location.area[1]` (full state name) → STATE_NAME_MAP abbreviation |
| City | `location.area[-1]` (most specific area) |
| Date Posted | `created[:10]` |
| Job URL | `redirect_url` |

### State Name Map (in `adzuna.py`)
```python
STATE_NAME_MAP = {
    'new south wales': 'NSW', 'victoria': 'VIC',
    'queensland': 'QLD', 'western australia': 'WA',
    'south australia': 'SA', 'tasmania': 'TAS',
    'australian capital territory': 'ACT', 'northern territory': 'NT',
}
```

### Pagination
- Page-based (1-indexed), 50 results/page, up to 5 pages = 250/keyword
- Stop when `len(all_jobs) >= count` or no results returned
