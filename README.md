# FAANG Validator Backend Service

A FastAPI-based microservice for validating FAANG data.

## Features

- Single API endpoint that returns a welcome message
- Containerized with Docker for easy deployment
- Built with FastAPI for high performance and automatic API documentation

## Requirements

- Python 3.9+
- FastAPI
- Uvicorn
- Docker (for containerized deployment)

## Running Locally

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/faang-validator-backend-service.git
   cd faang-validator-backend-service
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python app.main.py
   ```

   Alternatively, you can use Uvicorn directly:
   ```
   uvicorn app.main:app --reload
   ```

4. Access the API at http://localhost:8000

## Docker Deployment

1. Build the Docker image:
   ```
   docker build -t faang-validator-api .
   ```

2. Run the container:
   ```
   docker run -p 8000:8000 faang-validator-api
   ```

3. Access the API at http://localhost:8000

## API Documentation

Once the application is running, you can access the automatic API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### GET /

Returns a welcome message and status.

**Response Example:**
```json
{
  "message": "Welcome to FAANG Validator API",
  "status": "operational"
}
```

## Submission: durable background jobs (Celery + Redis)

Validation runs inside FastAPI (fast, I/O-bound async fan-out). **Submission** —
the long-running, state-changing, failure-sensitive work — runs on a durable
background queue so large batches survive load-balancer timeouts and worker
restarts, get retried on transient ENA/BioSamples failures, and report progress.

The broker and result/state backend are both **Redis**. **RabbitMQ is not
required** — Redis is sufficient for this workload.

### Architecture

```
            validate (in-request, async)        submit (background, durable)
Frontend ─► FastAPI ──────────────────────►  FastAPI ─► Redis queue ─► Celery worker ─► ENA / BioSamples
                                                 │                          │
                                                 └──── returns job_id ◄──────┘ (progress + result in Redis)
```

### Running it

```bash
docker compose up --build      # starts redis + api + worker together
```

Or locally, in three terminals:

```bash
export REDIS_URL=redis://localhost:6379/0
redis-server                                                   # 1. broker
uvicorn app.main:app --host 0.0.0.0 --port 8000                # 2. api
celery -A app.celery_app.celery_app worker --loglevel=info     # 3. worker
```

### Async submission endpoints

The original synchronous endpoints (`/submit-to-biosamples`, `/submit-experiment`,
`/submit-analysis`) are unchanged. The async variants enqueue a job and return
immediately:

- `POST /submit-to-biosamples-async`
- `POST /submit-experiment-async`
- `POST /submit-analysis-async`

Each returns a job id:

```json
{ "job_id": "abc123", "status": "queued", "message": "Submission queued. Poll ..." }
```

Poll for progress and the final result:

```
GET /submission-jobs/{job_id}
```

```json
{ "job_id": "abc123", "status": "running", "stage": "submitting", "submitted": 250, "total": 1000 }
```

`status` is one of `queued | running | retrying | complete | failed`. On
`complete`, the original submitter result is returned under `result`.

A job is reported as **`failed`** in two cases: the task raised and exhausted
its retries (Celery `FAILURE`), **or** the task finished but the submission
itself was rejected (e.g. a 4xx from ENA/BioSamples — the submitter returns
`success: false`). In both cases `error` holds the summary and `errors` the
detail list; the full `result` (including any partial accessions) is still
returned. Always check `status` rather than assuming a finished task succeeded.

### Retry semantics

Submission tasks **auto-retry transient failures** with exponential backoff
(1s, 2s, 4s … capped at 2 min, with jitter), up to 5 attempts. "Transient"
means the work could succeed on a retry:

- a dropped connection / timeout (`requests` `ConnectionError` / `Timeout`),
- an upstream **5xx** from BioSamples,
- `curl` failing to reach ENA (connect/timeout exit codes).

A validation error or a **4xx** rejection is *not* retried — it would just fail
again — and is returned as a permanent failure.

Retries are safe because of the idempotency guard: BioSamples POST is not
idempotent, so each submitted sample's accession is recorded in Redis (keyed by
job id) the moment it succeeds. A retry — or a worker crash + `acks_late`
re-delivery — skips samples that already went through instead of duplicating
them. The synchronous endpoints keep their original behaviour (transient errors
are reported in the response, not raised).

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + result backend |
| `CELERY_BROKER_URL` | falls back to `REDIS_URL` | Override broker only |
| `CELERY_RESULT_BACKEND` | falls back to `REDIS_URL` | Override result backend only |
