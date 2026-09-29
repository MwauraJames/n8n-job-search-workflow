"""Orchestrates a full run: Kenya-company tier, then each role tier
(primary, then backup) across LinkedIn -> Indeed -> RemoteOK, stopping as
soon as config.TARGET_JOB_COUNT new jobs have been found.
"""
import logging

from . import config
from .sources import indeed, linkedin, remoteok

logger = logging.getLogger("job-scraper")


def fetch_new_jobs(target_count: int, sent_urls: set) -> list:
  new_jobs = []
  seen_this_run = set()
  remoteok_listings = None  # fetched lazily, at most once per run

  logger.info(f"Starting job fetch: target={target_count}, already-sent={len(sent_urls)}")

  # Kenya company tier runs first, across every role term at once -- a hit
  # here is worth more than a generic remote match, so it gets first shot
  # at the target count before the role tiers below even start.
  linkedin.fetch_kenya_company_jobs(
      config.PRIMARY_SEARCH_TERMS + config.BACKUP_SEARCH_TERMS,
      target_count, sent_urls, seen_this_run, new_jobs,
  )

  for tier_name, terms in config.TERM_TIERS:
    if len(new_jobs) >= target_count:
      logger.info(f"Target already reached, skipping '{tier_name}' tier {terms}")
      break

    logger.info(f"=== Starting '{tier_name}' tier: {terms} ===")

    # Source priority within a tier: LinkedIn first, then Indeed, then
    # RemoteOK -- each function already no-ops immediately if the target
    # was hit by the source before it.
    linkedin.fetch_linkedin_jobs(terms, target_count, sent_urls, seen_this_run, new_jobs)
    indeed.fetch_indeed_jobs(terms, target_count, sent_urls, seen_this_run, new_jobs)

    if len(new_jobs) < target_count:
      if remoteok_listings is None:
        remoteok_listings = remoteok.fetch_remoteok_listings()
      remoteok.fetch_remoteok_jobs(remoteok_listings, terms, target_count, sent_urls, seen_this_run, new_jobs)
    else:
      logger.info("[RemoteOK] Target count already reached, skipping RemoteOK entirely")

    if len(new_jobs) < target_count and tier_name == "primary":
      logger.info(
          f"Primary tier {config.PRIMARY_SEARCH_TERMS} did not fill the target across any source "
          f"({len(new_jobs)}/{target_count}) -- falling back to backup roles {config.BACKUP_SEARCH_TERMS}"
      )

  by_source = {}
  for job in new_jobs:
    by_source[job.get("source", "unknown")] = by_source.get(job.get("source", "unknown"), 0) + 1
  logger.info(f"Job fetch complete: {len(new_jobs)} new job(s) found | by source: {by_source}")
  return new_jobs
