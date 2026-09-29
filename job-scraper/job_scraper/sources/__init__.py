"""Job sources: linkedin, indeed, remoteok. Each module exposes one or more
fetch_*_jobs(terms, target_count, sent_urls, seen_this_run, new_jobs)
functions with a matching signature, called from pipeline.fetch_new_jobs().
"""
