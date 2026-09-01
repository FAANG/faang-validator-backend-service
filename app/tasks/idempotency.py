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
        return self._client.hget(self._key, alias)

    def record(self, alias: str, accession: str) -> None:
        self._client.hset(self._key, alias, accession)
        self._client.expire(self._key, _TTL_SECONDS)
