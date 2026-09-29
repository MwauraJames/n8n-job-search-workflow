"""Shared job-dict shaping and the dedupe/filter gate every source funnels
through before a listing gets added to the run's results.
"""
import logging
import math

from . import filters

logger = logging.getLogger("job-scraper")


def clean_field(value):
  """Normalize a raw value pulled from a scraper's row/dict into either a
  real value or None.

  Pandas DataFrame rows (LinkedIn/Indeed results) return NaN -- a float,
  not None or "" -- for a missing string column. NaN is truthy in Python
  (`not float("nan")` is False), so a bare `if not row.get("job_url")`
  check would silently let a NaN job_url through as if it were present,
  and it would eventually get written into the persisted sent-urls file.
  Every field pulled from a source's raw row/dict should go through this
  before landing in a job dict -- see job_from_row() below.
  """
  if value is None:
    return None
  if isinstance(value, float) and math.isnan(value):
    return None
  return value


def job_from_row(row, source: str) -> dict:
  """Build a job dict from a jobspy result row (a pandas Series), running
  every field through clean_field() so a NaN column can't slip through as
  if it were present. Used by every DataFrame-based source (LinkedIn,
  Indeed) -- RemoteOK builds its own dict since it comes from a raw JSON
  list of plain dicts, not a DataFrame, and doesn't have the NaN issue.
  """
  return {
      "title": clean_field(row.get("title")),
      "company": clean_field(row.get("company")),
      "location": clean_field(row.get("location")) or "",
      "job_url": clean_field(row.get("job_url")),
      "description": clean_field(row.get("description")),
      "source": source,
  }


def new_stats() -> dict:
  return {"added": 0, "dupe": 0, "senior": 0, "wrong_region": 0, "no_url": 0, "no_match": 0}


def try_add_job(job: dict, sent_urls: set, seen_this_run: set, new_jobs: list, target_count: int, stats: dict, region_verified: bool = False) -> None:
  """Shared filter/append logic used by every job source, so dedupe and
  senior-role filtering stay consistent no matter where a listing came from.

  region_verified=True skips the location-text region check entirely, for
  sources where the region is already guaranteed by how the query itself was
  built (e.g. Indeed's country_indeed=X), rather than something that has to
  be parsed out of a free-text `location` string. Indeed's Germany results,
  for example, often come back with location text like "Berlin, Deutschland"
  -- the country name is guaranteed by which Indeed site was queried, but a
  plain English "germany" string search on that text would never match.
  """
  if len(new_jobs) >= target_count:
    return

  job_url = clean_field(job.get("job_url"))
  title = clean_field(job.get("title")) or ""
  location = clean_field(job.get("location")) or ""

  if not job_url:
    stats["no_url"] += 1
    return
  if job_url in sent_urls or job_url in seen_this_run:
    stats["dupe"] += 1
    return
  if filters.is_senior_role(title):
    stats["senior"] += 1
    return
  if not region_verified and not filters.is_allowed_region(location):
    stats["wrong_region"] += 1
    logger.debug(f"Filtering out job outside allowed regions (location='{location}'): {title}")
    return

  seen_this_run.add(job_url)
  new_jobs.append(job)
  stats["added"] += 1


def log_batch_summary(prefix: str, stats: dict, new_jobs: list, target_count: int) -> None:
  logger.info(
      f"{prefix} summary: +{stats['added']} added, {stats['dupe']} dupes skipped, "
      f"{stats['senior']} senior-role skipped, {stats['wrong_region']} outside allowed regions, "
      f"{stats['no_url']} missing url, {stats['no_match']} title mismatch | "
      f"running total={len(new_jobs)}/{target_count}"
  )
