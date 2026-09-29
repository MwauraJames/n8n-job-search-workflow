"""Central logging configuration, so every module in this package just does
`logger = logging.getLogger("job-scraper")` and gets the same stdout-based
setup that main.py configures once at startup.
"""
import logging
import os
import sys

LOGGER_NAME = "job-scraper"

_configured = False


def configure_logging() -> logging.Logger:
  """Configure the "job-scraper" logger to stream to stdout, so
  `docker logs <container>` picks it up. Set LOG_LEVEL=DEBUG in the
  container env for more verbose output. Idempotent -- safe to call more
  than once (e.g. from a test), only configures handlers the first time.
  """
  global _configured
  if not _configured:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    _configured = True
  return logging.getLogger(LOGGER_NAME)
