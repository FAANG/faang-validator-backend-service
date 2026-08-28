"""ENA Import Script.

Fetches ENA run data per study accession, transforms into ES-ready JSON
for experiment, file, and dataset indices.

Usage:
    python -m scripts.import_from_ena --studies PRJEB51699 PRJEB43111
    python -m scripts.import_from_ena --studies-file studies.txt
"""
import argparse
import json
import logging
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import requests

from scripts.es_cache import create_es_client

logger = logging.getLogger(__name__)

ENA_FILEREPORT_URL = (
    "https://www.ebi.ac.uk/ena/portal/api/filereport"
    "?accession={study_id}&result=read_run&fields=all&format=json&limit=0"
)

# Experiment XML — used to recover attributes (e.g. "secondary project") that the
# filereport read_run API leaves empty for many studies.
ENA_EXPERIMENT_XML_URL = "https://www.ebi.ac.uk/ena/browser/api/xml/{accessions}"
EXPERIMENT_XML_BATCH_SIZE = 100

# Assay type standardization
ASSAY_TYPE_FIXES = {
    "whole genome sequencing": "whole genome sequencing assay",
}

# Infer assay type from library_strategy when assay_type is empty
LIBRARY_STRATEGY_TO_ASSAY = {
    "Bisulfite-Seq": "methylation profiling by high throughput sequencing",
    "DNase-Hypersensitivity": "DNase-Hypersensitivity seq",
    "ChIP-Seq": "ChIP-seq",
    "ATAC-seq": "ATAC-seq",
    "Hi-C": "Hi-C",
    "WGS": "whole genome sequencing assay",
    "RNA-Seq": "transcription profiling by high throughput sequencing",
    "ssRNA-seq": "transcription profiling by high throughput sequencing",
    "miRNA-Seq": "microRNA profiling by high throughput sequencing",
    "ncRNA-Seq": "RNA-seq of non coding RNA",
}

# Default experiment targets per assay type
DEFAULT_TARGETS = {
    "ATAC-seq": "open_chromatin_region",
    "methylation profiling by high throughput sequencing": "DNA methylation",
    "DNase-Hypersensitivity seq": "open_chromatin_region",
    "Hi-C": "chromatin",
    "whole genome sequencing assay": "input DNA",
    "CAGE-seq": "TSS",
}

# Assay type -> technology type for dataset aggregation
TECHNOLOGIES = {
    "ATAC-seq": "ATAC-seq",
    "methylation profiling by high throughput sequencing": "BS-seq",
    "ChIP-seq": "ChIP-seq",
    "DNase-Hypersensitivity seq": "DNase-seq",
    "Hi-C": "Hi-C",
    "microRNA profiling by high throughput sequencing": "RNA-seq",
    "RNA-seq of coding RNA": "RNA-seq",
    "RNA-seq of non coding RNA": "RNA-seq",
    "RNA-seq of total RNA": "RNA-seq",
    "transcription profiling by high throughput sequencing": "RNA-seq",
    "whole genome sequencing assay": "WGS",
    "CAGE-seq": "CAGE-seq",
    "scRNA-seq": "scRNA-seq",
    "snATAC-seq": "snATAC-seq",
    "ISO-Seq": "ISO-Seq",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import ENA data per study")
    parser.add_argument(
        "--studies", nargs="+",
        help="Study accessions (e.g., PRJEB51699 PRJEB43111)",
    )
    parser.add_argument(
        "--studies-file",
        help="File with one study accession per line",
    )
    parser.add_argument(
        "--output-dir", default="./output/ena",
        help="Directory for JSON output (default: ./output/ena)",
    )
    parser.add_argument(
        "--specimen-index", default="2026_03_26_specimen",
        help="ES specimen index to read from",
    )
    parser.add_argument(
        "--organism-index", default="2026_03_26_organism",
        help="ES organism index to read from",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def get_filename_from_url(url: str) -> str:
    """Extract filename from URL if it's a PDF, otherwise return the URL."""
    if not url:
        return ""
    if url.lower().endswith(".pdf"):
        return url.rsplit("/", 1)[-1]
    return url


def convert_readable(size_bytes: str) -> str:
    """Convert bytes to human-readable size string."""
    if not size_bytes:
        return ""
    try:
        size = int(size_bytes)
    except (ValueError, TypeError):
        return str(size_bytes)
    units = ["B", "kB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.2f} PB"


def safe_get(record: dict, key: str) -> str:
    """Get a value from record, returning empty string if missing."""
    return record.get(key, "") or ""


def build_protocol(url: str) -> dict:
    """Build {url, filename} protocol dict."""
    return {
        "url": url or None,
        "filename": get_filename_from_url(url) or None,
    }


def safe_int(value: str) -> int | None:
    """Convert string to int, return None if empty."""
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ── ENA API ──────────────────────────────────────────────────────────────────

def fetch_study_data(study_id: str) -> list[dict]:
    """Fetch all run data for a study from ENA filereport API."""
    url = ENA_FILEREPORT_URL.format(study_id=study_id)
    logger.info("Fetching ENA data for %s", study_id)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    logger.info("Fetched %d runs for %s", len(data), study_id)
    return data


def fetch_experiment_secondary_projects(exp_ids: list[str]) -> dict[str, str]:
    """Fetch experiment XML and parse the "secondary project" attribute per experiment.

    The filereport read_run API leaves ``secondary_project`` empty for many studies
    (e.g. PRJEB112855 / AQUA-FAANG); the value is stored as an EXPERIMENT_ATTRIBUTE in
    the experiment XML instead. Returns: {experiment_accession: secondary_project}.
    """
    result: dict[str, str] = {}
    for i in range(0, len(exp_ids), EXPERIMENT_XML_BATCH_SIZE):
        batch = exp_ids[i:i + EXPERIMENT_XML_BATCH_SIZE]
        url = ENA_EXPERIMENT_XML_URL.format(accessions=",".join(batch))
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception:
            logger.warning(
                "Failed to fetch experiment XML for batch starting %s", batch[0],
                exc_info=True,
            )
            continue
        for exp in root.findall("EXPERIMENT"):
            acc = exp.get("accession")
            if not acc:
                continue
            for attr in exp.findall("./EXPERIMENT_ATTRIBUTES/EXPERIMENT_ATTRIBUTE"):
                if (attr.findtext("TAG") or "").strip().lower() == "secondary project":
                    value = (attr.findtext("VALUE") or "").strip()
                    if value:
                        result[acc] = value
                    break
    return result


# ── Specimen lookup ──────────────────────────────────────────────────────────

def fetch_all_specimens(es, specimen_index: str, organism_index: str) -> dict[str, dict]:
    """Fetch all specimens from ES with their organism info using scroll API.

    Returns: {biosampleId: {biosampleId, material, cellType, organism: {organism, sex, breed}}}
    """
    from elasticsearch.helpers import scan

    specimens = {}
    for hit in scan(
        es,
        index=specimen_index,
        query={"query": {"match_all": {}}},
        _source=["biosampleId", "material", "cellType", "organism"],
        size=5000,
    ):
        src = hit["_source"]
        bid = src.get("biosampleId", "")
        if bid:
            specimens[bid] = src

    logger.info("Loaded %d specimens from ES", len(specimens))
    return specimens


# ── Assay type / target normalization ────────────────────────────────────────

def normalize_assay_and_target(record: dict) -> tuple[str, str, str]:
    """Normalize assay_type, experiment_target, and target_for_file.

    Returns: (assay_type, experiment_target, target_used_in_file)
    """
    assay_type = safe_get(record, "assay_type")
    library_strategy = safe_get(record, "library_strategy")
    experiment_target = safe_get(record, "experiment_target")

    # Fix ontology IDs to readable names
    if experiment_target == "EFO_0005031":
        experiment_target = "input DNA"
    if experiment_target == "CHEBI_33697":
        experiment_target = "RNA"

    # Fix assay type from library strategy
    if not assay_type and library_strategy in LIBRARY_STRATEGY_TO_ASSAY:
        assay_type = LIBRARY_STRATEGY_TO_ASSAY[library_strategy]

    # Infer assay type for OTHER/unknown library strategies
    if not assay_type and library_strategy == "OTHER":
        library_source = safe_get(record, "library_source")
        platform = safe_get(record, "instrument_platform")
        if library_source == "TRANSCRIPTOMIC" and platform == "PACBIO_SMRT":
            assay_type = "ISO-Seq"
        elif library_source == "GENOMIC" and platform == "PACBIO_SMRT":
            assay_type = "whole genome sequencing assay"

    if assay_type in ASSAY_TYPE_FIXES:
        assay_type = ASSAY_TYPE_FIXES[assay_type]

    # Infer default experiment target
    if not experiment_target and assay_type in DEFAULT_TARGETS:
        experiment_target = DEFAULT_TARGETS[assay_type]

    # Target used in file docs
    if assay_type == "ChIP-seq" and experiment_target.lower() != "input dna":
        target_used_in_file = safe_get(record, "chip_target")
    else:
        target_used_in_file = experiment_target

    return assay_type, experiment_target, target_used_in_file


# ── File type detection ──────────────────────────────────────────────────────

def determine_file_and_source(record: dict) -> tuple[str, str]:
    """Determine file type and source from ENA record.

    Returns: (file_type, source_type) or ("", "") if none found.
    Preference order: fastq > submitted > sra > cram_index
    """
    file_types = ["fastq", "submitted", "sra", "cram_index"]
    source_types = ["ftp", "galaxy", "aspera"]
    for file_type in file_types:
        for source_type in source_types:
            key = f"{file_type}_{source_type}"
            if record.get(key, ""):
                return file_type, source_type
    return "", ""


# ── Experiment document builder ──────────────────────────────────────────────

def build_experiment_doc(record: dict, assay_type: str, experiment_target: str,
                         alias_cache: dict, secondary_project: str = "") -> dict:
    """Build ES experiment document from an ENA record."""
    exp_id = record["experiment_accession"]

    doc = {
        "accession": exp_id,
        "project": safe_get(record, "project") or "FAANG",
        "secondaryProject": secondary_project,
        "assayType": assay_type,
        "experimentTarget": experiment_target,
        "standardMet": "FAANG",
        "libraryName": safe_get(record, "library_name"),
        "sampleStorage": safe_get(record, "sample_storage"),
        "sampleStorageProcessing": safe_get(record, "sample_storage_processing"),
        "samplingToPreparationInterval": {
            "text": safe_get(record, "sample_prep_interval"),
            "unit": safe_get(record, "sample_prep_interval_units"),
        },
        "experimentalProtocol": build_protocol(safe_get(record, "experimental_protocol")),
        "extractionProtocol": build_protocol(safe_get(record, "extraction_protocol")),
        "libraryPreparationLocation": safe_get(record, "library_prep_location"),
        "libraryPreparationDate": {
            "text": safe_get(record, "library_prep_date"),
            "unit": safe_get(record, "library_prep_date_format"),
        },
        "sequencingLocation": safe_get(record, "sequencing_location"),
        "sequencingDate": {
            "text": safe_get(record, "sequencing_date"),
            "unit": safe_get(record, "sequencing_date_format"),
        },
    }

    # Optional coordinate fields
    lon = safe_get(record, "library_prep_longitude")
    if lon:
        doc["libraryPreparationLocationLongitude"] = {"text": lon, "unit": "decimal degrees"}
    lat = safe_get(record, "library_prep_latitude")
    if lat:
        doc["libraryPreparationLocationLatitude"] = {"text": lat, "unit": "decimal degrees"}
    seq_lon = safe_get(record, "sequencing_longitude")
    if seq_lon:
        doc["sequencingLocationLongitude"] = {"text": seq_lon, "unit": "decimal degrees"}
    seq_lat = safe_get(record, "sequencing_latitude")
    if seq_lat:
        doc["sequencingLocationLatitude"] = {"text": seq_lat, "unit": "decimal degrees"}

    # Assay-type-specific sections
    _add_assay_specific_fields(doc, record, assay_type, experiment_target, alias_cache)

    return doc


def _add_assay_specific_fields(doc: dict, record: dict, assay_type: str,
                                experiment_target: str, alias_cache: dict) -> None:
    """Add assay-type-specific nested section to experiment doc."""
    if assay_type == "ATAC-seq":
        doc["ATAC-seq"] = {
            "transposaseProtocol": build_protocol(safe_get(record, "transposase_protocol")),
        }

    elif assay_type == "methylation profiling by high throughput sequencing":
        lib_sel = safe_get(record, "faang_library_selection")
        if lib_sel == "RBBS":
            lib_sel = "RRBS"
        doc["BS-seq"] = {
            "librarySelection": lib_sel,
            "bisulfiteConversionProtocol": build_protocol(safe_get(record, "bisulfite_protocol")),
            "pcrProductIsolationProtocol": build_protocol(safe_get(record, "pcr_isolation_protocol")),
            "bisulfiteConversionPercent": safe_get(record, "bisulfite_percent"),
            "restrictionEnzyme": safe_get(record, "restriction_enzyme"),
        }

    elif assay_type == "ChIP-seq":
        chip_protocol = build_protocol(safe_get(record, "chip_protocol"))
        section = {
            "chipProtocol": chip_protocol,
            "libraryGenerationMaxFragmentSizeRange": safe_get(record, "library_max_fragment_size"),
            "libraryGenerationMinFragmentSizeRange": safe_get(record, "library_min_fragment_size"),
        }
        if experiment_target.lower() == "input dna":
            doc["ChIP-seq input DNA"] = section
        else:
            section["chipAntibodyProvider"] = safe_get(record, "chip_ab_provider")
            section["chipAntibodyCatalog"] = safe_get(record, "chip_ab_catalog")
            section["chipAntibodyLot"] = safe_get(record, "chip_ab_lot")
            section["chipTarget"] = safe_get(record, "chip_target")
            # Resolve control experiment alias -> accession
            control = safe_get(record, "control_experiment")
            study_id = record["study_accession"]
            section["controlExperiment"] = resolve_control_experiment(
                study_id, control, alias_cache
            )
            doc["ChIP-seq DNA-binding"] = section

    elif assay_type == "DNase-Hypersensitivity seq":
        doc["DNase-seq"] = {
            "dnaseProtocol": build_protocol(safe_get(record, "dnase_protocol")),
        }

    elif assay_type == "Hi-C":
        doc["Hi-C"] = {
            "restrictionEnzyme": safe_get(record, "restriction_enzyme"),
            "restrictionSite": safe_get(record, "restriction_site"),
            "hi-cProtocol": build_protocol(safe_get(record, "hi_c_protocol")),
        }

    elif assay_type == "whole genome sequencing assay":
        doc["WGS"] = {
            "libraryGenerationPcrProductIsolationProtocol": build_protocol(
                safe_get(record, "library_pcr_isolation_protocol")
            ),
            "libraryGenerationProtocol": build_protocol(
                safe_get(record, "library_gen_protocol")
            ),
            "librarySelection": safe_get(record, "faang_library_selection"),
        }

    elif assay_type == "CAGE-seq":
        doc["CAGE-seq"] = {
            "rnaPurity260280ratio": safe_get(record, "rna_purity_280_ratio"),
            "rnaPurity260230ratio": safe_get(record, "rna_purity_230_ratio"),
            "rnaIntegrityNumber": safe_get(record, "rna_integrity_num"),
            "cageProtocol": build_protocol(safe_get(record, "cage_protocol")),
            "sequencingPrimerProvider": safe_get(record, "sequencing_primer_provider"),
            "sequencingPrimerCatalog": safe_get(record, "sequencing_primer_catalog"),
            "sequencingPrimerLot": safe_get(record, "sequencing_primer_lot"),
            "restrictionEnzymeTargetSequence": safe_get(record, "restriction_enzyme_target_sequence"),
        }

    else:
        # RNA-seq and other RNA-based assays
        doc["RNA-seq"] = {
            "rnaPreparation3AdapterLigationProtocol": build_protocol(
                safe_get(record, "rna_prep_3_protocol")
            ),
            "rnaPreparation5AdapterLigationProtocol": build_protocol(
                safe_get(record, "rna_prep_5_protocol")
            ),
            "libraryGenerationPcrProductIsolationProtocol": build_protocol(
                safe_get(record, "library_pcr_isolation_protocol")
            ),
            "preparationReverseTranscriptionProtocol": build_protocol(
                safe_get(record, "rt_prep_protocol")
            ),
            "libraryGenerationProtocol": build_protocol(
                safe_get(record, "library_gen_protocol")
            ),
            "readStrand": safe_get(record, "read_strand"),
            "rnaPurity260280ratio": safe_get(record, "rna_purity_280_ratio"),
            "rnaPurity260230ratio": safe_get(record, "rna_purity_230_ratio"),
            "rnaIntegrityNumber": safe_get(record, "rna_integrity_num"),
        }


def resolve_control_experiment(study_id: str, value: str, alias_cache: dict) -> str:
    """Resolve a control experiment alias to an accession."""
    if not value:
        return ""
    # Already an accession?
    if re.match(r"^[SED]RX\d+$", value):
        return value

    # Build alias cache for this study if needed
    if study_id not in alias_cache:
        alias_cache[study_id] = {}
        try:
            url = (
                "https://www.ebi.ac.uk/ena/portal/api/search"
                f"?result=read_experiment&format=json&limit=0"
                f"&fields=experiment_accession,experiment_alias"
                f"&query=study_accession%3D%22{study_id}%22"
            )
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            for rec in resp.json():
                alias_cache[study_id][rec["experiment_alias"]] = rec["experiment_accession"]
        except Exception:
            logger.warning("Failed to fetch alias map for %s", study_id, exc_info=True)

    return alias_cache[study_id].get(value, value)


# ── Main processing ──────────────────────────────────────────────────────────

def process_study(
    study_id: str,
    specimens: dict[str, dict],
    alias_cache: dict,
) -> tuple[dict, dict, dict, list[str]]:
    """Process a single study. Returns (experiments, files, dataset_info, warnings)."""
    data = fetch_study_data(study_id)
    if not data:
        return {}, {}, {}, [f"No data returned for {study_id}"]

    # Recover "secondary project" from experiment XML — the read_run API leaves it empty.
    exp_ids = sorted({r["experiment_accession"] for r in data if r.get("experiment_accession")})
    secondary_project_map = fetch_experiment_secondary_projects(exp_ids)

    experiments: dict[str, dict] = {}
    files: dict[str, dict] = {}
    warnings: list[str] = []

    # Aggregation for dataset
    agg = {
        "specimens": {},
        "instruments": set(),
        "center_names": set(),
        "secondary_projects": set(),
        "archives": set(),
        "files": {},
        "experiments": {},
        "assay_types": set(),
    }

    dataset_meta = {
        "accession": study_id,
        "alias": "",
        "title": "",
        "secondaryAccession": "",
    }

    for record in data:
        assay_type, experiment_target, target_for_file = normalize_assay_and_target(record)
        file_type, source_type = determine_file_and_source(record)

        if not file_type:
            continue

        # Determine archive
        if file_type in ("fastq", "submitted", "cram_index"):
            archive = "ENA"
            if file_type == "cram_index":
                file_type = "submitted"
                source_type = "ftp"
        else:
            archive = "SRA"

        # Parse files from semicolon-delimited fields
        raw_files = record.get(f"{file_type}_{source_type}", "").split(";")
        raw_sizes = record.get(f"{file_type}_bytes", "").split(";")
        raw_checksums = record.get(f"{file_type}_md5", "").split(";")
        if file_type == "fastq":
            raw_types = ["fastq"] * len(raw_files)
        else:
            raw_types = record.get("submitted_format", "").split(";")

        if len(raw_files) != len(raw_types) or len(raw_files) != len(raw_sizes) or not raw_files[0]:
            continue

        specimen_id = record.get("sample_accession", "")

        # Check specimen exists
        if specimen_id not in specimens:
            warnings.append(f"{specimen_id} from {study_id} not found in specimen index")
            continue

        specimen_data = specimens[specimen_id]
        exp_id = record["experiment_accession"]

        # Secondary project: prefer the read_run field, fall back to experiment XML
        secondary_project = safe_get(record, "secondary_project") or secondary_project_map.get(exp_id, "")

        # Dataset metadata (from first record)
        if not dataset_meta["alias"]:
            dataset_meta["alias"] = safe_get(record, "study_alias")
            dataset_meta["title"] = safe_get(record, "study_title")
            dataset_meta["secondaryAccession"] = safe_get(record, "secondary_study_accession")

        # Build experiment doc (once per experiment)
        if exp_id not in experiments:
            experiments[exp_id] = build_experiment_doc(
                record, assay_type, experiment_target, alias_cache, secondary_project
            )

        # Build file docs
        for idx, file_url in enumerate(raw_files):
            if not file_url:
                continue
            fullname = file_url.rsplit("/", 1)[-1]
            file_id = fullname.split(".")[0]

            file_doc = {
                "specimen": specimen_id,
                "organism": specimen_data.get("organism", {}).get("biosampleId", ""),
                "species": specimen_data.get("organism", {}).get("organism", {}),
                "secondaryProject": secondary_project,
                "url": file_url,
                "name": fullname,
                "type": raw_types[idx] if idx < len(raw_types) else "",
                "size": safe_int(raw_sizes[idx]) if idx < len(raw_sizes) else None,
                "readableSize": convert_readable(raw_sizes[idx]) if idx < len(raw_sizes) else "",
                "checksumMethod": "md5",
                "checksum": raw_checksums[idx] if idx < len(raw_checksums) else "",
                "archive": archive,
                "baseCount": safe_int(safe_get(record, "base_count")),
                "readCount": safe_int(safe_get(record, "read_count")),
                "releaseDate": safe_get(record, "first_public"),
                "updateDate": safe_get(record, "last_updated"),
                "submission": safe_get(record, "submission_accession"),
                "experiment": {
                    "accession": exp_id,
                    "assayType": assay_type,
                    "target": target_for_file,
                    "standardMet": "FAANG",
                },
                "run": {
                    "accession": safe_get(record, "run_accession"),
                    "alias": safe_get(record, "run_alias"),
                    "platform": safe_get(record, "instrument_platform"),
                    "instrument": safe_get(record, "instrument_model"),
                    "centerName": safe_get(record, "center_name"),
                    "sequencingDate": safe_get(record, "sequencing_date"),
                    "sequencingLocation": safe_get(record, "sequencing_location"),
                    "sequencingLatitude": safe_get(record, "sequencing_latitude"),
                    "sequencingLongitude": safe_get(record, "sequencing_longitude"),
                },
                "study": {
                    "accession": study_id,
                    "alias": safe_get(record, "study_alias"),
                    "title": safe_get(record, "study_title"),
                    "type": safe_get(record, "study_type"),
                    "secondaryAccession": safe_get(record, "secondary_study_accession"),
                },
                "paperPublished": "",
            }
            files[file_id] = file_doc

            # Aggregate for dataset
            agg["specimens"][specimen_id] = specimen_data
            agg["instruments"].add(safe_get(record, "instrument_model"))
            agg["center_names"].add(safe_get(record, "center_name"))
            if secondary_project:
                agg["secondary_projects"].add(secondary_project)
            agg["archives"].add(archive)
            agg["files"][fullname] = {
                "url": file_url,
                "name": fullname,
                "fileId": file_id,
                "experiment": exp_id,
                "type": raw_types[idx] if idx < len(raw_types) else "",
                "size": raw_sizes[idx] if idx < len(raw_sizes) else "",
                "readableSize": convert_readable(raw_sizes[idx]) if idx < len(raw_sizes) else "",
                "archive": archive,
                "baseCount": safe_get(record, "base_count"),
                "readCount": safe_get(record, "read_count"),
                "checksum": raw_checksums[idx] if idx < len(raw_checksums) else "",
                "checksumMethod": "md5",
            }
            agg["experiments"][exp_id] = {
                "accession": exp_id,
                "assayType": assay_type,
                "target": experiment_target,
            }
            agg["assay_types"].add(assay_type)

    # Build dataset document
    dataset_doc = _build_dataset_doc(dataset_meta, agg)

    return experiments, files, dataset_doc, warnings


def _build_dataset_doc(meta: dict, agg: dict) -> dict:
    """Build ES dataset document from aggregated data."""
    # Build specimen list with organism info
    specimens_list = []
    species_map = {}
    for sid, sdata in sorted(agg["specimens"].items()):
        org_info = sdata.get("organism", {})
        specimen_entry = {
            "biosampleId": sid,
            "material": sdata.get("material", {}),
            "cellType": sdata.get("cellType", {}),
            "organism": org_info.get("organism", {}),
            "sex": org_info.get("sex", {}),
            "breed": org_info.get("breed", {}),
        }
        specimens_list.append(specimen_entry)
        org = org_info.get("organism", {})
        if org.get("text"):
            species_map[org["text"]] = org

    # Tech types from assay types
    tech_types = set()
    for at in agg["assay_types"]:
        if at in TECHNOLOGIES:
            tech_types.add(TECHNOLOGIES[at])

    return {
        "accession": meta["accession"],
        "alias": meta["alias"],
        "title": meta["title"],
        "secondaryAccession": meta["secondaryAccession"],
        "standardMet": "FAANG",
        "secondaryProject": sorted(agg["secondary_projects"]),
        "assayType": sorted(agg["assay_types"]),
        "tech": sorted(tech_types),
        "archive": sorted(agg["archives"]),
        "instrument": sorted(agg["instruments"] - {""}),
        "centerName": sorted(agg["center_names"] - {""}),
        "specimen": specimens_list,
        "species": list(species_map.values()),
        "file": sorted(agg["files"].values(), key=lambda f: f["name"]),
        "experiment": list(agg["experiments"].values()),
        "paperPublished": "",
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    # Collect study IDs
    study_ids = []
    if args.studies:
        study_ids.extend(args.studies)
    if args.studies_file:
        with open(args.studies_file) as f:
            study_ids.extend(line.strip() for line in f if line.strip())

    if not study_ids:
        logger.error("No study accessions provided. Use --studies or --studies-file")
        return

    logger.info("Processing %d studies", len(study_ids))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load specimen data from ES
    es = create_es_client()
    specimens = fetch_all_specimens(es, args.specimen_index, args.organism_index)

    alias_cache: dict[str, dict[str, str]] = {}

    all_experiments = {}
    all_files = {}
    all_datasets = {}
    all_warnings = []

    for study_id in study_ids:
        try:
            exps, files, dataset, warns = process_study(study_id, specimens, alias_cache)
            all_experiments.update(exps)
            all_files.update(files)
            if dataset:
                all_datasets[study_id] = dataset
            all_warnings.extend(warns)
            logger.info(
                "Study %s: %d experiments, %d files",
                study_id, len(exps), len(files),
            )
        except Exception:
            logger.error("Failed to process study %s", study_id, exc_info=True)
            all_warnings.append(f"Failed to process {study_id}")

    # Write output
    exp_path = output_dir / "experiments.json"
    with open(exp_path, "w") as f:
        json.dump(
            [{"_id": k, "document": v} for k, v in all_experiments.items()],
            f, indent=2, default=str,
        )
    logger.info("Written %s (%d experiments)", exp_path, len(all_experiments))

    file_path = output_dir / "files.json"
    with open(file_path, "w") as f:
        json.dump(
            [{"_id": k, "document": v} for k, v in all_files.items()],
            f, indent=2, default=str,
        )
    logger.info("Written %s (%d files)", file_path, len(all_files))

    dataset_path = output_dir / "datasets.json"
    with open(dataset_path, "w") as f:
        json.dump(
            [{"_id": k, "document": v} for k, v in all_datasets.items()],
            f, indent=2, default=str,
        )
    logger.info("Written %s (%d datasets)", dataset_path, len(all_datasets))

    if all_warnings:
        warn_path = output_dir / "warnings.txt"
        with open(warn_path, "w") as f:
            f.write("\n".join(all_warnings))
        logger.info("Written %s (%d warnings)", warn_path, len(all_warnings))

    logger.info("ENA import complete")


if __name__ == "__main__":
    main()
