"""ES cache: reads existing update dates from ES, compares with BioSamples data."""
import logging
import os

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

BIOSAMPLES_BASE_URL = "https://www.ebi.ac.uk/biosamples/samples"
BIOSAMPLES_ACCESSIONS_URL = (
    "https://www.ebi.ac.uk/biosamples/accessions"
    "?filter=attr:project:FAANG&size=200&cursor=*"
)
ES_INDICES = ["organism", "specimen"]


def create_es_client() -> Elasticsearch:
    """Create ES client from .env credentials.

    Supports both Elastic Cloud URLs (https://...) and host:port format.
    """
    load_dotenv()
    es_url = os.getenv("ES_URL", "")
    username = os.getenv("ES_USERNAME", "")
    password = os.getenv("ES_PASSWORD", "")

    if es_url:
        # Elastic Cloud: pass URL string with explicit port for elasticsearch-py v7
        from urllib.parse import urlparse

        parsed = urlparse(es_url)
        port = parsed.port or (443 if parsed.scheme == "https" else 9200)
        host_url = f"{parsed.scheme}://{parsed.hostname}:{port}"
        kwargs = {
            "hosts": [host_url],
            "verify_certs": True,
            "timeout": 60,
        }
    else:
        # Legacy host:port format
        host = os.getenv("ES_HOST", "localhost")
        port = int(os.getenv("ES_PORT", "9200"))
        kwargs = {"hosts": [{"host": host, "port": port}], "timeout": 60}

    if username and password:
        kwargs["http_auth"] = (username, password)

    return Elasticsearch(**kwargs)


def fetch_es_update_dates(
    es: Elasticsearch, indices: list[str] | None = None
) -> dict[str, str]:
    """Fetch existing update dates from ES organism and specimen indices.

    Returns: {biosampleId: updateDate}
    """
    from elasticsearch.helpers import scan

    dates: dict[str, str] = {}

    for index_name in indices or ES_INDICES:
        try:
            for hit in scan(
                es,
                index=index_name,
                query={"query": {"match_all": {}}},
                _source=["biosampleId", "updateDate"],
                size=5000,
            ):
                src = hit["_source"]
                bid = src.get("biosampleId", "")
                update_date = src.get("updateDate", "")
                if bid:
                    dates[bid] = update_date
        except Exception:
            logger.warning("Could not read update dates from index %s", index_name, exc_info=True)

    logger.info("Fetched %d update dates from ES", len(dates))
    return dates


def fetch_biosample_accessions() -> list[str]:
    """Fetch all FAANG sample accession IDs from BioSamples API (paginated)."""
    import requests

    accessions: list[str] = []
    url: str | None = BIOSAMPLES_ACCESSIONS_URL
    page = 0

    while url:
        page += 1
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        page_accessions = data.get("_embedded", {}).get("accessions", [])
        accessions.extend(page_accessions)

        url = data.get("_links", {}).get("next", {}).get("href")

        if page % 10 == 0:
            logger.info("Fetched %d accessions so far (page %d)...", len(accessions), page)

    logger.info("Fetched %d accessions from BioSamples", len(accessions))
    return accessions


def get_changed_ids_from_batch(
    es_dates: dict[str, str], samples: list
) -> tuple[list, list]:
    """Compare ES update dates against BioSamples 'update' field.

    Returns (new_samples, updated_samples):
      - new_samples: not in ES at all
      - updated_samples: in ES but with a different update timestamp
    """
    import re

    new = []
    updated = []
    for sample in samples:
        accession = sample.get("accession", "")
        # BioSamples 'update' is ISO: "2023-06-20T10:30:00Z"
        # ES 'updateDate' is "2023-06-20"
        bs_update = sample.get("update", "")
        bs_date = ""
        if bs_update:
            match = re.search(r"(\d{4}-\d{2}-\d{2})", bs_update)
            bs_date = match.group(1) if match else bs_update

        es_date = es_dates.get(accession, "")

        if not es_date:
            new.append(sample)
        elif bs_date != es_date:
            updated.append(sample)

    logger.info(
        "Update date comparison: %d new, %d updated out of %d total",
        len(new),
        len(updated),
        len(samples),
    )
    return new, updated
