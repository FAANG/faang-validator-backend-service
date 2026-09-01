import requests


class RetryableSubmissionError(Exception):
    """A submission failed for a transient reason (network drop / timeout /
    upstream 5xx) and is therefore safe to retry."""


RETRYABLE_EXCEPTIONS = (
    RetryableSubmissionError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)

# curl exit codes - (6 host resolve, 7 connect, 28 timeout,
# 35 SSL connect, 52 empty reply, 55 send error, 56 recv error.)
TRANSIENT_CURL_EXIT_CODES = {6, 7, 28, 35, 52, 55, 56}
