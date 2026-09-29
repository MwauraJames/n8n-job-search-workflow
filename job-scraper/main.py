"""FastAPI entrypoint. Thin by design -- all the actual scraping logic
lives in job_scraper/. Kept as main.py at the repo root (rather than moved
into the package) so the existing `uvicorn main:app` container command
doesn't need to change.
"""
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from job_scraper import config, jobspy_patch, pipeline, storage
from job_scraper.logging_setup import configure_logging

logger = configure_logging()
app = FastAPI()


@app.on_event("startup")
def on_startup():
  logger.info("=== job-scraper service starting up ===")
  jobspy_patch.apply()
  logger.info(f"Kenya company tier (searched first, LinkedIn-only): "
              f"{sorted(config.TARGET_KENYA_COMPANIES)} in '{config.KENYA_COMPANY_SEARCH_LOCATION}'")
  logger.info(f"Term tiers: {config.TERM_TIERS}")
  logger.info(
      f"Target job count: {config.TARGET_JOB_COUNT} | Batch size: {config.BATCH_SIZE} | "
      f"Max batches per term: {config.MAX_BATCHES_PER_TERM}"
  )
  logger.info(f"Broad location tags treated as allowed + prioritized: {sorted(config.BROAD_ALLOWED_LOCATION_TAGS)}")
  logger.info("Sources (priority order): kenya-companies -> linkedin -> indeed -> remoteok")
  logger.info(f"Sent-jobs file path: {config.SENT_JOBS_FILE}")
  if not config.SENT_JOBS_FILE.parent.exists():
    logger.warning(
        f"Data directory {config.SENT_JOBS_FILE.parent} does not exist yet "
        "(will be created on first save). Make sure it's a mounted volume "
        "if you want persistence across restarts."
    )


@app.post("/scrape")
def scrape():
  logger.info(">>> /scrape endpoint called")
  start = time.monotonic()
  try:
    sent_urls = storage.load_sent_urls()
    jobs_list = pipeline.fetch_new_jobs(config.TARGET_JOB_COUNT, sent_urls)

    for job in jobs_list:
      sent_urls.add(job["job_url"])
    storage.save_sent_urls(sent_urls)

    elapsed = time.monotonic() - start
    logger.info(f"<<< /scrape completed successfully: {len(jobs_list)} job(s) in {elapsed:.1f}s")
    return {"count": len(jobs_list), "jobs": jobs_list}

  except Exception:
    elapsed = time.monotonic() - start
    logger.exception(f"<<< /scrape FAILED after {elapsed:.1f}s")
    return JSONResponse(
        status_code=500,
        content={"error": "scrape failed, check container logs for details"},
    )


@app.get("/health")
def health():
  logger.debug("Health check hit")
  return {"status": "ok"}
