"""Loading/saving the set of job URLs we've already sent, persisted on a
mounted volume so it survives container restarts.
"""
import json
import logging

from . import config

logger = logging.getLogger("job-scraper")


def load_sent_urls() -> set:
  path = config.SENT_JOBS_FILE
  if not path.exists():
    logger.info(f"No existing sent-urls file at {path}; starting fresh")
    return set()

  try:
    raw = json.loads(path.read_text())
  except (json.JSONDecodeError, OSError) as e:
    logger.error(f"Failed to read/parse {path}: {e}. Starting with empty set.")
    return set()

  if not isinstance(raw, list):
    logger.error(
        f"{path} contained a {type(raw).__name__}, expected a list of URLs. "
        "Starting with empty set instead of trusting a malformed file."
    )
    return set()

  urls = {u for u in raw if isinstance(u, str)}
  dropped = len(raw) - len(urls)
  if dropped:
    logger.warning(f"{path} contained {dropped} non-string entr{'y' if dropped == 1 else 'ies'}; dropped them")

  logger.info(f"Loaded {len(urls)} previously-sent job URLs from {path}")
  return urls


def save_sent_urls(sent_urls: set) -> None:
  path = config.SENT_JOBS_FILE
  try:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(sent_urls), indent=2))
    logger.info(f"Saved {len(sent_urls)} sent job URLs to {path}")
  except OSError as e:
    logger.error(f"Failed to write {path}: {e}")
    raise
