"""Map BioSamples API responses to Pydantic model input format.

Two-pass extraction:
  Pass 1: Extract fields matching Pydantic aliases -> validation dict
  Pass 2: Collect remaining characteristics -> custom fields for ES document
"""
import logging
import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from app.rulesets_pydantics.sample.organism_ruleset import FAANGOrganismSample
from app.rulesets_pydantics.sample.specimen_ruleset import FAANGSpecimenFromOrganismSample
from app.rulesets_pydantics.sample.cell_specimen_ruleset import FAANGCellSpecimenSample
from app.rulesets_pydantics.sample.cell_culture_ruleset import FAANGCellCultureSample
from app.rulesets_pydantics.sample.cell_line_ruleset import FAANGCellLineSample
from app.rulesets_pydantics.sample.pool_of_specimens_ruleset import FAANGPoolOfSpecimensSample
from app.rulesets_pydantics.sample.organoid_ruleset import FAANGOrganoidSample
from app.rulesets_pydantics.sample.single_cell_specimen_ruleset import FAANGSingleCellSpecimenSample
from app.rulesets_pydantics.sample.teleostei_embryo_ruleset import FAANGTeleosteiEmbryoSample
from app.rulesets_pydantics.sample.teleostei_post_hatching_ruleset import FAANGTeleosteiPostHatchingSample

logger = logging.getLogger(__name__)


# ── Model registry ──────────────────────────────────────────────────────────

MODEL_MAP: dict[str, type[BaseModel]] = {
    "organism": FAANGOrganismSample,
    "specimen from organism": FAANGSpecimenFromOrganismSample,
    "cell specimen": FAANGCellSpecimenSample,
    "cell culture": FAANGCellCultureSample,
    "cell line": FAANGCellLineSample,
    "pool of specimens": FAANGPoolOfSpecimensSample,
    "organoid": FAANGOrganoidSample,
    "single cell specimen": FAANGSingleCellSpecimenSample,
    "teleostei embryo": FAANGTeleosteiEmbryoSample,
    "teleostei post-hatching": FAANGTeleosteiPostHatchingSample,
}


def get_pydantic_model(material_type: str) -> type[BaseModel]:
    model = MODEL_MAP.get(material_type)
    if not model:
        raise ValueError(f"No Pydantic model for material type: {material_type}")
    return model


# ── Ontology term helpers ───────────────────────────────────────────────────

def extract_ontology_id(uri: str) -> str:
    """Extract ontology ID from full OBO URI.

    'http://purl.obolibrary.org/obo/NCBITaxon_9913' -> 'NCBITaxon_9913'
    """
    match = re.search(r"/obo/(.+)$", uri)
    if match:
        return match.group(1)
    # Fallback: last path segment
    return uri.rsplit("/", 1)[-1] if "/" in uri else uri


def get_text(chars: dict, field: str) -> str | None:
    """Safely get text from characteristics[field][0]['text']."""
    entries = chars.get(field, [])
    if entries and isinstance(entries, list):
        return entries[0].get("text")
    return None


def get_unit(chars: dict, field: str) -> str | None:
    """Safely get unit from characteristics[field][0]['unit']."""
    entries = chars.get(field, [])
    if entries and isinstance(entries, list):
        return entries[0].get("unit")
    return None


def get_ontology_term(chars: dict, field: str) -> str | None:
    """Get first ontology term ID from characteristics[field][0]['ontologyTerms'][0]."""
    entries = chars.get(field, [])
    if entries and isinstance(entries, list):
        ont_terms = entries[0].get("ontologyTerms", [])
        if ont_terms:
            return extract_ontology_id(ont_terms[0])
    return None


def get_multi_values(chars: dict, field: str) -> list[dict[str, Any]]:
    """Get all entries for a multi-value field as [{text, term}] dicts.

    Used for health status, cell type, etc.
    """
    entries = chars.get(field, [])
    result = []
    for entry in entries:
        item: dict[str, Any] = {"text": entry.get("text", "")}
        ont_terms = entry.get("ontologyTerms", [])
        if ont_terms:
            item["term"] = extract_ontology_id(ont_terms[0])
        result.append(item)
    return result


def get_protocol_url(chars: dict, field: str) -> str | None:
    """Get URL from a protocol field."""
    return get_text(chars, field)


# ── Relationship extraction ─────────────────────────────────────────────────

def extract_relationships(sample: dict) -> dict[str, list[str]]:
    """Extract relationships from BioSamples response.

    Returns: {'child of': [...], 'derived from': [...], 'same as': [...]}
    """
    rels: defaultdict[str, list[str]] = defaultdict(list)
    accession = sample.get("accession", "")

    for rel in sample.get("relationships", []):
        rel_type = rel.get("type", "").lower()
        source = rel.get("source", "")
        target = rel.get("target", "")

        # Only outgoing relationships (source is this sample)
        if source != accession:
            continue
        if target == accession:
            continue

        rels[rel_type].append(target)

    return dict(rels)


# ── Base (SampleCoreMetadata) field mapping ─────────────────────────────────

# Fields from SampleCoreMetadata that apply to ALL types
BASE_FIELD_MAP = {
    # BioSamples characteristic name -> Pydantic alias
    "Material": ("Material", "text"),
    "material": ("Material", "text"),
}


def map_base_fields(
    sample: dict, relationships: dict[str, list[str]]
) -> dict[str, Any]:
    """Map SampleCoreMetadata fields common to all types."""
    chars = sample.get("characteristics", {})
    result: dict[str, Any] = {}

    # Sample Name = accession
    result["Sample Name"] = sample.get("accession", "")

    # Material + Term Source ID
    material_text = get_text(chars, "Material") or get_text(chars, "material")
    material_term = get_ontology_term(chars, "Material") or get_ontology_term(chars, "material")
    if material_text:
        result["Material"] = material_text
    if material_term:
        result["Term Source ID"] = material_term

    # Project
    project_text = get_text(chars, "project")
    if project_text:
        result["Project"] = project_text

    # Secondary Project
    secondary = chars.get("secondary project", [])
    if secondary:
        result["Secondary Project"] = [e.get("text", "") for e in secondary if e.get("text")]

    # Sample Description
    desc = get_text(chars, "description")
    if desc:
        result["Sample Description"] = desc

    # Availability
    avail = get_text(chars, "availability")
    if avail:
        result["Availability"] = avail

    # Same as (from relationships)
    same_as = relationships.get("same as", [])
    ebi_equiv = relationships.get("ebi equivalent biosample", [])
    all_same = same_as + ebi_equiv
    if all_same:
        result["Same as"] = all_same[0]  # Take first

    return result


# ── Per-type field mappings ─────────────────────────────────────────────────

def _map_organism(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map organism-specific fields."""
    result: dict[str, Any] = {}

    # Organism
    org_text = get_text(chars, "Organism") or get_text(chars, "organism")
    org_term = get_ontology_term(chars, "Organism") or get_ontology_term(chars, "organism")
    if org_text:
        result["Organism"] = org_text
    if org_term:
        result["Organism Term Source ID"] = org_term

    # Sex
    sex_text = get_text(chars, "Sex") or get_text(chars, "sex")
    sex_term = get_ontology_term(chars, "Sex") or get_ontology_term(chars, "sex")
    if sex_text:
        result["Sex"] = sex_text
    if sex_term:
        result["Sex Term Source ID"] = sex_term

    # Breed (or strain)
    breed_text = get_text(chars, "breed") or get_text(chars, "strain")
    breed_term = get_ontology_term(chars, "breed") or get_ontology_term(chars, "strain")
    if breed_text:
        result["Breed"] = breed_text
    if breed_term:
        result["Breed Term Source ID"] = breed_term

    # Birth date
    birth_date = get_text(chars, "birth date")
    birth_date_unit = get_unit(chars, "birth date")
    if birth_date:
        result["Birth Date"] = birth_date
    if birth_date_unit:
        result["Unit"] = birth_date_unit  # Pydantic alias is "Unit" for birth_date_unit

    # Birth location
    birth_loc = get_text(chars, "birth location")
    if birth_loc:
        result["Birth Location"] = birth_loc

    # Birth location lat/long
    for field, alias_prefix in [
        ("birth location latitude", "Birth Location Latitude"),
        ("birth location longitude", "Birth Location Longitude"),
    ]:
        val = get_text(chars, field)
        unit = get_unit(chars, field)
        if val:
            result[alias_prefix] = val
        if unit:
            result[f"{alias_prefix} Unit"] = unit

    # Birth weight, placental weight, pregnancy length
    for field, alias in [
        ("birth weight", "Birth Weight"),
        ("placental weight", "Placental Weight"),
        ("pregnancy length", "Pregnancy Length"),
    ]:
        val = get_text(chars, field)
        unit = get_unit(chars, field)
        if val:
            result[alias] = val
        if unit:
            result[f"{alias} Unit"] = unit

    # Scalar fields
    for field, alias in [
        ("delivery timing", "Delivery Timing"),
        ("delivery ease", "Delivery Ease"),
        ("pedigree", "Pedigree"),
    ]:
        val = get_text(chars, field)
        if val:
            result[alias] = val

    # Health status (multi-value)
    health = get_multi_values(chars, "health status")
    if health:
        result["Health Status"] = health

    # Child Of (from relationships)
    child_of = relationships.get("child of", [])
    if child_of:
        result["Child Of"] = child_of[:2]  # Max 2 parents

    return result


def _map_specimen(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map specimen from organism specific fields."""
    result: dict[str, Any] = {}

    # Specimen collection date
    val = get_text(chars, "specimen collection date")
    unit = get_unit(chars, "specimen collection date")
    if val:
        result["Specimen Collection Date"] = val
    if unit:
        result["Unit"] = unit  # Pydantic alias is "Unit" for specimen_collection_date_unit

    # Animal age at collection
    val = get_text(chars, "animal age at collection")
    unit = get_unit(chars, "animal age at collection")
    if val:
        result["Animal Age At Collection"] = val
    if unit:
        result["Animal Age At Collection Unit"] = unit

    # Developmental stage
    dev_text = get_text(chars, "developmental stage")
    dev_term = get_ontology_term(chars, "developmental stage")
    if dev_text:
        result["Developmental Stage"] = dev_text
    if dev_term:
        result["Developmental Stage Term Source ID"] = dev_term

    # Organism part
    org_part_text = get_text(chars, "organism part")
    org_part_term = get_ontology_term(chars, "organism part")
    if org_part_text:
        result["Organism Part"] = org_part_text
    if org_part_term:
        result["Organism Part Term Source ID"] = org_part_term

    # Specimen collection protocol
    protocol = get_text(chars, "specimen collection protocol")
    if protocol:
        result["Specimen Collection Protocol"] = protocol

    # Fasted status
    val = get_text(chars, "fasted status")
    if val:
        result["Fasted Status"] = val

    # Numeric fields with units
    for field, alias in [
        ("number of pieces", "Number of Pieces"),
        ("specimen volume", "Specimen Volume"),
        ("specimen size", "Specimen Size"),
        ("specimen weight", "Specimen Weight"),
        ("gestational age at sample collection", "Gestational Age At Sample Collection"),
    ]:
        val = get_text(chars, field)
        unit = get_unit(chars, field)
        if val:
            result[alias] = val
        if unit:
            result[f"{alias} Unit"] = unit

    # Specimen picture URL (multi-value text)
    pics = chars.get("specimen picture url", [])
    if pics:
        result["Specimen Picture URL"] = [e.get("text", "") for e in pics if e.get("text")]

    # Health status
    health = get_multi_values(chars, "health status")
    if health:
        result["Health Status"] = health

    # Geographic location
    geo = get_text(chars, "geographic location")
    if geo:
        result["Geographic Location"] = geo

    # Derived from (from relationships)
    derived_from = relationships.get("derived from", [])
    if derived_from:
        result["Derived From"] = derived_from

    return result


def _map_cell_specimen(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map cell specimen specific fields."""
    result: dict[str, Any] = {}

    # Cell type (multi-value)
    cell_types = get_multi_values(chars, "cell type")
    if cell_types:
        result["Cell Type"] = cell_types

    # Markers
    markers = get_text(chars, "markers")
    if markers:
        result["Markers"] = markers

    # Purification protocol
    protocol = get_text(chars, "purification protocol")
    if protocol:
        result["Purification Protocol"] = protocol

    # Derived from
    derived_from = relationships.get("derived from", [])
    if derived_from:
        result["Derived From"] = derived_from

    return result


def _map_cell_culture(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map cell culture specific fields."""
    result: dict[str, Any] = {}

    # Culture type
    ct_text = get_text(chars, "culture type")
    ct_term = get_ontology_term(chars, "culture type")
    if ct_text:
        result["Culture Type"] = ct_text
    if ct_term:
        result["Culture Type Term Source ID"] = ct_term

    # Cell type (multi-value)
    cell_types = get_multi_values(chars, "cell type")
    if cell_types:
        result["Cell Type"] = cell_types

    # Cell culture protocol
    protocol = get_text(chars, "cell culture protocol")
    if protocol:
        result["Cell Culture Protocol"] = protocol

    # Culture conditions
    val = get_text(chars, "culture conditions")
    if val:
        result["Culture Conditions"] = val

    # Number of passages
    val = get_text(chars, "number of passages")
    if val:
        result["Number Of Passages"] = val

    # Derived from
    derived_from = relationships.get("derived from", [])
    if derived_from:
        result["Derived From"] = derived_from

    return result


def _map_cell_line(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map cell line specific fields."""
    result: dict[str, Any] = {}

    # Organism (cell lines have their own, not inherited)
    org_text = get_text(chars, "Organism") or get_text(chars, "organism")
    org_term = get_ontology_term(chars, "Organism") or get_ontology_term(chars, "organism")
    if org_text:
        result["Organism"] = org_text
    if org_term:
        result["Organism Term Source ID"] = org_term

    # Sex
    sex_text = get_text(chars, "Sex") or get_text(chars, "sex")
    sex_term = get_ontology_term(chars, "Sex") or get_ontology_term(chars, "sex")
    if sex_text:
        result["Sex"] = sex_text
    if sex_term:
        result["Sex Term Source ID"] = sex_term

    # Cell line name
    val = get_text(chars, "cell line")
    if val:
        result["Cell Line"] = val

    # Biomaterial provider
    val = get_text(chars, "biomaterial provider")
    if val:
        result["Biomaterial Provider"] = val

    # Catalogue number
    val = get_text(chars, "catalogue number")
    if val:
        result["Catalogue Number"] = val

    # Number of passages
    val = get_text(chars, "number of passages")
    if val:
        result["Number of Passages"] = val

    # Date established
    val = get_text(chars, "date established")
    unit = get_unit(chars, "date established")
    if val:
        result["Date Established"] = val
    if unit:
        result["Date Established Unit"] = unit

    # Publication
    val = get_text(chars, "publication")
    if val:
        result["Publication"] = val

    # Breed
    breed_text = get_text(chars, "breed")
    breed_term = get_ontology_term(chars, "breed")
    if breed_text:
        result["Breed"] = breed_text
    if breed_term:
        result["Breed Term Source ID"] = breed_term

    # Cell type (multi-value)
    cell_types = get_multi_values(chars, "cell type")
    if cell_types:
        result["Cell Type"] = cell_types

    # Culture conditions & protocol
    val = get_text(chars, "culture conditions")
    if val:
        result["Culture Conditions"] = val
    protocol = get_text(chars, "culture protocol")
    if protocol:
        result["Culture Protocol"] = protocol

    # Disease
    disease_text = get_text(chars, "disease")
    disease_term = get_ontology_term(chars, "disease")
    if disease_text:
        result["Disease"] = disease_text
    if disease_term:
        result["Disease Term Source ID"] = disease_term

    # Karyotype
    val = get_text(chars, "karyotype")
    if val:
        result["Karyotype"] = val

    # Derived from (optional for cell lines)
    derived_from = relationships.get("derived from", [])
    if derived_from:
        result["Derived From"] = derived_from

    return result


def _map_pool_of_specimens(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map pool of specimens specific fields."""
    result: dict[str, Any] = {}

    # Pool creation date
    val = get_text(chars, "pool creation date")
    unit = get_unit(chars, "pool creation date")
    if val:
        result["Pool Creation Date"] = val
    if unit:
        result["Pool Creation Date Unit"] = unit

    # Pool creation protocol
    protocol = get_text(chars, "pool creation protocol")
    if protocol:
        result["Pool Creation Protocol"] = protocol

    # Volume/size/weight
    for field, alias in [
        ("specimen volume", "Specimen Volume"),
        ("specimen size", "Specimen Size"),
        ("specimen weight", "Specimen Weight"),
    ]:
        val = get_text(chars, field)
        unit = get_unit(chars, field)
        if val:
            result[alias] = val
        if unit:
            result[f"{alias} Unit"] = unit

    # Specimen picture URL
    pics = chars.get("specimen picture url", [])
    if pics:
        result["Specimen Picture URL"] = [e.get("text", "") for e in pics if e.get("text")]

    # Derived from (multiple parents allowed)
    derived_from = relationships.get("derived from", [])
    if derived_from:
        result["Derived From"] = derived_from

    return result


def _map_organoid(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map organoid specific fields."""
    result: dict[str, Any] = {}

    # Organ model
    val = get_text(chars, "organ model")
    term = get_ontology_term(chars, "organ model")
    if val:
        result["Organ Model"] = val
    if term:
        result["Organ Model Term Source ID"] = term

    # Organ part model
    val = get_text(chars, "organ part model")
    term = get_ontology_term(chars, "organ part model")
    if val:
        result["Organ Part Model"] = val
    if term:
        result["Organ Part Model Term Source ID"] = term

    # Freezing method
    val = get_text(chars, "freezing method")
    if val:
        result["Freezing Method"] = val

    # Freezing date
    val = get_text(chars, "freezing date")
    unit = get_unit(chars, "freezing date")
    if val:
        result["Freezing Date"] = val
    if unit:
        result["Freezing Date Unit"] = unit

    # Freezing protocol
    val = get_text(chars, "freezing protocol")
    if val:
        result["Freezing Protocol"] = val

    # Organoid passage
    val = get_text(chars, "organoid passage")
    if val:
        result["Organoid Passage"] = val

    # Type of organoid culture
    val = get_text(chars, "type of organoid culture")
    if val:
        result["Type Of Organoid Culture"] = val

    # Growth environment
    val = get_text(chars, "growth environment")
    if val:
        result["Growth Environment"] = val

    # Derived from
    derived_from = relationships.get("derived from", [])
    if derived_from:
        result["Derived From"] = derived_from

    return result


def _map_single_cell_specimen(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map single cell specimen specific fields."""
    result: dict[str, Any] = {}

    # Tissue dissociation
    val = get_text(chars, "tissue dissociation")
    if val:
        result["Tissue Dissociation"] = val

    # Cell enrichment
    val = get_text(chars, "cell enrichment")
    if val:
        result["Cell Enrichment"] = val

    # Cell type (multi-value)
    cell_types = get_multi_values(chars, "cell type")
    if cell_types:
        result["Cell Type"] = cell_types

    # Enrichment markers
    val = get_text(chars, "enrichment markers")
    if val:
        result["Enrichment Markers"] = val

    # Single cell isolation protocol
    protocol = get_text(chars, "single cell isolation protocol")
    if protocol:
        result["Single Cell Isolation Protocol"] = protocol

    # Single cell isolation
    val = get_text(chars, "single cell isolation")
    if val:
        result["Single Cell Isolation"] = val

    # Single cell entity
    val = get_text(chars, "single cell entity")
    if val:
        result["Single Cell Entity"] = val

    # Single cell quality
    val = get_text(chars, "single cell quality")
    if val:
        result["Single Cell Quality"] = val

    # Cell number
    val = get_text(chars, "cell number")
    if val:
        result["Cell Number"] = val

    # Derived from
    derived_from = relationships.get("derived from", [])
    if derived_from:
        result["Derived From"] = derived_from

    return result


def _map_teleostei_embryo(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map teleostei embryo specific fields (extends specimen)."""
    # Start with specimen fields
    result = _map_specimen(chars, relationships)

    # Teleostei-specific fields
    for field, alias in [
        ("origin", "Origin"),
        ("reproductive strategy", "Reproductive Strategy"),
        ("hatching", "Hatching"),
        ("growth media", "Growth Media"),
    ]:
        val = get_text(chars, field)
        if val:
            result[alias] = val

    # Numeric fields
    for field, alias in [
        ("time post fertilisation", "Time Post Fertilisation"),
        ("pre-hatching water temperature average", "Pre-hatching Water Temperature Average"),
        ("post-hatching water temperature average", "Post-hatching Water Temperature Average"),
        ("degree days", "Degree Days"),
        ("medium replacement frequency", "Medium Replacement Frequency"),
        ("percentage total somite number", "Percentage Total Somite Number"),
        ("average water salinity", "Average Water Salinity"),
    ]:
        val = get_text(chars, field)
        unit = get_unit(chars, field)
        if val:
            result[alias] = val
        if unit:
            result[f"{alias} Unit"] = unit

    # Photoperiod
    val = get_text(chars, "photoperiod")
    if val:
        result["Photoperiod"] = val

    # Enforce single parent for teleostei
    if "Derived From" in result and len(result["Derived From"]) > 1:
        logger.warning(
            "Teleostei embryo has multiple parents, using first: %s",
            result["Derived From"],
        )
        result["Derived From"] = result["Derived From"][:1]

    return result


def _map_teleostei_post_hatching(chars: dict, relationships: dict) -> dict[str, Any]:
    """Map teleostei post-hatching specific fields (extends teleostei embryo)."""
    # Start with teleostei embryo fields
    result = _map_teleostei_embryo(chars, relationships)

    # Post-hatching specific fields
    for field, alias in [
        ("gonad type", "Gonad Type"),
        ("method of euthanasia", "Method Of Euthanasia"),
        ("water rearing system", "Water Rearing System"),
    ]:
        val = get_text(chars, field)
        if val:
            result[alias] = val

    # Maturity state
    val = get_text(chars, "maturity state")
    term = get_ontology_term(chars, "maturity state")
    if val:
        result["Maturity State"] = val
    if term:
        result["Maturity State Term Source ID"] = term

    # Numeric fields
    for field, alias in [
        ("post-hatching animal density", "Post-hatching Animal Density"),
        ("food restriction", "Food Restriction"),
        ("sampling weight", "Sampling Weight"),
        ("average water oxygen", "Average Water Oxygen"),
    ]:
        val = get_text(chars, field)
        unit = get_unit(chars, field)
        if val:
            result[alias] = val
        if unit:
            result[f"{alias} Unit"] = unit

    return result


# ── Mapping dispatch ────────────────────────────────────────────────────────

TYPE_MAPPER = {
    "organism": _map_organism,
    "specimen from organism": _map_specimen,
    "cell specimen": _map_cell_specimen,
    "cell culture": _map_cell_culture,
    "cell line": _map_cell_line,
    "pool of specimens": _map_pool_of_specimens,
    "organoid": _map_organoid,
    "single cell specimen": _map_single_cell_specimen,
    "teleostei embryo": _map_teleostei_embryo,
    "teleostei post-hatching": _map_teleostei_post_hatching,
}

# Known characteristics per type (lowercase) — used to identify custom fields
# Includes base fields common to all types
_COMMON_KNOWN = {
    "description", "material", "organism", "project",
    "secondary project", "availability", "same as",
}

_TYPE_KNOWN_FIELDS: dict[str, set] = {
    "organism": {
        "sex", "birth date", "breed", "strain", "health status",
        "birth location", "birth location longitude", "birth location latitude",
        "birth weight", "placental weight", "pregnancy length",
        "delivery timing", "delivery ease", "pedigree",
    },
    "specimen from organism": {
        "specimen collection date", "animal age at collection",
        "developmental stage", "health status",
        "organism part", "specimen collection protocol", "fasted status",
        "number of pieces", "specimen volume", "specimen size",
        "specimen weight", "specimen picture url",
        "gestational age at sample collection", "geographic location",
    },
    "cell specimen": {"markers", "cell type", "purification protocol"},
    "cell culture": {
        "culture type", "cell type", "cell culture protocol",
        "culture conditions", "number of passages",
    },
    "cell line": {
        "organism", "sex", "cell line", "biomaterial provider",
        "catalogue number", "number of passages", "date established",
        "publication", "breed", "cell type", "culture conditions",
        "culture protocol", "disease", "karyotype",
    },
    "pool of specimens": {
        "pool creation date", "pool creation protocol",
        "specimen volume", "specimen size", "specimen weight",
        "specimen picture url",
    },
    "organoid": {
        "organ model", "organ part model", "freezing method",
        "freezing date", "freezing protocol", "organoid passage",
        "type of organoid culture", "growth environment",
    },
    "single cell specimen": {
        "tissue dissociation", "cell enrichment", "cell type",
        "enrichment markers", "single cell isolation protocol",
        "single cell isolation", "single cell entity",
        "single cell quality", "cell number",
    },
    "teleostei embryo": {
        # Inherits specimen fields plus:
        "origin", "reproductive strategy", "hatching", "growth media",
        "time post fertilisation",
        "pre-hatching water temperature average",
        "post-hatching water temperature average",
        "degree days", "medium replacement frequency",
        "percentage total somite number", "average water salinity",
        "photoperiod",
    },
    "teleostei post-hatching": {
        # Inherits teleostei embryo fields plus:
        "gonad type", "method of euthanasia", "maturity state",
        "post-hatching animal density", "food restriction",
        "sampling weight", "water rearing system", "average water oxygen",
    },
}

# Teleostei types inherit specimen known fields
_TYPE_KNOWN_FIELDS["teleostei embryo"] |= _TYPE_KNOWN_FIELDS["specimen from organism"]
_TYPE_KNOWN_FIELDS["teleostei post-hatching"] |= _TYPE_KNOWN_FIELDS["teleostei embryo"]


def _extract_custom_fields(
    chars: dict, material_type: str
) -> list[dict[str, Any]]:
    """Extract characteristics not in known fields as custom fields."""
    known = _COMMON_KNOWN | _TYPE_KNOWN_FIELDS.get(material_type, set())
    custom: list[dict[str, Any]] = []

    for field_name, entries in chars.items():
        if field_name.lower() in known:
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            item: dict[str, Any] = {
                "name": field_name,
                "value": entry.get("text", ""),
            }
            unit = entry.get("unit")
            if unit:
                item["unit"] = unit
            ont_terms = entry.get("ontologyTerms", [])
            if ont_terms:
                item["ontologyTerms"] = ont_terms[0]
            custom.append(item)

    return custom


# ── Public API ──────────────────────────────────────────────────────────────

def map_samples(
    material_type: str, samples: list[dict]
) -> list[dict[str, Any]]:
    """Map a list of BioSamples API responses to Pydantic input format.

    Returns list of dicts:
        {accession, pydantic_dict, custom_fields, raw_sample}
    """
    mapper_fn = TYPE_MAPPER.get(material_type)
    if not mapper_fn:
        raise ValueError(f"No mapper for material type: {material_type}")

    results = []
    for sample in samples:
        accession = sample.get("accession", "unknown")
        chars = sample.get("characteristics", {})
        relationships = extract_relationships(sample)

        # Pass 1: base fields + type-specific fields
        pydantic_dict = map_base_fields(sample, relationships)
        type_fields = mapper_fn(chars, relationships)
        pydantic_dict.update(type_fields)

        # Pass 2: custom fields (everything not in known fields)
        custom_fields = _extract_custom_fields(chars, material_type)

        results.append({
            "accession": accession,
            "pydantic_dict": pydantic_dict,
            "custom_fields": custom_fields,
            "raw_sample": sample,
        })

    logger.info("Mapped %d %s samples", len(results), material_type)
    return results
