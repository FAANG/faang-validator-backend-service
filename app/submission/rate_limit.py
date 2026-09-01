import os
import time
import random
import logging
import threading
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import requests

from app.submission.retryable import RetryableSubmissionError

logger = logging.getLogger(__name__)
TRANSIENT_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RPS = float(os.environ.get("BIOSAMPLES_MAX_RPS", "10"))
_MAX_RETRIES = int(os.environ.get("BIOSAMPLES_RATE_LIMIT_MAX_RETRIES", "5"))
_MAX_BACKOFF = float(os.environ.get("BIOSAMPLES_RATE_LIMIT_MAX_BACKOFF", "60"))


class RateLimiter:

    def __init__(self, max_rps: float = _MAX_RPS):
        self._min_interval = 1.0 / max_rps if max_rps > 0 else 0.0
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            sleep_for = self._next_allowed - now
            if sleep_for > 0:
                time.sleep(sleep_for)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval


def _retry_after_seconds(response: requests.Response, attempt: int) -> float:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), _MAX_BACKOFF)
        except (TypeError, ValueError):
            try:
                retry_dt = parsedate_to_datetime(header)
                if retry_dt.tzinfo is None:
                    retry_dt = retry_dt.replace(tzinfo=timezone.utc)
                delta = (retry_dt - datetime.now(timezone.utc)).total_seconds()
                return max(0.0, min(delta, _MAX_BACKOFF))
            except (TypeError, ValueError):
                pass
    backoff = min(2 ** attempt, _MAX_BACKOFF)
    return backoff * (0.5 + random.random() / 2.0)


def request_with_retry(method, url, *, limiter, headers_provider=None,
                       raise_on_transient=False, **kwargs):
    kwargs.setdefault("timeout", 60)
    total_attempts = _MAX_RETRIES + 1
    last_response = None

    for attempt in range(total_attempts):
        limiter.wait()
        if headers_provider is not None:
            kwargs["headers"] = headers_provider()
        try:
            response = requests.request(method, url, **kwargs)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as exc:
            logger.warning("Network error on %s %s (attempt %d/%d): %s",
                           method, url, attempt + 1, total_attempts, exc)
            if attempt < _MAX_RETRIES:
                time.sleep(min(2 ** attempt, _MAX_BACKOFF))
                continue
            if raise_on_transient:
                raise RetryableSubmissionError(f"{method} {url} failed: {exc}") from exc
            raise

        if response.status_code not in TRANSIENT_HTTP_STATUS_CODES:
            return response  # success or error

        last_response = response  # transient
        if attempt < _MAX_RETRIES:
            wait_s = _retry_after_seconds(response, attempt)
            logger.warning(
                "Transient %s from %s %s (attempt %d/%d); retrying in %.1fs. "
                "Retry-After=%s body=%.200r",
                response.status_code, method, url, attempt + 1, total_attempts,
                wait_s, response.headers.get("Retry-After"),
                (response.text or "")[:200],
            )
            time.sleep(wait_s)
            continue
        logger.error("Still transient %s from %s %s after %d retries",
                     response.status_code, method, url, _MAX_RETRIES)

    if raise_on_transient:
        raise RetryableSubmissionError(
            f"{method} {url} still transient ({last_response.status_code}) "
            f"after {_MAX_RETRIES} retries")
    return last_response
