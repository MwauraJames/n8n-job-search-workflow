# job-scraper: fixes + modular layout

## What changed

**1. Fixed the Kenya crash.** It wasn't a bug in your code — `jobspy`'s
`Country` enum doesn't include Kenya, and LinkedIn's own result parser
(`_get_location`) calls `Country.from_string()` on the country text of
every job card it returns. Any LinkedIn result located in Kenya raised an
uncaught `ValueError` that killed the *entire* batch for that search term,
not just the one job. Confirmed by installing `python-jobspy` (1.1.82,
current) and reproducing the exact traceback from your logs.

Fix: `job_scraper/jobspy_patch.py` replaces `LinkedIn._get_location` with
a version that falls back to the raw location text instead of raising,
applied once at startup (`main.py`). It deliberately leaves
`Country.from_string` and the `country_indeed` request-time validation
untouched, so a genuinely bad entry in `INDEED_COUNTRIES` still fails
loudly. Full write-up is in the module's docstring.

**2. Found and fixed a second, related bug.** Pandas returns `NaN` (a
float) for a missing column, not `None` — and `NaN` is truthy in Python,
so the original `if not job_url:` check didn't actually catch a missing
`job_url`. That job would flow through, get added to `sent_urls`, and
crash `save_sent_urls()` on `sorted()` the next time it tried to compare
a float to strings — *after* a full scrape had already run. Fixed with
`job_utils.clean_field()`, which normalizes `NaN`/`None` consistently
before any dedupe/filter check runs. Reproduced and verified fixed in
testing.

**3. Hardened error handling:**
- `storage.load_sent_urls()` now validates the file actually contains a
  list of strings, not just that it's parseable JSON — a corrupted file
  that parsed as e.g. `{}` used to pass silently through as an empty set
  either way, but now it's logged explicitly instead of silently assumed.
- `sources/remoteok.py` validates the API response is a list before
  indexing into it, and skips non-dict entries instead of raising on a
  malformed listing.
- `jobspy_patch.apply()` fails soft — if jobspy's internals change shape
  in a future release, it logs and leaves jobspy unpatched rather than
  crashing startup.

Everything above was actually tested (not just written) — see the bottom
of this file for how to re-run those checks.

## New structure

```
main.py                          <- FastAPI app (thin) -- entrypoint unchanged: `uvicorn main:app`
job_scraper/
  config.py                      <- every tunable constant, in one place
  logging_setup.py               <- stdout logging setup
  jobspy_patch.py                <- the Kenya-crash fix, with full explanation
  filters.py                     <- role/region filtering (is_senior_role, is_allowed_region, ...)
  job_utils.py                   <- job-dict shaping, NaN-safe field cleaning, dedupe gate
  storage.py                     <- sent-urls persistence (load/save)
  pipeline.py                    <- fetch_new_jobs() orchestrator (tier logic)
  sources/
    linkedin.py                  <- fetch_linkedin_jobs, fetch_kenya_company_jobs
    indeed.py                    <- fetch_indeed_jobs
    remoteok.py                  <- fetch_remoteok_listings, fetch_remoteok_jobs
```

`main.py` stays at the repo root so your existing `uvicorn main:app`
container command doesn't need to change. Just make sure your Dockerfile
copies the whole project (including the `job_scraper/` directory), not
just `main.py` specifically, if it currently does something like
`COPY main.py .`.

Every constant, function name, log message, and piece of behavior is
unchanged from your original `main.py` except where called out above —
this was a reorganization + two bug fixes, not a rewrite.

## Re-running the verification

The exact checks used while building this (jobspy-source install, crash
reproduction, patched-vs-unpatched comparison, full pipeline dry run with
mocked sources including a Kenya-located job, and the NaN edge case) are
straightforward to redo if you want to see them yourself:

```bash
pip install python-jobspy fastapi --break-system-packages
python3 -c "from job_scraper import jobspy_patch, pipeline; ..."  # see chat for the full scripts
```
