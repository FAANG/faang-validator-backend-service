"""
Shared definitions of what counts as a *transient* (retryable) submission
failure, so the Celery tasks and the submitters agree on a single source of
truth.

A failure is retryable only if re-running could plausibly succeed: a dropped
connection, a timeout, or an upstream 5xx. A validation error or a 4xx
rejection is NOT retryable — it will fail again no matter how many times we try.
"""
import requests


class RetryableSubmissionError(Exception):
    """A submission failed for a transient reason (network drop / timeout /
    upstream 5xx) and is therefore safe to retry."""


# Passed to Celery's ``autoretry_for`` so these trigger automatic retries.
RETRYABLE_EXCEPTIONS = (
    RetryableSubmissionError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)

# curl exit codes that mean "couldn't reach / talk to ENA" — i.e. the request
# never landed, so retrying is safe. (6 host resolve, 7 connect, 28 timeout,
# 35 SSL connect, 52 empty reply, 55 send error, 56 recv error.)
TRANSIENT_CURL_EXIT_CODES = {6, 7, 28, 35, 52, 55, 56}
