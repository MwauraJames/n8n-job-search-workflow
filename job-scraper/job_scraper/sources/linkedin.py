"""LinkedIn sources: the general role search (fetch_linkedin_jobs) and the
Kenya-tech-employer search (fetch_kenya_company_jobs).

Both rely on jobspy_patch.apply() having already run (see main.py's startup
event) so a Kenya-located result doesn't crash the whole batch -- see
jobspy_patch.py for the full explanation of that bug.
"""
import logging
import time

from jobspy import scrape_jobs

from .. import config, filters, job_utils

logger = logging.getLogger("job-scraper")


def fetch_linkedin_jobs(terms: list, target_count: int, sent_urls: set, seen_this_run: set, new_jobs: list) -> None:
  for term in terms:
    if len(new_jobs) >= target_count:
      logger.info(f"[LinkedIn] Target count reached before searching '{term}', skipping remaining terms")
      break

    logger.info(f"[LinkedIn] --- Searching term: '{term}' ---")
    offset = 0
    for batch_num in range(1, config.MAX_BATCHES_PER_TERM + 1):
      if len(new_jobs) >= target_count:
        break

      logger.info(
          f"[LinkedIn/{term}] batch {batch_num}/{config.MAX_BATCHES_PER_TERM} "
          f"(offset={offset}, results_wanted={config.BATCH_SIZE})"
      )

      try:
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term=term,
            location="Remote",
            results_wanted=config.BATCH_SIZE,
            offset=offset,
            hours_old=24,
            linkedin_fetch_description=True,
        )
      except Exception:
        logger.exception(
            f"[LinkedIn] scrape_jobs() raised an exception for term='{term}' offset={offset}. "
            "Skipping to next term."
        )
        break

      offset += config.BATCH_SIZE

      if jobs is None or jobs.empty:
        logger.warning(f"[LinkedIn/{term}] batch {batch_num} returned 0 results, stopping this term")
        break

      logger.info(f"[LinkedIn/{term}] batch {batch_num} returned {len(jobs)} raw results")

      batch_jobs = [job_utils.job_from_row(row, source="linkedin") for _, row in jobs.iterrows()]

      stats = job_utils.new_stats()
      for job in filters.sort_by_location_priority(batch_jobs):
        if len(new_jobs) >= target_count:
          break
        job_utils.try_add_job(job, sent_urls, seen_this_run, new_jobs, target_count, stats)

      job_utils.log_batch_summary(f"[LinkedIn/{term}] batch {batch_num}", stats, new_jobs, target_count)

      # A short batch means the source is out of results for this query --
      # further offset batches would almost certainly come back empty, so
      # stop this term now instead of burning another call + sleep on it.
      exhausted = len(jobs) < config.BATCH_SIZE

      # Only pace with a sleep if we're actually about to make another
      # request. If the target is already met, everything downstream is
      # skipped entirely, so sleeping here would just be wasted time.
      if len(new_jobs) < target_count:
        logger.debug(f"[LinkedIn/{term}] sleeping {config.LINKEDIN_BATCH_SLEEP_SECONDS}s before next request")
        time.sleep(config.LINKEDIN_BATCH_SLEEP_SECONDS)

      if exhausted:
        logger.info(f"[LinkedIn/{term}] batch {batch_num} returned fewer results than requested "
                     f"({len(jobs)}<{config.BATCH_SIZE}); likely no more results for this term, moving on")
        break


def is_target_kenya_company(company: str) -> bool:
  company_lower = (company or "").lower()
  return any(name in company_lower for name in config.TARGET_KENYA_COMPANIES)


def fetch_kenya_company_jobs(terms: list, target_count: int, sent_urls: set, seen_this_run: set, new_jobs: list) -> None:
  """Search LinkedIn with location="Kenya" for postings at the specific
  employers in config.TARGET_KENYA_COMPANIES.

  LinkedIn-only: jobspy's Indeed scraper needs a `country_indeed` value to
  pick a regional domain, and Kenya isn't in its supported country list
  (see config.INDEED_COUNTRIES) -- there's no Indeed-Kenya domain for it to
  query. LinkedIn has no such restriction; it searches globally off the
  `location` string directly, so "Kenya" works the same as "Remote" does
  elsewhere in this file. (This search used to also crash on exactly these
  results for a different reason -- see jobspy_patch.py.)

  Runs across every term (primary + backup combined) in one pass, since the
  employer match is already the narrow filter here -- there's no need to
  also gate on role tier.
  """
  if len(new_jobs) >= target_count:
    logger.info("[Kenya companies] Target count already reached, skipping entirely")
    return

  logger.info(f"[Kenya companies] --- Searching {sorted(config.TARGET_KENYA_COMPANIES)} in "
              f"'{config.KENYA_COMPANY_SEARCH_LOCATION}' across terms: {terms} ---")

  for term in terms:
    if len(new_jobs) >= target_count:
      break

    logger.info(f"[Kenya companies/{term}] querying LinkedIn (location='{config.KENYA_COMPANY_SEARCH_LOCATION}', "
                f"results_wanted={config.BATCH_SIZE})")

    try:
      jobs = scrape_jobs(
          site_name=["linkedin"],
          search_term=term,
          location=config.KENYA_COMPANY_SEARCH_LOCATION,
          results_wanted=config.BATCH_SIZE,
          hours_old=24,
          linkedin_fetch_description=True,
      )
    except Exception:
      logger.exception(f"[Kenya companies] scrape_jobs() raised an exception for term='{term}'")
      if len(new_jobs) < target_count:
        time.sleep(config.LINKEDIN_BATCH_SLEEP_SECONDS)
      continue

    if jobs is None or jobs.empty:
      logger.info(f"[Kenya companies/{term}] returned 0 results")
      if len(new_jobs) < target_count:
        time.sleep(config.LINKEDIN_BATCH_SLEEP_SECONDS)
      continue

    logger.info(f"[Kenya companies/{term}] returned {len(jobs)} raw results")

    stats = job_utils.new_stats()
    for _, row in jobs.iterrows():
      if len(new_jobs) >= target_count:
        break
      job = job_utils.job_from_row(row, source="linkedin-kenya")
      if not is_target_kenya_company(job.get("company")):
        stats["no_match"] += 1
        continue
      # region_verified=True: this query already targeted Kenya directly
      job_utils.try_add_job(job, sent_urls, seen_this_run, new_jobs, target_count, stats, region_verified=True)

    job_utils.log_batch_summary(f"[Kenya companies/{term}]", stats, new_jobs, target_count)

    if len(new_jobs) < target_count:
      time.sleep(config.LINKEDIN_BATCH_SLEEP_SECONDS)
