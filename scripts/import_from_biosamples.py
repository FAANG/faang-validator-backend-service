"""FAANG BioSamples Import Script.

Fetches FAANG samples from BioSamples API, validates with Pydantic models,
and outputs ES-ready JSON documents.
"""
import argparse
import json
import logging
from pathlib import Path

from scripts.es_cache import (
    create_es_client,
    fetch_es_update_dates,
    get_changed_ids_from_batch,
)
from scripts.biosamples_client import (
    categorize_samples,
    check_samples_exist,
    fetch_all_samples_batch,
)

from app.validation.generic_validator_classes import RelationshipValidator

logger = logging.getLogger(__name__)

_shared_relationship_validator: RelationshipValidator | None = None

# Processing tiers — each tier completes before the next starts
PROCESSING_TIERS = [
    # Tier 1: no dependencies
    ["organism"],
    # Tier 2: depend on organisms
    ["specimen from organism", "teleostei embryo", "teleostei post-hatching"],
    # Tier 3: depend on specimens
    ["cell specimen", "single cell specimen"],
    # Tier 4: depend on specimens/cell specimens; pool last
    ["cell culture", "cell line", "organoid"],
    ["pool of specimens"],
]


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import FAANG samples from BioSamples API"
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Directory for JSON output (default: ./output)",
    )
    parser.add_argument(
        "--organism-index",
        default="2026_03_26_organism",
        help="ES organism index to read existing samples from",
    )
    parser.add_argument(
        "--specimen-index",
        default="2026_03_26_specimen",
        help="ES specimen index to read existing samples from",
    )
    parser.add_argument(
        "--skip-deletion-check",
        action="store_true",
        help="Skip per-sample existence checks for IDs in ES but absent from "
             "the BioSamples FAANG dump (saves ~2h on large indices)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )
    return parser.parse_args()


def _prepopulate_relationship_cache(
    samples: list, validator: RelationshipValidator
) -> None:
    """Pre-populate RelationshipValidator.biosamples_cache from fetched data.

    Uses the reduced-schema format expected by RelationshipValidator:
    {"organism": "<text>", "material": "<text>", "relationships": [...]}
    """
    for sample in samples:
        accession = sample.get("accession", "")
        if not accession:
            continue
        chars = sample.get("characteristics", {})

        org_entries = chars.get("Organism") or chars.get("organism", [])
        organism_text = org_entries[0].get("text", "") if org_entries else ""

        mat_entries = chars.get("Material") or chars.get("material", [])
        material_text = mat_entries[0].get("text", "") if mat_entries else ""

        relationships = []
        for rel in sample.get("relationships", []):
            if rel.get("source") == accession:
                rel_type = rel.get("type", "").lower()
                if rel_type in ("child of", "derived from"):
                    relationships.append(rel)

        validator.biosamples_cache[accession] = {
            "organism": organism_text,
            "material": material_text,
            "relationships": relationships,
        }

    logger.info(
        "Pre-populated RelationshipValidator cache with %d samples",
        len(validator.biosamples_cache),
    )


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)
    logger.info("Starting BioSamples import")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Fetch existing update dates from ES
    es = create_es_client()
    es_dates = fetch_es_update_dates(es, [args.organism_index, args.specimen_index])

    # Step 2: Fetch all FAANG samples from BioSamples API (batch with cursor pagination)
    logger.info("Fetching all FAANG samples from BioSamples API...")
    all_samples = fetch_all_samples_batch()

    # Step 3: Split into new samples and updated samples
    new_samples, updated_samples = get_changed_ids_from_batch(es_dates, all_samples)

    # Track which accessions are updates (existing in ES) vs new
    existing_accessions = {s.get("accession", "") for s in updated_samples}
    logger.info("%d new samples, %d updates", len(new_samples), len(updated_samples))

    # Step 4: Detect samples in ES but absent from BioSamples dump
    biosamples_accessions = {s.get("accession", "") for s in all_samples}
    missing_from_dump = set(es_dates.keys()) - biosamples_accessions
    deleted_results = []
    if missing_from_dump and args.skip_deletion_check:
        logger.info(
            "%d samples in ES but absent from BioSamples dump — skipping existence "
            "check (--skip-deletion-check)", len(missing_from_dump),
        )
    elif missing_from_dump:
        logger.info("%d samples in ES but absent from BioSamples dump, checking API...", len(missing_from_dump))
        _still_exist, confirmed_deleted = check_samples_exist(missing_from_dump)
        deleted_results = [{"biosampleId": sid} for sid in sorted(confirmed_deleted)]
        logger.info("%d samples confirmed deleted from BioSamples", len(deleted_results))

    raw_samples = new_samples + updated_samples
    if not raw_samples and not deleted_results:
        logger.info("No changed samples — nothing to do")
        return

    # Step 5: Filter and categorize
    categorized = categorize_samples(raw_samples)
    failed_categorization = categorized.pop("_failed", [])

    # Pre-populate RelationshipValidator cache from fetched samples
    global _shared_relationship_validator
    _shared_relationship_validator = RelationshipValidator()
    _prepopulate_relationship_cache(raw_samples, _shared_relationship_validator)

    # Step 6-8: Process tiers (map -> validate -> transform)
    valid_results = []
    failed_results = []
    processed_documents = {}  # {accession: es_document} for parent resolution

    # Add categorization failures
    for sample in failed_categorization:
        failed_results.append({
            "biosampleId": sample.get("accession", "unknown"),
            "material_type": "unknown",
            "errors": ["Could not determine material type"],
            "warnings": [],
            "raw_data": sample,
        })

    for tier in PROCESSING_TIERS:
        for material_type in tier:
            samples = categorized.get(material_type, [])
            if not samples:
                continue

            logger.info("Processing %d %s samples...", len(samples), material_type)

            tier_valid, tier_failed = process_material_type(
                material_type, samples, processed_documents, existing_accessions
            )
            valid_results.extend(tier_valid)
            failed_results.extend(tier_failed)

    # Step 9: Write output
    valid_path = output_dir / "samples_valid.json"
    failed_path = output_dir / "samples_failed.json"
    deleted_path = output_dir / "samples_deleted.json"

    with open(valid_path, "w") as f:
        json.dump(valid_results, f, indent=2, default=str)
    logger.info("Output written: %s (%d records)", valid_path, len(valid_results))

    with open(failed_path, "w") as f:
        json.dump(failed_results, f, indent=2, default=str)
    logger.info("Output written: %s (%d records)", failed_path, len(failed_results))

    with open(deleted_path, "w") as f:
        json.dump(deleted_results, f, indent=2, default=str)
    logger.info("Output written: %s (%d records)", deleted_path, len(deleted_results))

    logger.info("Import complete")


def process_material_type(
    material_type: str,
    samples: list,
    processed_documents: dict,
    existing_accessions: set[str],
) -> tuple:
    """Process a batch of samples: map -> validate -> transform.

    Returns: (valid_results, failed_results)
    """
    from scripts.biosamples_mapper import map_samples
    from scripts.es_transformer import transform_to_es_document, clean_internal_fields

    valid_results = []
    failed_results = []

    # Map BioSamples API data to Pydantic input format
    mapped_samples = map_samples(material_type, samples)

    # Validate with Pydantic models
    validated = validate_samples(material_type, mapped_samples, existing_accessions)

    for item in validated:
        accession = item["accession"]

        # Transform to ES document for both valid and failed samples
        es_doc = transform_to_es_document(
            material_type=material_type,
            raw_sample=item["raw_sample"],
            pydantic_data=item["pydantic_data"] or item["pydantic_dict"],
            custom_fields=item["custom_fields"],
            processed_documents=processed_documents,
            validation_status=item["status"],
        )
        processed_documents[accession] = es_doc

        if item["status"] == "error":
            failed_results.append({
                "biosampleId": accession,
                "material_type": material_type,
                "errors": item["errors"],
                "document": clean_internal_fields(es_doc),
            })
        else:
            entry = {
                "biosampleId": accession,
                "material_type": material_type,
                "standardMet": "FAANG",
                "document": clean_internal_fields(es_doc),
            }
            if item.get("legacy_errors"):
                entry["legacy_errors"] = item["legacy_errors"]
            valid_results.append(entry)

    return valid_results, failed_results


def validate_samples(
    material_type: str, mapped_samples: list, existing_accessions: set[str]
) -> list:
    """Validate mapped samples using Pydantic models.

    New samples (not in existing_accessions) are validated strictly.
    Update samples (in existing_accessions) treat validation errors as
    legacy_errors and are considered valid.

    Returns list of dicts with keys:
        accession, status, pydantic_data, custom_fields, errors, warnings,
        legacy_errors, raw_sample
    """
    from scripts.biosamples_mapper import get_pydantic_model
    from app.validation.generic_validator_classes import (
        OntologyValidator,
        ontology_validator_context,
    )
    from app.validation.sample.base_validator import ontology_warnings_context

    # Create shared validator
    ontology_validator = OntologyValidator(cache_enabled=True)

    # Collect all ontology terms for prefetching
    all_terms = set()
    for item in mapped_samples:
        pydantic_dict = item["pydantic_dict"]
        for key, value in pydantic_dict.items():
            if "Term Source ID" in key and isinstance(value, str) and value:
                # Normalize underscore to colon for OLS lookup
                term = value.replace("_", ":", 1) if "_" in value else value
                all_terms.add(term)
            # Handle nested models (health status, cell type)
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and "term" in entry:
                        term = entry["term"]
                        if isinstance(term, str) and term:
                            term = term.replace("_", ":", 1) if "_" in term else term
                            all_terms.add(term)

    # Prefetch ontology terms (no event loop running at this point)
    if all_terms:
        logger.info("Prefetching %d ontology terms from OLS...", len(all_terms))
        ontology_validator.batch_fetch_from_ols_sync(list(all_terms))

    # Get model class
    model_class = get_pydantic_model(material_type)

    results = []
    for item in mapped_samples:
        accession = item["accession"]
        pydantic_dict = item["pydantic_dict"]
        custom_fields = item["custom_fields"]
        raw_sample = item["raw_sample"]

        # Set context vars
        ontology_validator_context.set(ontology_validator)
        ontology_warnings_context.set([])

        errors = []
        warnings = []
        legacy_errors = []
        pydantic_data = None
        status = "pass"
        is_update = accession in existing_accessions

        try:
            model_instance = model_class(**pydantic_dict)
            pydantic_data = model_instance.model_dump()
            # Collect ontology warnings
            ont_warnings = ontology_warnings_context.get()
            if ont_warnings:
                warnings.extend(ont_warnings)
                status = "warning"
        except Exception as e:
            validation_errors = []
            if hasattr(e, "errors"):
                for err in e.errors():
                    loc = ".".join(str(x) for x in err.get("loc", []))
                    msg = err.get("msg", str(err))
                    validation_errors.append(f"{loc}: {msg}")
            else:
                validation_errors.append(str(e))

            if is_update:
                # Existing sample: treat all errors as legacy, keep as valid
                legacy_errors = validation_errors
                status = "warning"
                pydantic_data = pydantic_dict
            else:
                # New sample: strict validation
                errors = validation_errors
                status = "error"

        results.append({
            "accession": accession,
            "status": status,
            "pydantic_data": pydantic_data,
            "pydantic_dict": pydantic_dict,
            "custom_fields": custom_fields,
            "errors": errors,
            "warnings": warnings,
            "legacy_errors": legacy_errors,
            "raw_sample": raw_sample,
        })

    pass_count = sum(1 for r in results if r["status"] != "error")
    fail_count = sum(1 for r in results if r["status"] == "error")
    logger.info(
        "Validated %s: %d pass, %d failed", material_type, pass_count, fail_count
    )

    return results


if __name__ == "__main__":
    main()
