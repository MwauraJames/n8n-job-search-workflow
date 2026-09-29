"""RemoteOK source: a single public-API fetch (no per-term query, unlike
LinkedIn/Indeed) filtered in-memory against whatever terms are active.
"""
import logging

import requests

from .. import config, filters, job_utils

logger = logging.getLogger("job-scraper")


def fetch_remoteok_listings() -> list:
  """Fetch raw listings from the RemoteOK public API.

  This is a single call that returns ALL current remote listings -- there's
  no per-term query like LinkedIn/Indeed have. pipeline.fetch_new_jobs()
  calls this at most once per run (cached) and reuses the same raw listings
  for both the primary and backup term tiers, so a backup-tier pass never
  re-hits the API for data we already have.
  """
  logger.info("[RemoteOK] --- Fetching from RemoteOK public API ---")
  try:
    resp = requests.get(config.REMOTEOK_API_URL, headers=config.REMOTEOK_HEADERS, timeout=15)
    resp.raise_for_status()
  except requests.RequestException as e:
    logger.error(f"[RemoteOK] API request failed: {e}")
    return []

  try:
    listings = resp.json()
  except ValueError as e:
    logger.error(f"[RemoteOK] API response wasn't valid JSON: {e}")
    return []

  if not isinstance(listings, list):
    logger.error(f"[RemoteOK] API response was a {type(listings).__name__}, expected a list. Treating as empty.")
    return []

  # RemoteOK's response has a legal/meta notice as the first element, not a job
  if listings and isinstance(listings[0], dict) and "legal" in listings[0]:
    listings = listings[1:]

  logger.info(f"[RemoteOK] fetched {len(listings)} raw listings")
  return listings


def fetch_remoteok_jobs(listings: list, terms: list, target_count: int, sent_urls: set, seen_this_run: set, new_jobs: list) -> None:
  if len(new_jobs) >= target_count:
    logger.info("[RemoteOK] Target count already reached, skipping RemoteOK entirely")
    return
  if not listings:
    logger.info("[RemoteOK] No listings available (fetch failed or empty), skipping")
    return

  search_terms_lower = [t.lower() for t in terms]
  stats = job_utils.new_stats()

  matched_jobs = []
  for listing in listings:
    if not isinstance(listing, dict):
      logger.debug(f"[RemoteOK] Skipping malformed listing entry (not an object): {listing!r}")
      continue
    title = listing.get("position") or listing.get("title") or ""
    if not any(term in title.lower() for term in search_terms_lower):
      stats["no_match"] += 1
      continue
    matched_jobs.append({
        "title": job_utils.clean_field(title),
        "company": job_utils.clean_field(listing.get("company")),
        "location": job_utils.clean_field(listing.get("location")) or "",
        "job_url": job_utils.clean_field(listing.get("url") or listing.get("apply_url")),
        "description": job_utils.clean_field(listing.get("description")),
        "source": "remoteok",
    })

  for job in filters.sort_by_location_priority(matched_jobs):
    if len(new_jobs) >= target_count:
      break
    job_utils.try_add_job(job, sent_urls, seen_this_run, new_jobs, target_count, stats)

  job_utils.log_batch_summary("[RemoteOK]", stats, new_jobs, target_count)
