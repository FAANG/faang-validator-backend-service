"""
Per-job idempotency store for BioSamples submission.

BioSamples POST is *not* idempotent — every POST mints a brand-new accession.
So if a submission job is retried or its worker is killed half-way through (and
acks_late re-delivers it), naively re-running would create duplicate samples.

This store records "alias -> accession" in Redis as each sample succeeds, keyed
by the Celery job id. A retried/re-delivered run of the *same job* therefore
skips aliases that already went through and re-uses their accessions, instead of
submitting them again.

Scope is intentionally per-job (the job id is the idempotency key): a retry of
one job is de-duplicated; a brand-new submission is treated as new work.

The submission layer only depends on the small ``seen``/``record`` duck-typed
interface, not on Redis, so it stays decoupled from Celery.
"""
import os
from typing import Optional

import redis

_REDIS_URL = (
    os.environ.get("CELERY_RESULT_BACKEND")
    or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)
# Keep the record well beyond result_expires so a late retry can still de-dup.
_TTL_SECONDS = 7 * 24 * 60 * 60


class RedisIdempotencyStore:
    def __init__(self, job_id: str, client: Optional["redis.Redis"] = None):
        self._client = client or redis.Redis.from_url(_REDIS_URL, decode_responses=True)
        self._key = f"idem:biosamples:{job_id}"

    def seen(self, alias: str) -> Optional[str]:
        """Return the accession already minted for this alias in this job, or None."""
        return self._client.hget(self._key, alias)

    def record(self, alias: str, accession: str) -> None:
        """Durably record that ``alias`` was submitted and got ``accession``."""
        self._client.hset(self._key, alias, accession)
        self._client.expire(self._key, _TTL_SECONDS)
