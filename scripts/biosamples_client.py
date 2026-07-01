"""BioSamples API client: fetch FAANG samples via batch or individual requests."""

import logging
from collections import defaultdict

import requests

logger = logging.getLogger(__name__)

BIOSAMPLES_SEARCH_URL = (
    "https://www.ebi.ac.uk/biosamples/samples"
    "?size=200&filter=attr%3Aproject%3AFAANG&cursor=*"
)
BIOSAMPLES_SAMPLE_URL = "https://www.ebi.ac.uk/biosamples/samples/{sample_id}.json"
BIOSAMPLES_CURATION_URL = (
    "https://www.ebi.ac.uk/biosamples/samples/{sample_id}.json"
    "?curationdomain=self.FAANG_DCC_curation"
)

BASE_MATERIAL_TYPES = {
    "organism": "http://purl.obolibrary.org/obo/OBI_0100026",
    "specimen from organism": "http://purl.obolibrary.org/obo/OBI_0001479",
    "cell specimen": "http://purl.obolibrary.org/obo/OBI_0001468",
    "single cell specimen": "http://purl.obolibrary.org/obo/OBI_0002127",
    "pool of specimens": "http://purl.obolibrary.org/obo/OBI_0302716",
    "cell culture": "http://purl.obolibrary.org/obo/OBI_0001876",
    "cell line": "http://purl.obolibrary.org/obo/CLO_0000031",
    "organoid": "http://purl.obolibrary.org/obo/NCIT_C172259",
}

IRI_TO_MATERIAL = {v: k for k, v in BASE_MATERIAL_TYPES.items()}

# Aliases for non-standard material type labels in BioSamples data
MATERIAL_ALIASES = {
    "primary cell culture": "cell culture",
}


def fetch_all_samples_batch() -> list[dict]:
    """Fetch all FAANG samples via paginated batch request."""
    samples: list[dict] = []
    url: str | None = BIOSAMPLES_SEARCH_URL
    page = 0

    while url:
        page += 1
        logger.info("Fetching batch page %d...", page)
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        page_samples = data.get("_embedded", {}).get("samples", [])
        samples.extend(page_samples)

        url = data.get("_links", {}).get("next", {}).get("href")

    logger.info("Batch fetch complete: %d samples", len(samples))
    return samples


def fetch_samples_individual(sample_ids: set[str]) -> list[dict]:
    """Fetch individual samples by ID (for incremental updates)."""
    samples: list[dict] = []
    total = len(sample_ids)

    for i, sample_id in enumerate(sample_ids, 1):
        if i % 100 == 0:
            logger.info("Fetching individual sample %d/%d...", i, total)
        try:
            url = BIOSAMPLES_CURATION_URL.format(sample_id=sample_id)
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            samples.append(resp.json())
        except Exception:
            logger.warning("Failed to fetch sample %s", sample_id, exc_info=True)

    logger.info("Individual fetch complete: %d/%d samples", len(samples), total)
    return samples


def check_samples_exist(sample_ids: set[str]) -> tuple[set[str], set[str]]:
    """Check which sample IDs still exist in BioSamples API.

    Returns (existing_ids, deleted_ids).
    """
    existing = set()
    deleted = set()
    total = len(sample_ids)

    for i, sample_id in enumerate(sample_ids, 1):
        if i % 100 == 0:
            logger.info("Checking sample existence %d/%d...", i, total)
        try:
            url = BIOSAMPLES_SAMPLE_URL.format(sample_id=sample_id)
            resp = requests.get(url, timeout=30)
            if resp.status_code in (403, 404):
                deleted.add(sample_id)
            else:
                resp.raise_for_status()
                existing.add(sample_id)
        except Exception:
            # Network error or other failure — don't assume deleted
            logger.warning("Could not check sample %s, skipping", sample_id, exc_info=True)

    logger.info("Existence check: %d exist, %d deleted, %d unchecked",
                len(existing), len(deleted), total - len(existing) - len(deleted))
    return existing, deleted


def refetch_with_curation(sample_id: str) -> dict | None:
    """Re-fetch a single sample from FAANG_DCC_curation domain."""
    try:
        url = BIOSAMPLES_CURATION_URL.format(sample_id=sample_id)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.warning("Failed to re-fetch %s from curation domain", sample_id)
        return None


def check_is_faang(sample: dict) -> bool:
    """Check if a sample has project=FAANG."""
    chars = sample.get("characteristics", {})
    for project in chars.get("project", []):
        if project.get("text", "").lower() == "faang":
            return True
    return False


def get_material_type(sample: dict) -> str | None:
    """Extract and normalize material type from a sample."""
    chars = sample.get("characteristics", {})
    material_entries = chars.get("Material") or chars.get("material", [])
    if not material_entries:
        return None

    entry = material_entries[0]
    text = entry.get("text", "").lower().strip()
    ontology_terms = entry.get("ontologyTerms", [])

    if text in BASE_MATERIAL_TYPES:
        return text

    if text in MATERIAL_ALIASES:
        return MATERIAL_ALIASES[text]

    for iri in ontology_terms:
        if iri in IRI_TO_MATERIAL:
            return IRI_TO_MATERIAL[iri]

    logger.debug("Unknown material type text='%s' ontology=%s", text, ontology_terms)
    return text if text else None


def deal_with_decimal_degrees(sample: dict) -> dict:
    """Re-fetch organism from curation domain if lat/long uses 'decimal degree' units."""
    chars = sample.get("characteristics", {})
    material_entries = chars.get("Material") or chars.get("material", [])
    if not material_entries:
        return sample

    material_text = material_entries[0].get("text", "").lower().strip()
    if material_text != "organism":
        return sample

    for field in ["birth location latitude", "birth location longitude"]:
        entries = chars.get(field, [])
        for entry in entries:
            if entry.get("unit", "").lower() == "decimal degree":
                logger.debug(
                    "Re-fetching %s due to decimal degree units",
                    sample.get("accession", ""),
                )
                refetched = refetch_with_curation(sample["accession"])
                if refetched:
                    return refetched
                return sample

    return sample


def _detect_teleostei_type(sample: dict) -> str | None:
    """Detect if a specimen is actually a teleostei embryo or post-hatching.

    Teleostei samples arrive with material='specimen from organism' but have
    teleostei-specific characteristics like 'origin', 'hatching', 'reproductive strategy'.
    """
    chars = sample.get("characteristics", {})

    has_origin = "origin" in chars
    has_hatching = "hatching" in chars
    has_reproductive_strategy = "reproductive strategy" in chars

    if not (has_origin or has_hatching or has_reproductive_strategy):
        return None

    # Determine embryo vs post-hatching
    hatching_entries = chars.get("hatching", [])
    if hatching_entries:
        hatching_val = hatching_entries[0].get("text", "").lower()
        if hatching_val == "post":
            return "teleostei post-hatching"
        elif hatching_val == "pre":
            return "teleostei embryo"

    # If has post-hatching specific fields, it's post-hatching
    has_gonad = "gonad type" in chars
    has_maturity = "maturity state" in chars
    if has_gonad or has_maturity:
        return "teleostei post-hatching"

    # Default to embryo if teleostei fields present
    return "teleostei embryo"


def categorize_samples(samples: list[dict]) -> dict[str, list[dict]]:
    """Categorize samples by material type, filtering non-FAANG and invalid."""
    categorized: dict[str, list[dict]] = defaultdict(list)
    failed: list[dict] = []
    skipped_not_faang = 0
    skipped_no_material = 0

    for sample in samples:
        accession = sample.get("accession", "unknown")

        if not check_is_faang(sample):
            skipped_not_faang += 1
            continue

        material_type = get_material_type(sample)
        if not material_type:
            skipped_no_material += 1
            logger.debug("Sample %s has no material field", accession)
            failed.append(sample)
            continue

        if material_type not in BASE_MATERIAL_TYPES:
            logger.warning(
                "Sample %s has unrecognized material type: %s", accession, material_type
            )
            failed.append(sample)
            continue

        # Check if specimen is actually a teleostei type
        if material_type == "specimen from organism":
            teleostei_type = _detect_teleostei_type(sample)
            if teleostei_type:
                material_type = teleostei_type

        sample = deal_with_decimal_degrees(sample)
        categorized[material_type].append(sample)

    if skipped_not_faang:
        logger.info("Skipped %d non-FAANG samples", skipped_not_faang)
    if skipped_no_material:
        logger.info("Skipped %d samples with no material field", skipped_no_material)

    result = dict(categorized)
    result["_failed"] = failed

    for mat_type, mat_samples in result.items():
        if mat_type != "_failed":
            logger.info("  %s: %d samples", mat_type, len(mat_samples))

    return result
