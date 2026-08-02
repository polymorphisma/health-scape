import os
import re
import json
import logging
import urllib.parse
import pandas as pd
from datetime import datetime, timedelta

# Query-string params that are purely tracking/search artifacts and should be
# stripped before URL deduplication. Job-identity params (e.g. Indeed's `jk=`)
# must NOT be stripped — they ARE the unique identifier.
_STRIP_PARAMS = {
    'keywords', 'keyword', 'ref', 'src', 'source',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
}

# Maps SEEK sub-classification descriptions → client's 4 canonical categories.
SEEK_CATEGORY_MAP = {
    # Nursing
    'nursing - general medical & surgical':             'Nursing',
    'nursing - community, maternal & child health':     'Nursing',
    'nursing - a&e, critical care & icu':               'Nursing',
    'nursing - aged care':                              'Nursing',
    'nursing - theatre & recovery':                     'Nursing',
    'nursing - high acuity':                            'Nursing',
    'nursing - psych, forensic & correctional health':  'Nursing',
    'nursing - management':                             'Nursing',
    'nursing - educators & facilitators':               'Nursing',
    'nursing - neonatal, paediatric & child health':    'Nursing',
    'nursing - midwifery, neo-natal, mothers & babies': 'Nursing',
    # Aged Care
    'aged care':                                        'Aged Care',
    # Disability Support
    'aged & disability support':                        'Disability Support',
    'disability support':                               'Disability Support',
    # Allied Health — all SEEK variants (acronym changed OTEP → OT between API versions)
    'allied health':                                    'Allied Health',
    'physiotherapy, otep & rehabilitation':             'Allied Health',
    'physiotherapy, ot & rehabilitation':               'Allied Health',
    'physiotherapy, ot&p & rehabilitation':             'Allied Health',
    'psychology, counselling & social work':            'Allied Health',
    'medical imaging':                                  'Allied Health',
    'occupational therapy':                             'Allied Health',
    'speech pathology':                                 'Allied Health',
    'speech therapy':                                   'Allied Health',
    'pharmacy':                                         'Allied Health',
    'chiropractic & osteopathic':                       'Allied Health',
    'optical':                                          'Allied Health',
    'dietetics & nutrition':                            'Allied Health',
    'general practitioners':                            'Allied Health',
    'medical specialists':                              'Allied Health',
    # Nursing variants
    'nursing - midwifery, neo-natal, scn & nicu':       'Nursing',
    'nursing - midwifery, neo-natal, mothers & babies': 'Nursing',
    # Healthcare-adjacent (keep in output)
    'medical administration':                           'Allied Health',
    'management':                                       'Allied Health',
}

# Common Australian cities → state abbreviation.
# Used as fallback when state extraction from the location string fails.
CITY_STATE_MAP = {
    # NSW
    'sydney': 'NSW', 'newcastle': 'NSW', 'wollongong': 'NSW', 'central coast': 'NSW',
    'penrith': 'NSW', 'campbelltown': 'NSW', 'parramatta': 'NSW', 'blacktown': 'NSW',
    'liverpool': 'NSW', 'gosford': 'NSW', 'albury': 'NSW', 'wagga wagga': 'NSW',
    'orange': 'NSW', 'dubbo': 'NSW', 'tamworth': 'NSW', 'lismore': 'NSW',
    'port macquarie': 'NSW', 'bathurst': 'NSW', 'maitland': 'NSW', 'cessnock': 'NSW',
    # VIC
    'melbourne': 'VIC', 'geelong': 'VIC', 'ballarat': 'VIC', 'bendigo': 'VIC',
    'shepparton': 'VIC', 'wodonga': 'VIC', 'mildura': 'VIC', 'warrnambool': 'VIC',
    'traralgon': 'VIC', 'horsham': 'VIC', 'wangaratta': 'VIC', 'frankston': 'VIC',
    # QLD
    'brisbane': 'QLD', 'gold coast': 'QLD', 'sunshine coast': 'QLD', 'townsville': 'QLD',
    'cairns': 'QLD', 'toowoomba': 'QLD', 'rockhampton': 'QLD', 'mackay': 'QLD',
    'bundaberg': 'QLD', 'hervey bay': 'QLD', 'gladstone': 'QLD', 'ipswich': 'QLD',
    # WA
    'perth': 'WA', 'fremantle': 'WA', 'mandurah': 'WA', 'bunbury': 'WA',
    'geraldton': 'WA', 'kalgoorlie': 'WA', 'albany': 'WA', 'broome': 'WA',
    # SA
    'adelaide': 'SA', 'mount gambier': 'SA', 'whyalla': 'SA', 'port augusta': 'SA',
    'port pirie': 'SA', 'victor harbor': 'SA', 'murray bridge': 'SA',
    # TAS
    'hobart': 'TAS', 'launceston': 'TAS', 'devonport': 'TAS', 'burnie': 'TAS',
    # ACT
    'canberra': 'ACT', 'belconnen': 'ACT', 'tuggeranong': 'ACT', 'woden': 'ACT',
    # NT
    'darwin': 'NT', 'alice springs': 'NT', 'palmerston': 'NT', 'katherine': 'NT',
}

# Healthcare title keywords — at least one must appear in the job title
# for an EthicalJobs result to be kept. Protects against full-text false positives.
HEALTHCARE_TITLE_KEYWORDS = [
    'nurse', 'nursing', 'midwi',
    'aged care', 'age care',
    'disability', 'support worker', 'care worker', 'care coordinator',
    'allied health', 'physiother', 'occupational therap', 'speech', 'patholog',
    'dietit', 'nutrition', 'pharmacy', 'pharmacist',
    'psycholog', 'counsell', 'mental health',
    'social work', 'case manager', 'care manager',
    'medical', 'clinical', 'health worker', 'health coordinator',
    'health manager', 'health officer', 'health practitioner',
    'doctor', 'physician', 'surgeon', 'gp ', 'general practitioner',
    'dental', 'optom', 'radiol', 'sonograph',
    'care assistant', 'personal care', 'home care',
]


def is_healthcare_title(title: str) -> bool:
    """Returns True if the job title contains at least one healthcare keyword."""
    t = title.lower()
    return any(kw in t for kw in HEALTHCARE_TITLE_KEYWORDS)


# Indeed and Adzuna classify by search keyword and employer rather than by job
# title, so a care-sector employer hiring a developer lands in the feed as a
# care role: Red Hat SREs, SAP consultants, retail sales assistants, a Scentre
# Group data scientist. Roughly 1.2% of those two platforms' output.
#
# This is a denylist rather than an allowlist by design. Healthcare employment
# has a long ancillary tail (cleaners, cooks, laundry and food service staff at
# aged care facilities) that recruiters do want. Running the allowlist above
# across Indeed and Adzuna drops 38% of the run, most of it legitimate.
NON_HEALTHCARE_TITLE_KEYWORDS = [
    'software', 'developer', 'devops', 'site reliability', 'full stack',
    'backend', 'frontend', 'cyber security', 'network security',
    'data scientist', 'data engineer', 'solutions architect',
    'principal engineer', 'engineering manager', 'structural engineer',
    'civil engineer', 'mechanical engineer', 'electrical engineer',
    'design assurance', 'erp ', 'salesforce', 'cloud engineer',
    'technical account', 'it support', 'business development',
    'partner development', 'account manager', 'sales consultant',
    'sales assistant', 'sales representative', 'marketing', 'brand manager',
    'prototyping engineer',
]

# Clinical roles the allowlist above does not name. A denylist hit is kept if
# the title matches here or HEALTHCARE_TITLE_KEYWORDS, which is what saves
# "Locum Podiatrist" from the 'sales' match elsewhere in its title.
EXTRA_CLINICAL_KEYWORDS = [
    'podiatr', 'paramedic', 'phlebotom', 'audiolog', 'chiroprac',
    'osteopath', 'sonograp', 'therapist', 'support work',
]


def is_non_healthcare_title(title: str) -> bool:
    """True if the title is clearly not a healthcare role.

    Denylist match wins only when nothing clinical appears in the title.
    """
    t = str(title).lower()
    if not any(kw in t for kw in NON_HEALTHCARE_TITLE_KEYWORDS):
        return False
    if is_healthcare_title(t):
        return False
    return not any(kw in t for kw in EXTRA_CLINICAL_KEYWORDS)


class DataProcessor:
    def __init__(self, base_dir=".", days_window=7):
        self.base_dir = base_dir
        self.days_window = days_window
        self.raw_dumps_dir = os.path.join(self.base_dir, "raw_dumps")
        self.output_dir = os.path.join(self.base_dir, "output")
        self.logs_dir = os.path.join(self.base_dir, "logs")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        self._setup_logging()

        # State standardization mapping
        self.state_map = {
            'new south wales': 'NSW', 'nsw': 'NSW',
            'victoria': 'VIC', 'vic': 'VIC',
            'queensland': 'QLD', 'qld': 'QLD',
            'western australia': 'WA', 'wa': 'WA',
            'south australia': 'SA', 'sa': 'SA',
            'tasmania': 'TAS', 'tas': 'TAS',
            'australian capital territory': 'ACT', 'act': 'ACT',
            'northern territory': 'NT', 'nt': 'NT',
        }

    def _setup_logging(self):
        log_file = os.path.join(self.logs_dir, f"processor_{datetime.now().strftime('%Y%m%d')}.log")
        formatter = logging.Formatter('%(asctime)s - processor - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        self.logger = logging.getLogger("processor")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def extract_state(self, location_str):
        """Extracts and standardizes an Australian state from a location string."""
        if not isinstance(location_str, str):
            return "Unknown"
        loc_lower = location_str.lower()
        for key, val in self.state_map.items():
            if re.search(rf'\b{re.escape(key)}\b', loc_lower):
                return val
        return "Unknown"

    def city_to_state(self, city: str) -> str:
        """Looks up state by city name. Returns 'Unknown' if not found."""
        if not city:
            return "Unknown"
        return CITY_STATE_MAP.get(city.lower().strip(), "Unknown")

    def process_seek_file(self, file_path):
        """Processes a raw SEEK JSON dump into standardized records."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            jobs = data.get('data', [])
            processed = []

            for job in jobs:
                facility_name = job.get('advertiser', {}).get('description', 'Unknown Facility')
                job_title = job.get('title', 'Unknown Title')

                raw_category = None
                classifications = job.get('classifications', [])
                if classifications and 'subclassification' in classifications[0]:
                    raw_category = classifications[0]['subclassification'].get('description', '')
                job_category = SEEK_CATEGORY_MAP.get(
                    (raw_category or '').lower(),
                    raw_category or 'Healthcare & Medical'
                )

                # Drop SEEK results whose category didn't map to a canonical
                # healthcare category AND whose title isn't healthcare-related.
                # Catches non-healthcare roles that matched on keyword in description.
                canonical = {'Nursing', 'Aged Care', 'Disability Support', 'Allied Health'}
                if job_category not in canonical:
                    if not is_healthcare_title(job_title):
                        continue
                    # Reclassify healthcare-titled rows that SEEK miscategorised
                    t = job_title.lower()
                    if any(kw in t for kw in ['nurse', 'nursing', 'midwi']):
                        job_category = 'Nursing'
                    elif any(kw in t for kw in ['aged care', 'age care']):
                        job_category = 'Aged Care'
                    elif any(kw in t for kw in ['disability', 'support worker', 'care worker']):
                        job_category = 'Disability Support'
                    else:
                        job_category = 'Allied Health'

                location_str = ''
                state = 'Unknown'
                if job.get('locations'):
                    location_str = job['locations'][0].get('label', '')
                    state = self.extract_state(location_str)

                city = location_str.split(',')[0].strip() if ',' in location_str else location_str

                # Fix 2: city→state fallback
                if state == 'Unknown' and city:
                    state = self.city_to_state(city)

                date_posted = (job.get('listingDate', '') or '')[:10]
                job_url = f"https://www.seek.com.au/job/{job.get('id')}"

                processed.append({
                    "Platform": "SEEK",
                    "Facility Name": facility_name.strip(),
                    "Job Title": job_title.strip(),
                    "Job Category": job_category.strip(),
                    "State": state,
                    "City": city,
                    "Date Posted": date_posted,
                    "Job URL": job_url,
                })

            return processed
        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            return []

    def process_jora_file(self, file_path):
        """Processes a raw Jora JSON dump into standardized records."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            category_label = data.get('category', 'Healthcare')
            jobs = data.get('data', [])
            processed = []

            for job in jobs:
                job_title = job.get('title', 'Unknown Title')
                facility_name = job.get('facility_name', 'Unknown Facility')
                state = job.get('state', 'Unknown')
                city = job.get('city', '')

                if state == 'Unknown' and city:
                    state = self.city_to_state(city)

                processed.append({
                    "Platform": "Jora",
                    "Facility Name": facility_name.strip(),
                    "Job Title": job_title.strip(),
                    "Job Category": category_label,
                    "State": state,
                    "City": city.strip(),
                    "Date Posted": job.get('date_posted', ''),
                    "Job URL": job.get('url', ''),
                })

            return processed

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            return []

    def process_careerone_file(self, file_path):
        """Processes a raw CareerOne JSON dump into standardized records."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            category_label = data.get('category', 'Healthcare')
            jobs = data.get('data', [])
            processed = []

            for job in jobs:
                state = job.get('state', 'Unknown').strip()
                city = job.get('city', '').strip()
                if state == 'Unknown' and city:
                    state = self.city_to_state(city)

                processed.append({
                    "Platform":      "CareerOne",
                    "Facility Name": job.get('facility_name', 'Unknown Facility').strip(),
                    "Job Title":     job.get('title', 'Unknown Title').strip(),
                    "Job Category":  category_label,
                    "State":         state,
                    "City":          city,
                    "Date Posted":   job.get('date_posted', ''),
                    "Job URL":       job.get('url', ''),
                })

            return processed

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            return []

    def process_indeed_file(self, file_path):
        """Processes a raw Indeed JSON dump into standardized records."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            category_label = data.get('category', 'Healthcare')
            jobs = data.get('data', [])
            processed = []

            for job in jobs:
                state = job.get('state', 'Unknown').strip()
                city = job.get('city', '').strip()
                if state == 'Unknown' and city:
                    state = self.city_to_state(city)

                processed.append({
                    "Platform":     "Indeed",
                    "Facility Name": job.get('facility_name', 'Unknown Facility').strip(),
                    "Job Title":    job.get('title', 'Unknown Title').strip(),
                    "Job Category": category_label,
                    "State":        state,
                    "City":         city,
                    "Date Posted":  job.get('date_posted', ''),
                    "Job URL":      job.get('url', ''),
                })

            return processed

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            return []

    def process_workforceaustralia_file(self, file_path):
        """Processes a raw Workforce Australia JSON dump into standardized records."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            category_label = data.get('category', 'Healthcare')
            jobs = data.get('data', [])
            processed = []

            for job in jobs:
                processed.append({
                    "Platform":     "WorkforceAustralia",
                    "Facility Name": job.get('facility_name', 'Unknown Facility').strip(),
                    "Job Title":    job.get('title', 'Unknown Title').strip(),
                    "Job Category": category_label,
                    "State":        job.get('state', 'Unknown').strip(),
                    "City":         job.get('city', '').strip(),
                    "Date Posted":  job.get('date_posted', ''),
                    "Job URL":      job.get('url', ''),
                })

            return processed

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            return []

    def process_adzuna_file(self, file_path):
        """Processes a raw Adzuna JSON dump into standardized records."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            category_label = data.get('category', 'Healthcare')
            jobs = data.get('data', [])
            processed = []

            for job in jobs:
                state = job.get('state', 'Unknown').strip()
                city = job.get('city', '').strip()
                if state == 'Unknown' and city:
                    state = self.city_to_state(city)

                processed.append({
                    "Platform":      "Adzuna",
                    "Facility Name": job.get('facility_name', 'Unknown Facility').strip(),
                    "Job Title":     job.get('title', 'Unknown Title').strip(),
                    "Job Category":  category_label,
                    "State":         state,
                    "City":          city,
                    "Date Posted":   job.get('date_posted', ''),
                    "Job URL":       job.get('url', ''),
                })

            return processed

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            return []

    def process_ethicaljobs_file(self, file_path):
        """Processes a raw EthicalJobs JSON dump (RSC-parsed) into standardized records."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            category_label = data.get('category', 'Allied Health')
            jobs = data.get('data', [])
            processed = []

            for job in jobs:
                job_title = job.get('title', 'Unknown Title')

                # Fix 3: drop EthicalJobs results where title isn't healthcare-related
                if not is_healthcare_title(job_title):
                    self.logger.debug(f"Filtered non-healthcare title: '{job_title}'")
                    continue

                facility_name = job.get('organisationName', 'Unknown Facility')
                state = job.get('state', 'Unknown')
                city = job.get('locality', '') or job.get('location_name', '')

                # Fix 2: city→state fallback
                if state == 'Unknown' and city:
                    state = self.city_to_state(city)

                scrape_date = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d")
                date_field = (job.get('approvedAt') or '')[:10] or scrape_date

                processed.append({
                    "Platform": "EthicalJobs",
                    "Facility Name": facility_name.strip(),
                    "Job Title": job_title.strip(),
                    "Job Category": category_label,
                    "State": state,
                    "City": city.strip(),
                    "Date Posted": date_field,
                    "Job URL": job.get('url', ''),
                })

            return processed

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            return []

    def run(self):
        """Main ETL pipeline: load → deduplicate → weekly filter → export."""
        self.logger.info("Starting data processing pipeline...")
        all_records = []

        # 1. Load all raw dumps
        for filename in sorted(os.listdir(self.raw_dumps_dir)):
            file_path = os.path.join(self.raw_dumps_dir, filename)
            if filename.startswith('seek_raw'):
                all_records.extend(self.process_seek_file(file_path))
            elif filename.startswith('ethicaljobs_raw'):
                all_records.extend(self.process_ethicaljobs_file(file_path))
            elif filename.startswith('jora_raw'):
                all_records.extend(self.process_jora_file(file_path))
            elif filename.startswith('workforceaustralia_raw'):
                all_records.extend(self.process_workforceaustralia_file(file_path))
            elif filename.startswith('indeed_raw'):
                all_records.extend(self.process_indeed_file(file_path))
            elif filename.startswith('careerone_raw'):
                all_records.extend(self.process_careerone_file(file_path))
            elif filename.startswith('adzuna_raw'):
                all_records.extend(self.process_adzuna_file(file_path))

        if not all_records:
            self.logger.warning("No records found to process.")
            return

        self.logger.info(f"Loaded {len(all_records)} total RAW records.")
        df = pd.DataFrame(all_records)

        # Normalise state casing — old WFA raw dumps may have 'UNKNOWN' (all-caps)
        df['State'] = df['State'].apply(
            lambda s: 'Unknown' if str(s).upper() == 'UNKNOWN' else str(s)
        )

        # 1b. Drop non-healthcare roles that keyword/employer classification let
        # through. Runs before dedup so the counts below describe real jobs.
        before = len(df)
        df = df[~df['Job Title'].apply(is_non_healthcare_title)]
        self.logger.info(
            f"Non-healthcare title filter removed {before - len(df)}. {len(df)} remaining."
        )

        # 2. Primary deduplication — URL (strip tracking params only, keep ID params like jk=)
        def _url_key(url: str) -> str:
            try:
                p = urllib.parse.urlparse(str(url))
                qs = {k: v for k, v in urllib.parse.parse_qs(p.query).items()
                      if k not in _STRIP_PARAMS}
                clean = urllib.parse.urlunparse(p._replace(
                    query=urllib.parse.urlencode(qs, doseq=True)
                ))
                return clean.rstrip('/')
            except Exception:
                return str(url)

        df['_url_key'] = df['Job URL'].apply(_url_key)
        before = len(df)
        df = df.drop_duplicates(subset=['_url_key']).drop(columns=['_url_key'])
        self.logger.info(f"URL dedup removed {before - len(df)}. {len(df)} remaining.")

        # 3. Secondary deduplication — Facility + Title + State composite
        df['_composite'] = (df['Facility Name'] + '_' + df['Job Title'] + '_' + df['State']).str.lower()
        before = len(df)
        df = df.drop_duplicates(subset=['_composite']).drop(columns=['_composite'])
        self.logger.info(f"Composite dedup removed {before - len(df)}. {len(df)} remaining.")

        # 4. Fix 1: weekly window — keep only jobs posted within the last N days
        cutoff = datetime.now() - timedelta(days=self.days_window)
        df['_date'] = pd.to_datetime(df['Date Posted'], errors='coerce')
        before = len(df)
        df = df[df['_date'] >= cutoff].drop(columns=['_date'])
        self.logger.info(
            f"Weekly window ({self.days_window} days, cutoff {cutoff.date()}) "
            f"removed {before - len(df)} older jobs. {len(df)} remaining."
        )

        if df.empty:
            self.logger.warning("No jobs remain after weekly window filter.")
            return

        # 5. Export
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        output_csv = os.path.join(self.output_dir, f'healthcare_jobs_report_{timestamp}.csv')
        df.to_csv(output_csv, index=False, encoding='utf-8')
        self.logger.info(f"Exported {len(df)} jobs to {output_csv}")
        return output_csv


if __name__ == "__main__":
    processor = DataProcessor()
    processor.run()
