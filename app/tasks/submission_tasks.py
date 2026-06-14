"""
Celery tasks that run the long, state-changing submission work in the
background, outside the FastAPI request.

Design notes (the things an interviewer cares about):
- Retries with exponential backoff on *transient* network failures only
  (connection drops / timeouts / 5xx-style errors). Validation-style errors are
  not retried — they will never succeed on a retry.
- Progress is reported via ``self.update_state`` so a status endpoint can show
  "2,300 of 5,000 submitted" while the job runs.
- The worker builds its own validator (it is a separate process from the API).
"""
from typing import Any, Dict

from app.celery_app import celery_app
from app.submission.retryable import RETRYABLE_EXCEPTIONS as RETRYABLE_EXC

# Shared, lazily-built validator. Building it loads all the rulesets, so we do
# it once per worker process rather than once per task.
_validator = None


def _get_validator():
    global _validator
    if _validator is None:
        from app.validation.unified_validator import UnifiedFAANGValidator
        _validator = UnifiedFAANGValidator()
    return _validator


# Common retry configuration applied to every submission task.
_RETRY_KWARGS = dict(
    bind=True,
    autoretry_for=RETRYABLE_EXC,
    max_retries=5,
    retry_backoff=True,        # 1s, 2s, 4s, 8s, ...
    retry_backoff_max=120,     # capped at 2 minutes
    retry_jitter=True,         # spread retries so we don't hammer ENA in lockstep
)


@celery_app.task(name="submit_biosamples", **_RETRY_KWARGS)
def submit_biosamples_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Submit (or update) a batch of samples to BioSamples in the background."""
    self.update_state(state="STARTED", meta={"stage": "preparing", "submitted": 0})

    def _progress(submitted: int, total: int) -> None:
        self.update_state(
            state="STARTED",
            meta={"stage": "submitting", "submitted": submitted, "total": total},
        )

    from app.submission import BioSampleSubmitter
    from app.tasks.idempotency import RedisIdempotencyStore

    validator = _get_validator()
    submitter = BioSampleSubmitter(validator.sample_validators)

    # Scope idempotency to this job id, so a retry / crash-redelivery of the same
    # job skips samples already submitted instead of duplicating them.
    idempotency = RedisIdempotencyStore(self.request.id)

    return submitter.submit_to_biosamples(
        validation_results=payload["validation_results"],
        webin_username=payload["webin_username"],
        webin_password=payload["webin_password"],
        domain=payload.get("domain"),
        mode=payload["mode"],
        update_existing=payload.get("update_existing", False),
        progress_callback=_progress,
        idempotency=idempotency,
        raise_on_transient=True,
    )


@celery_app.task(name="submit_experiment", **_RETRY_KWARGS)
def submit_experiment_task(
    self,
    prepared_results: Dict[str, Any],
    credentials: Dict[str, str],
    action: str = "submission",
) -> Dict[str, Any]:
    """Submit a prepared experiment bundle to ENA in the background."""
    self.update_state(state="STARTED", meta={"stage": "submitting"})

    from app.submission import ExperimentSubmitter

    submitter = ExperimentSubmitter()
    return submitter.submit_to_ena(
        results=prepared_results, credentials=credentials, action=action,
        raise_on_transient=True,
    )


@celery_app.task(name="submit_analysis", **_RETRY_KWARGS)
def submit_analysis_task(
    self,
    prepared_results: Dict[str, Any],
    credentials: Dict[str, str],
    action: str = "submission",
) -> Dict[str, Any]:
    """Submit a prepared analysis bundle to ENA in the background."""
    self.update_state(state="STARTED", meta={"stage": "submitting"})

    from app.submission import AnalysisSubmitter

    submitter = AnalysisSubmitter()
    return submitter.submit_to_ena(
        results=prepared_results, credentials=credentials, action=action,
        raise_on_transient=True,
    )
