"""
Celery application for the FAANG submission service.

Validation stays inside FastAPI (it is fast, I/O-bound fan-out that asyncio
handles well). Only *submission* — the long-running, state-changing,
failure-sensitive work — is moved onto a durable background queue.

Broker + result backend are both Redis. RabbitMQ is NOT required: Redis is a
perfectly good Celery broker for this workload. Swap REDIS_URL for a RabbitMQ
URL only if/when submission volume needs stronger queue semantics.
"""
import os

from celery import Celery

# Single Redis instance acts as both broker and result/state backend.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)

celery_app = Celery(
    "faang_submission",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["app.tasks.submission_tasks"],
)

celery_app.conf.update(
    # JSON only — never pickle (credentials travel through the broker).
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Report a STARTED state so the status endpoint can show "running".
    task_track_started=True,
    # Keep job state around for a day so the frontend can poll the result.
    result_expires=60 * 60 * 24,
    # acks_late + prefetch=1: a crashed worker re-queues the job instead of
    # losing it, and one heavy submission per worker at a time.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    # Do NOT persist task args (they contain Webin credentials) in results.
    result_extended=False,
    # Let the app's own logging/stdout flow through instead of Celery hijacking
    # sys.stdout/stderr inside the worker process.
    worker_redirect_stdouts=False,
)
