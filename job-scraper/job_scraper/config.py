"""All tunable constants for the scraper, in one place. Nothing in here
does anything by itself -- it's imported by the modules that use it.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Search term tiers
# --------------------------------------------------------------------------
# PRIMARY terms are what you actually want. They're searched across every
# source, in source-priority order (LinkedIn -> Indeed -> RemoteOK), before
# anything else runs at all.
#
# BACKUP terms only get touched if the primary terms fail to fill
# TARGET_JOB_COUNT after being searched across every source -- i.e. "not
# found in either of the job sites" for the primary roles. If primary terms
# alone hit the target, backups never fire and their round trips are never
# spent.
PRIMARY_SEARCH_TERMS = ["AI Engineer", "Machine Learning Engineer"]
BACKUP_SEARCH_TERMS = ["Data Scientist"]  # "ML Ops Engineer", "AI Researcher"

# Processed in this order: primary tier fully exhausted (all sources) before
# backup tier is even attempted.
TERM_TIERS = [
    ("primary", PRIMARY_SEARCH_TERMS),
    ("backup", BACKUP_SEARCH_TERMS),
]

# --------------------------------------------------------------------------
# Kenya tech-giant search
# --------------------------------------------------------------------------
# Runs as its own tier, ahead of the role tiers above: landing a role at one
# of these specific employers beats a generic remote match, so it gets first
# shot at the target count. See sources/linkedin.py:fetch_kenya_company_jobs
# for why this is LinkedIn-only (jobspy's Indeed country list doesn't
# include Kenya).
#
# Matched as a case-insensitive substring against whatever the source
# returns as `company` (e.g. "Amazon Web Services (AWS)" still matches
# "amazon"), so keep entries lowercase and reasonably specific -- "safaricom"
# won't false-positive, but a short generic word could match unrelated firms.
TARGET_KENYA_COMPANIES = {"microsoft", "amazon", "aws", "google", "safaricom"}
KENYA_COMPANY_SEARCH_LOCATION = "Kenya"

# This is a SHARED cap across every tier and every source -- the Kenya
# company search first, then LinkedIn -> Indeed -> RemoteOK for whichever
# role tier (primary, then backup) is currently active -- once it's hit,
# everything remaining is skipped for this run. It's fully decoupled from
# the tiering above: raise it if you want more total jobs per run,
# independent of which roles/sources/companies fill it.
#
# NOTE: this value is baked into the image at build time, not read from an
# env var. If a running container's logs show a different `target=` value
# than what's in this file, the container is running an older image --
# rebuild/redeploy rather than assuming the code is wrong.
TARGET_JOB_COUNT = 10

# --------------------------------------------------------------------------
# Speed tuning
# --------------------------------------------------------------------------
# Ask for more results per call instead of making more, smaller calls.
# These are estimates, not measured; watch per-batch timing in the logs
# after deploying and retune if a call starts taking noticeably longer.
BATCH_SIZE = 15
MAX_BATCHES_PER_TERM = 2

# Pacing between requests to the same source, so we don't hammer LinkedIn /
# Indeed back-to-back. These are deliberate, not incidental -- scraping
# LinkedIn in particular is fragile and against its ToS, so don't drop these
# to zero or parallelize the calls without testing carefully.
LINKEDIN_BATCH_SLEEP_SECONDS = 10
INDEED_QUERY_SLEEP_SECONDS = 5

# Persisted on a mounted volume so it survives container restarts
SENT_JOBS_FILE = Path("/data/sent_job_urls.json")

EXCLUDE_KEYWORDS = [
    "senior", "sr.", "sr ", "staff", "principal", "lead", "director",
    "head of", "vp", "vice president", "manager", "architect",
]

# Only keep listings whose location string mentions one of these. Matched as
# whole words/phrases (case-insensitive) against whatever the source returns
# as a location (e.g. "Nairobi, Kenya", "London, UK", "Remote, US").
# Edit these sets to add/remove specific countries.
NORTH_AMERICA_COUNTRIES = {
    "united states", "usa", "u.s.a.", "u.s.", "us", "canada", "mexico",
}

EUROPE_COUNTRIES = {
    "united kingdom", "uk", "u.k.", "ireland", "germany", "france", "spain",
    "portugal", "italy", "netherlands", "belgium", "luxembourg",
    "switzerland", "austria", "poland", "czech republic", "czechia",
    "slovakia", "hungary", "romania", "bulgaria", "greece", "croatia",
    "slovenia", "serbia", "denmark", "sweden", "norway", "finland",
    "iceland", "estonia", "latvia", "lithuania", "malta", "cyprus",
    "ukraine",
}

AFRICA_COUNTRIES = {
    "kenya", "south africa", "nigeria", "egypt", "morocco", "ghana",
    "ethiopia", "tanzania", "uganda", "rwanda", "senegal", "tunisia",
    "algeria", "botswana", "namibia", "zambia", "zimbabwe", "mozambique",
    "cote d'ivoire", "ivory coast", "cameroon", "mauritius",
}

ALLOWED_REGION_COUNTRIES = NORTH_AMERICA_COUNTRIES | EUROPE_COUNTRIES | AFRICA_COUNTRIES

# Broad location tags some boards use instead of (or alongside) a specific
# country -- these are a deliberate, intentional signal from the poster
# ("open to anyone anywhere" / "open to EMEA"), not the kind of ambiguous
# blank location filters.is_allowed_region() otherwise drops.
# filters.is_broad_remote_location() is also used to PRIORITIZE these within
# a batch, not just allow them.
BROAD_ALLOWED_LOCATION_TAGS = {"worldwide", "emea"}

# jobspy's Indeed scraper is per-country (one `country_indeed` value per
# call), unlike LinkedIn's single global "Remote" search. This list picks a
# representative country per target region. jobspy's supported Africa list
# is limited to these four -- Kenya specifically isn't in it (see
# jobspy_patch.py for what that omission does on the LinkedIn side too).
INDEED_COUNTRIES = ["usa", "canada", "uk", "germany", "south africa", "nigeria", "egypt", "morocco"]

REMOTEOK_API_URL = "https://remoteok.com/api"
REMOTEOK_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; job-scraper-bot/1.0)"}
