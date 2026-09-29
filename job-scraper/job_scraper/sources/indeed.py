"""Indeed source: one query per (term, country) pair across
config.INDEED_COUNTRIES, since jobspy's Indeed scraper needs a single
country_indeed value per call (unlike LinkedIn's global search).
"""
import logging
import time

from jobspy import scrape_jobs

from .. import config, filters, job_utils

logger = logging.getLogger("job-scraper")


def fetch_indeed_jobs(terms: list, target_count: int, sent_urls: set, seen_this_run: set, new_jobs: list) -> None:
  if len(new_jobs) >= target_count:
    logger.info("[Indeed] Target count already reached, skipping Indeed entirely")
    return

  logger.info("[Indeed] --- Starting Indeed search across target-region countries ---")
  for term in terms:
    if len(new_jobs) >= target_count:
      break
    for country in config.INDEED_COUNTRIES:
      if len(new_jobs) >= target_count:
        break

      logger.info(f"[Indeed] term='{term}' country='{country}' (results_wanted={config.BATCH_SIZE})")

      try:
        jobs = scrape_jobs(
            site_name=["indeed"],
            search_term=term,
            location="Remote",
            results_wanted=config.BATCH_SIZE,
            hours_old=24,
            country_indeed=country,
        )
      except Exception:
        logger.exception(f"[Indeed] scrape_jobs() raised an exception for term='{term}' country='{country}'")
        if len(new_jobs) < target_count:
          time.sleep(config.INDEED_QUERY_SLEEP_SECONDS)
        continue

      if jobs is None or jobs.empty:
        logger.info(f"[Indeed/{term}/{country}] returned 0 results")
        if len(new_jobs) < target_count:
          time.sleep(config.INDEED_QUERY_SLEEP_SECONDS)
        continue

      logger.info(f"[Indeed/{term}/{country}] returned {len(jobs)} raw results")

      batch_jobs = [job_utils.job_from_row(row, source="indeed") for _, row in jobs.iterrows()]

      stats = job_utils.new_stats()
      for job in filters.sort_by_location_priority(batch_jobs):
        if len(new_jobs) >= target_count:
          break
        # region_verified=True: country_indeed already guarantees this job is
        # from an allowed-region country, no need to text-match `location`
        job_utils.try_add_job(job, sent_urls, seen_this_run, new_jobs, target_count, stats, region_verified=True)

      job_utils.log_batch_summary(f"[Indeed/{term}/{country}]", stats, new_jobs, target_count)

      if len(new_jobs) < target_count:
        time.sleep(config.INDEED_QUERY_SLEEP_SECONDS)
