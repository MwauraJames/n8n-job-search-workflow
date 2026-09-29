"""Location + role filtering shared by every source. Nothing here reaches
out to a network or mutates result lists -- see job_utils.try_add_job for
where these get applied to an actual job dict.
"""
import logging
import re

from . import config

logger = logging.getLogger("job-scraper")

_EXCLUDE_KEYWORDS = [kw.strip() for kw in config.EXCLUDE_KEYWORDS]


def is_senior_role(title: str) -> bool:
  title_lower = (title or "").lower()
  for kw in _EXCLUDE_KEYWORDS:
    if re.search(rf"\b{re.escape(kw)}\b", title_lower):
      logger.debug(f"Filtering out senior-level title (matched '{kw}'): {title}")
      return True
  return False


def is_broad_remote_location(location: str) -> bool:
  """True if `location` uses a broad "open to anywhere" tag (Worldwide,
  EMEA) rather than a specific country.

  Used two ways: is_allowed_region() below treats a match as allowed, and
  sort_by_location_priority() sorts these to the front of a batch so they
  get first claim on the target-count slots -- the actual "prioritize"
  behavior, not just inclusion.
  """
  location_lower = (location or "").lower()
  return any(
      re.search(rf"\b{re.escape(tag)}\b", location_lower)
      for tag in config.BROAD_ALLOWED_LOCATION_TAGS
  )


def is_allowed_region(location: str) -> bool:
  """True if `location` mentions a North America / Europe / Africa country,
  or an explicit broad tag like "Worldwide" / "EMEA".

  A genuinely blank/ambiguous location (no country, no broad tag at all --
  common on RemoteOK) is still treated as NOT allowed, since we can't
  confirm anything from it. "Worldwide" and "EMEA" are different: they're
  an intentional statement from the poster, not an absence of info, so
  they're recognized here same as any listed country.
  """
  if not location:
    return False
  location_lower = location.lower()
  if is_broad_remote_location(location_lower):
    return True
  for country in config.ALLOWED_REGION_COUNTRIES:
    if re.search(rf"\b{re.escape(country)}\b", location_lower):
      return True
  return False


def sort_by_location_priority(jobs: list) -> list:
  """Stable-sort a list of job dicts so Worldwide/EMEA-tagged listings come
  first. Doesn't drop or reorder anything else -- ties keep their original
  (source) order. Called right before the try_add_job loop in each fetcher
  so that, within any single batch, broad-location jobs get evaluated
  before country-specific ones for the remaining target-count slots.
  """
  return sorted(jobs, key=lambda j: 0 if is_broad_remote_location(j.get("location", "")) else 1)
