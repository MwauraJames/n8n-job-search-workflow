"""Patches a real limitation in jobspy (python-jobspy on PyPI, verified
against 1.1.82), not a bug in this codebase.

jobspy's `Country` enum (jobspy/model.py) only recognizes a fixed list of
countries -- the same list jobspy documents as its Indeed/Glassdoor country
support. Kenya isn't on it. That's expected and fine for the `country_indeed`
request parameter (see config.INDEED_COUNTRIES, which never includes Kenya
for exactly this reason) -- but LinkedIn's own result parser,
`LinkedIn._get_location()` (jobspy/linkedin/__init__.py), *also* calls
`Country.from_string()`, to turn each returned job card's own location text
(e.g. "Nairobi, Nairobi County, Kenya") into a structured `Location.country`
value. If that text names a country jobspy doesn't recognize, `from_string`
raises `ValueError`, which propagates all the way up through jobspy's
thread pool and kills every result for that entire search term -- not just
the one job whose location it couldn't parse.

Concretely: any LinkedIn search whose results include a Kenya-located job
(guaranteed for our own Kenya-company search, possible for the general
"Remote" search too) can silently lose the whole batch. That's what produced
the "Invalid country string: 'kenya'" errors seen in the logs.

Fix: replace LinkedIn._get_location with a version that catches that
specific failure and falls back to the raw location text instead of
raising. `Location.country` is typed as `Country | str | None`, and
jobspy's own `display_location()` already knows how to render a plain
string there, so a job from an unrecognized country still comes through
with its location intact -- it just won't be a `Country` enum member.

This deliberately does NOT touch `Country.from_string` itself, or the
`country_indeed` request-time validation in jobspy's top-level
`scrape_jobs()` (jobspy/__init__.py) -- a genuinely invalid entry in
config.INDEED_COUNTRIES should keep failing loudly and immediately, not be
silently swallowed. The patch only widens the one call site that's parsing
*results*, not the one validating a *request*.

Written against jobspy 1.1.82's LinkedIn._get_location. If a future jobspy
release restructures that method, apply() below will catch the resulting
ImportError/AttributeError, log it, and leave jobspy unpatched rather than
fail startup -- check the installed jobspy version if Kenya-location
crashes reappear in the logs after an upgrade.
"""
import logging

logger = logging.getLogger("job-scraper")

_patched = False


def apply() -> None:
  """Install the patch. Idempotent -- safe to call more than once, and
  cheap enough to call unconditionally at startup, before the first
  scrape_jobs() call (see main.py's startup event).
  """
  global _patched
  if _patched:
    return

  try:
    import importlib.metadata
    from typing import Optional
    from bs4.element import Tag
    from jobspy.linkedin import LinkedIn
    from jobspy.model import Country, Location
  except ImportError:
    logger.exception(
        "Could not import jobspy internals -- patch NOT applied, "
        "Kenya-located LinkedIn results may still crash a batch"
    )
    return

  def _safe_country(country_str: str):
    try:
      return Country.from_string(country_str)
    except ValueError:
      logger.debug(
          f"[LinkedIn] jobspy doesn't recognize country '{country_str}' -- "
          "keeping the raw text instead of dropping the whole batch over it"
      )
      return (country_str or "").strip().lower() or None

  def _get_location_tolerant(self, metadata_card: "Optional[Tag]") -> "Location":
    location = Location(country=_safe_country(self.country))
    if metadata_card is not None:
      location_tag = metadata_card.find("span", class_="job-search-card__location")
      location_string = location_tag.text.strip() if location_tag else "N/A"
      parts = location_string.split(", ")
      if len(parts) == 2:
        city, state = parts
        location = Location(city=city, state=state, country=_safe_country(self.country))
      elif len(parts) == 3:
        city, state, country = parts
        location = Location(city=city, state=state, country=_safe_country(country))
    return location

  try:
    LinkedIn._get_location = _get_location_tolerant
  except Exception:
    logger.exception(
        "Failed to apply jobspy LinkedIn patch -- Kenya-located LinkedIn "
        "results may still crash a batch"
    )
    return

  try:
    jobspy_version = importlib.metadata.version("python-jobspy")
  except importlib.metadata.PackageNotFoundError:
    jobspy_version = "unknown"

  _patched = True
  logger.info(
      "Applied jobspy patch: LinkedIn._get_location() no longer raises on "
      f"countries jobspy's enum doesn't recognize (e.g. Kenya) "
      f"[jobspy version: {jobspy_version}]"
  )
