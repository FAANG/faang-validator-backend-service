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
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
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
    # Let the app's own logging/stdout flow through
    # sys.stdout/stderr inside the worker process
    worker_redirect_stdouts=False,
)
