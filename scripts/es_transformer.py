"""Transform validated sample data into legacy Elasticsearch document format."""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_date(iso_str: str) -> str:
    """Extract YYYY-MM-DD from ISO format date string."""
    if not iso_str:
        return ""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", iso_str)
    return match.group(1) if match else iso_str


def extract_id_number(accession: str) -> str:
    """Extract numeric portion from BioSamples accession.

    SAMEA9835834 -> 9835834, SAMN12345 -> 12345
    """
    match = re.search(r"(\d+)$", accession)
    return match.group(1) if match else accession


def get_filename_from_url(url: str) -> str:
    """Extract filename from URL if it's a file link."""
    if not url:
        return ""
    if url.lower().endswith(".pdf"):
        return url.rsplit("/", 1)[-1]
    return url


def _build_text_ontology(
    chars: dict, field: str
) -> dict[str, Any]:
    """Build {text, ontologyTerms} dict from characteristics field."""
    entries = chars.get(field, [])
    if not entries:
        return {}
    entry = entries[0]
    result: dict[str, Any] = {"text": entry.get("text", "")}
    ont_terms = entry.get("ontologyTerms", [])
    if ont_terms:
        result["ontologyTerms"] = ont_terms[0]
    return result


def _build_text_unit(chars: dict, field: str) -> dict[str, Any]:
    """Build {text, unit} dict from characteristics field."""
    entries = chars.get(field, [])
    if not entries:
        return {"text": None, "unit": None}
    entry = entries[0]
    return {"text": entry.get("text"), "unit": entry.get("unit")}


def _build_protocol(chars: dict, field: str) -> dict[str, Any]:
    """Build {url, filename} dict from a protocol URL field."""
    entries = chars.get(field, [])
    if not entries:
        return {}
    url = entries[0].get("text", "")
    return {"url": url, "filename": get_filename_from_url(url)}


def _build_multi_text_ontology(
    chars: dict, field: str
) -> list[dict[str, Any]]:
    """Build list of {text, ontologyTerms} from multi-value field."""
    entries = chars.get(field, [])
    result = []
    for entry in entries:
        item: dict[str, Any] = {"text": entry.get("text", "")}
        ont_terms = entry.get("ontologyTerms", [])
        if ont_terms:
            item["ontologyTerms"] = ont_terms[0]
        result.append(item)
    return result


def _extract_organization(sample: dict) -> list[dict[str, str]]:
    """Extract organization info from sample."""
    # Legacy format: item['organization'] array
    orgs = sample.get("organization", [])
    if orgs and isinstance(orgs, list) and isinstance(orgs[0], dict):
        return [
            {
                "name": o.get("Name", ""),
                "role": o.get("Role", ""),
                "URL": o.get("URL", ""),
            }
            for o in orgs
        ]

    # Alternative: from characteristics
    chars = sample.get("characteristics", {})
    org_names = chars.get("organization name", [])
    org_roles = chars.get("organization role", [])
    org_uris = chars.get("organization uri", [])

    if org_names:
        result = []
        for i, name_entry in enumerate(org_names):
            org: dict[str, str] = {"name": name_entry.get("text", "")}
            if i < len(org_roles):
                org["role"] = org_roles[i].get("text", "")
            if i < len(org_uris):
                org["URL"] = org_uris[i].get("text", "")
            result.append(org)
        return result

    return []


def build_common_fields(
    raw_sample: dict, custom_fields: list[dict], validation_status: str
) -> dict[str, Any]:
    """Build fields common to all ES document types."""
    chars = raw_sample.get("characteristics", {})
    accession = raw_sample.get("accession", "")

    # Material
    material_entries = chars.get("Material") or chars.get("material", [])
    material = {}
    if material_entries:
        material = {
            "text": material_entries[0].get("text", ""),
        }
        ont = material_entries[0].get("ontologyTerms", [])
        if ont:
            material["ontologyTerms"] = ont[0]

    # Secondary project — single value as string, multiple as array (matches legacy)
    secondary_list = [
        e.get("text", "") for e in chars.get("secondary project", []) if e.get("text")
    ]
    if len(secondary_list) == 1:
        secondary = secondary_list[0]
    else:
        secondary = secondary_list

    doc: dict[str, Any] = {
        "name": raw_sample.get("name", ""),
        "biosampleId": accession,
        "id_number": extract_id_number(accession),
        "description": (chars.get("description", [{}])[0].get("text")
                        if chars.get("description") else None),
        "releaseDate": parse_date(raw_sample.get("release", "")),
        "updateDate": parse_date(raw_sample.get("update", "")),
        "material": material,
        "project": "FAANG",
        "secondaryProject": secondary,
        "availability": (chars.get("availability", [{}])[0].get("text")
                         if chars.get("availability") else None),
        "organization": _extract_organization(raw_sample),
        "customField": custom_fields,
        "standardMet": "FAANG" if validation_status != "error" else "FAANG error",
        "etag": "",
        "paperPublished": "",
    }

    return doc


def _get_organism_info_from_parent(
    parent_accession: str, processed_documents: dict[str, dict]
) -> dict[str, Any]:
    """Get organism info from a processed parent document."""
    parent = processed_documents.get(parent_accession, {})
    if not parent:
        return {}

    # If parent is an organism, use its organism/sex/breed directly
    material = parent.get("material", {}).get("text", "")
    if material == "organism":
        return {
            "organism": parent.get("organism", {}),
            "sex": parent.get("sex", {}),
            "breed": parent.get("breed", {}),
            "biosampleId": parent.get("biosampleId", ""),
        }

    # If parent is a specimen or other, look for inherited organism info
    return parent.get("_organism_info", {})


def _build_organism_nested(org_info: dict[str, Any]) -> dict[str, Any]:
    """Build the nested organism object for non-organism types.

    Specimen mapping expects: organism: { biosampleId, organism, sex, breed, healthStatus }
    """
    if not org_info:
        return {}
    return {
        "biosampleId": org_info.get("biosampleId", ""),
        "organism": org_info.get("organism", {}),
        "sex": org_info.get("sex", {}),
        "breed": org_info.get("breed", {}),
    }


def _walk_derived_from_chain(
    accession: str, processed_documents: dict[str, dict]
) -> list[str]:
    """Walk the derived_from chain to collect all specimen accessions."""
    specimens = []
    visited = set()
    current = accession

    while current and current not in visited:
        visited.add(current)
        doc = processed_documents.get(current)
        if not doc:
            break

        material = doc.get("material", {}).get("text", "")
        if material != "organism":
            specimens.append(current)

        # Get parent
        derived = doc.get("_derived_from_accessions", [])
        if derived:
            current = derived[0]
        else:
            break

    return specimens


# ── Type-specific transformers ──────────────────────────────────────────────

def _transform_organism(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add organism-specific fields to ES document."""
    chars = raw_sample.get("characteristics", {})
    rels = raw_sample.get("relationships", [])
    accession = raw_sample.get("accession", "")

    # Core organism fields
    doc["organism"] = (
        _build_text_ontology(chars, "Organism")
        or _build_text_ontology(chars, "organism")
    )
    doc["sex"] = (
        _build_text_ontology(chars, "Sex")
        or _build_text_ontology(chars, "sex")
    )
    doc["breed"] = (
        _build_text_ontology(chars, "breed")
        or _build_text_ontology(chars, "strain")
    )

    # Date/measurement fields
    doc["birthDate"] = _build_text_unit(chars, "birth date")
    doc["birthLocation"] = (chars.get("birth location", [{}])[0].get("text", "")
                            if chars.get("birth location") else "")
    doc["birthLocationLatitude"] = _build_text_unit(chars, "birth location latitude")
    doc["birthLocationLongitude"] = _build_text_unit(chars, "birth location longitude")
    doc["birthWeight"] = _build_text_unit(chars, "birth weight")
    doc["placentalWeight"] = _build_text_unit(chars, "placental weight")
    doc["pregnancyLength"] = _build_text_unit(chars, "pregnancy length")
    doc["deliveryTiming"] = (chars.get("delivery timing", [{}])[0].get("text", "")
                             if chars.get("delivery timing") else "")
    doc["deliveryEase"] = (chars.get("delivery ease", [{}])[0].get("text", "")
                           if chars.get("delivery ease") else "")
    doc["pedigree"] = (chars.get("pedigree", [{}])[0].get("text", "")
                       if chars.get("pedigree") else "")

    # Health status
    doc["healthStatus"] = _build_multi_text_ontology(chars, "health status")

    # Relationships
    child_of = []
    same_as = []
    for rel in rels:
        if rel.get("source") != accession:
            continue
        rel_type = rel.get("type", "").lower()
        target = rel.get("target", "")
        if rel_type == "child of":
            child_of.append(target)
        elif rel_type in ("same as", "ebi equivalent biosample"):
            same_as.append(target)

    doc["childOf"] = child_of
    doc["alternativeId"] = same_as

    return doc


def _transform_specimen(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add specimen-specific fields to ES document."""
    chars = raw_sample.get("characteristics", {})
    rels = raw_sample.get("relationships", [])
    accession = raw_sample.get("accession", "")

    specimen: dict[str, Any] = {}
    specimen["specimenCollectionDate"] = _build_text_unit(chars, "specimen collection date")
    specimen["animalAgeAtCollection"] = _build_text_unit(chars, "animal age at collection")
    specimen["developmentalStage"] = _build_text_ontology(chars, "developmental stage")
    specimen["organismPart"] = _build_text_ontology(chars, "organism part")
    specimen["specimenCollectionProtocol"] = _build_protocol(chars, "specimen collection protocol")
    specimen["fastedStatus"] = (chars.get("fasted status", [{}])[0].get("text", "")
                                if chars.get("fasted status") else "")
    specimen["numberOfPieces"] = _build_text_unit(chars, "number of pieces")
    specimen["specimenVolume"] = _build_text_unit(chars, "specimen volume")
    specimen["specimenSize"] = _build_text_unit(chars, "specimen size")
    specimen["specimenWeight"] = _build_text_unit(chars, "specimen weight")
    specimen["gestationalAgeAtSampleCollection"] = _build_text_unit(
        chars, "gestational age at sample collection"
    )

    # Picture URLs
    pics = [e.get("text", "") for e in chars.get("specimen picture url", []) if e.get("text")]
    specimen["specimenPictureUrl"] = pics

    # Health status at collection
    specimen["healthStatusAtCollection"] = _build_multi_text_ontology(
        chars, "health status at collection"
    )

    doc["specimenFromOrganism"] = specimen

    # Derived from
    derived_from = []
    for rel in rels:
        if rel.get("source") == accession and rel.get("type", "").lower() == "derived from":
            derived_from.append(rel.get("target", ""))

    doc["derivedFrom"] = derived_from[0] if derived_from else ""
    doc["_derived_from_accessions"] = derived_from

    # Resolve organism info from parent
    if derived_from:
        org_info = _get_organism_info_from_parent(derived_from[0], processed_documents)
        doc["organism"] = _build_organism_nested(org_info)
        doc["_organism_info"] = org_info
    else:
        doc["organism"] = {}
        doc["_organism_info"] = {}

    # Cell type from organism part
    doc["cellType"] = _build_text_ontology(chars, "organism part")

    # All derived from specimens
    doc["allDeriveFromSpecimens"] = _walk_derived_from_chain(accession, processed_documents)

    # Alternative ID
    same_as = []
    for rel in rels:
        if rel.get("source") == accession:
            rel_type = rel.get("type", "").lower()
            if rel_type in ("same as", "ebi equivalent biosample"):
                same_as.append(rel.get("target", ""))
    doc["alternativeId"] = same_as

    return doc


def _transform_cell_specimen(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add cell specimen-specific fields to ES document."""
    chars = raw_sample.get("characteristics", {})
    rels = raw_sample.get("relationships", [])
    accession = raw_sample.get("accession", "")

    cell_spec: dict[str, Any] = {}
    cell_spec["markers"] = (chars.get("markers", [{}])[0].get("text", "")
                            if chars.get("markers") else "")
    cell_spec["purificationProtocol"] = _build_protocol(chars, "purification protocol")
    cell_spec["cellType"] = _build_multi_text_ontology(chars, "cell type")

    doc["cellSpecimen"] = cell_spec

    # Derived from
    derived_from = []
    for rel in rels:
        if rel.get("source") == accession and rel.get("type", "").lower() == "derived from":
            derived_from.append(rel.get("target", ""))

    doc["derivedFrom"] = derived_from[0] if derived_from else ""
    doc["_derived_from_accessions"] = derived_from

    # Resolve organism info from parent chain
    if derived_from:
        org_info = _get_organism_info_from_parent(derived_from[0], processed_documents)
        doc["organism"] = _build_organism_nested(org_info)
        doc["_organism_info"] = org_info
    else:
        doc["organism"] = {}
        doc["_organism_info"] = {}

    doc["cellType"] = _build_text_ontology(chars, "cell type") or {}
    doc["allDeriveFromSpecimens"] = _walk_derived_from_chain(accession, processed_documents)

    # Alternative ID
    same_as = []
    for rel in rels:
        if rel.get("source") == accession:
            rel_type = rel.get("type", "").lower()
            if rel_type in ("same as", "ebi equivalent biosample"):
                same_as.append(rel.get("target", ""))
    doc["alternativeId"] = same_as

    return doc


def _transform_cell_culture(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add cell culture-specific fields to ES document."""
    chars = raw_sample.get("characteristics", {})
    rels = raw_sample.get("relationships", [])
    accession = raw_sample.get("accession", "")

    culture: dict[str, Any] = {}
    culture["cultureType"] = _build_text_ontology(chars, "culture type")
    culture["cellType"] = _build_text_ontology(chars, "cell type")
    culture["cellCultureProtocol"] = _build_protocol(chars, "cell culture protocol")
    culture["cultureConditions"] = (chars.get("culture conditions", [{}])[0].get("text", "")
                                    if chars.get("culture conditions") else "")
    culture["numberOfPassages"] = (chars.get("number of passages", [{}])[0].get("text", "")
                                   if chars.get("number of passages") else "")

    doc["cellCulture"] = culture

    # Derived from
    derived_from = []
    for rel in rels:
        if rel.get("source") == accession and rel.get("type", "").lower() == "derived from":
            derived_from.append(rel.get("target", ""))

    doc["derivedFrom"] = derived_from[0] if derived_from else ""
    doc["_derived_from_accessions"] = derived_from

    if derived_from:
        org_info = _get_organism_info_from_parent(derived_from[0], processed_documents)
        doc["organism"] = _build_organism_nested(org_info)
        doc["_organism_info"] = org_info
    else:
        doc["organism"] = {}
        doc["_organism_info"] = {}

    doc["cellType"] = _build_text_ontology(chars, "cell type") or {}
    doc["allDeriveFromSpecimens"] = _walk_derived_from_chain(accession, processed_documents)

    # Alternative ID
    same_as = []
    for rel in rels:
        if rel.get("source") == accession:
            rel_type = rel.get("type", "").lower()
            if rel_type in ("same as", "ebi equivalent biosample"):
                same_as.append(rel.get("target", ""))
    doc["alternativeId"] = same_as

    return doc


def _transform_cell_line(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add cell line-specific fields to ES document (owns organism data)."""
    chars = raw_sample.get("characteristics", {})
    rels = raw_sample.get("relationships", [])
    accession = raw_sample.get("accession", "")

    cell_line: dict[str, Any] = {}
    cell_line["organism"] = (
        _build_text_ontology(chars, "Organism")
        or _build_text_ontology(chars, "organism")
    )
    cell_line["sex"] = (
        _build_text_ontology(chars, "Sex")
        or _build_text_ontology(chars, "sex")
    )
    cell_line["cellLine"] = (chars.get("cell line", [{}])[0].get("text", "")
                             if chars.get("cell line") else "")
    cell_line["biomaterialProvider"] = (
        chars.get("biomaterial provider", [{}])[0].get("text", "")
        if chars.get("biomaterial provider") else ""
    )
    cell_line["catalogueNumber"] = (
        chars.get("catalogue number", [{}])[0].get("text", "")
        if chars.get("catalogue number") else ""
    )
    cell_line["numberOfPassages"] = (
        chars.get("number of passages", [{}])[0].get("text", "")
        if chars.get("number of passages") else ""
    )
    cell_line["dateEstablished"] = _build_text_unit(chars, "date established")
    cell_line["publication"] = (chars.get("publication", [{}])[0].get("text", "")
                                if chars.get("publication") else "")
    cell_line["breed"] = _build_text_ontology(chars, "breed")
    cell_line["cellType"] = _build_text_ontology(chars, "cell type")
    cell_line["cultureConditions"] = (
        chars.get("culture conditions", [{}])[0].get("text", "")
        if chars.get("culture conditions") else ""
    )
    cell_line["cultureProtocol"] = _build_protocol(chars, "culture protocol")
    cell_line["disease"] = _build_text_ontology(chars, "disease")
    cell_line["karyotype"] = (chars.get("karyotype", [{}])[0].get("text", "")
                              if chars.get("karyotype") else "")

    doc["cellLine"] = cell_line

    # Cell line owns its organism data — nest it like other specimen types
    doc["organism"] = {
        "organism": cell_line["organism"],
        "sex": cell_line["sex"],
        "breed": cell_line["breed"],
    }
    doc["cellType"] = cell_line["cellType"]

    # Derived from (optional)
    derived_from = []
    for rel in rels:
        if rel.get("source") == accession and rel.get("type", "").lower() == "derived from":
            derived_from.append(rel.get("target", ""))

    doc["derivedFrom"] = derived_from[0] if derived_from else ""
    doc["_derived_from_accessions"] = derived_from
    doc["allDeriveFromSpecimens"] = _walk_derived_from_chain(accession, processed_documents)

    # Alternative ID
    same_as = []
    for rel in rels:
        if rel.get("source") == accession:
            rel_type = rel.get("type", "").lower()
            if rel_type in ("same as", "ebi equivalent biosample"):
                same_as.append(rel.get("target", ""))
    doc["alternativeId"] = same_as

    return doc


def _transform_pool_of_specimens(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add pool of specimens-specific fields to ES document."""
    chars = raw_sample.get("characteristics", {})
    rels = raw_sample.get("relationships", [])
    accession = raw_sample.get("accession", "")

    pool: dict[str, Any] = {}
    pool["poolCreationDate"] = _build_text_unit(chars, "pool creation date")
    pool["poolCreationProtocol"] = _build_protocol(chars, "pool creation protocol")
    pool["specimenVolume"] = _build_text_unit(chars, "specimen volume")
    pool["specimenSize"] = _build_text_unit(chars, "specimen size")
    pool["specimenWeight"] = _build_text_unit(chars, "specimen weight")

    pics = [e.get("text", "") for e in chars.get("specimen picture url", []) if e.get("text")]
    pool["specimenPictureUrl"] = pics

    doc["poolOfSpecimens"] = pool

    # Derived from (multiple parents)
    derived_from = []
    for rel in rels:
        if rel.get("source") == accession and rel.get("type", "").lower() == "derived from":
            derived_from.append(rel.get("target", ""))

    doc["derivedFrom"] = derived_from
    doc["_derived_from_accessions"] = derived_from
    doc["allDeriveFromSpecimens"] = derived_from  # For pools, same as derivedFrom

    # Resolve organism info from all parents
    organisms_text = []
    sex_text = []
    breed_text = []
    for parent_id in derived_from:
        org_info = _get_organism_info_from_parent(parent_id, processed_documents)
        if org_info:
            org = org_info.get("organism", {})
            if org.get("text"):
                organisms_text.append(org["text"])
            s = org_info.get("sex", {})
            if s.get("text"):
                sex_text.append(s["text"])
            b = org_info.get("breed", {})
            if b.get("text"):
                breed_text.append(b["text"])

    # Concatenate with ";" for multi-source pools — nest like other specimen types
    doc["organism"] = {
        "organism": {"text": ";".join(organisms_text)} if organisms_text else {},
        "sex": {"text": ";".join(sex_text)} if sex_text else {},
        "breed": {"text": ";".join(breed_text)} if breed_text else {},
    }

    # Cell type
    doc["cellType"] = _build_text_ontology(chars, "cell type") or {"text": "Not Applicable"}

    # Alternative ID
    same_as = []
    for rel in rels:
        if rel.get("source") == accession:
            rel_type = rel.get("type", "").lower()
            if rel_type in ("same as", "ebi equivalent biosample"):
                same_as.append(rel.get("target", ""))
    doc["alternativeId"] = same_as

    return doc


def _transform_organoid(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add organoid-specific fields to ES document."""
    chars = raw_sample.get("characteristics", {})
    rels = raw_sample.get("relationships", [])
    accession = raw_sample.get("accession", "")

    organoid: dict[str, Any] = {}
    organoid["organModel"] = _build_text_ontology(chars, "organ model")
    organoid["organPartModel"] = _build_text_ontology(chars, "organ part model")
    organoid["freezingMethod"] = (chars.get("freezing method", [{}])[0].get("text", "")
                                  if chars.get("freezing method") else "")
    organoid["freezingDate"] = _build_text_unit(chars, "freezing date")
    organoid["freezingProtocol"] = _build_protocol(chars, "freezing protocol")
    organoid["organoidPassage"] = (chars.get("organoid passage", [{}])[0].get("text", "")
                                   if chars.get("organoid passage") else "")
    organoid["typeOfOrganoidCulture"] = (
        chars.get("type of organoid culture", [{}])[0].get("text", "")
        if chars.get("type of organoid culture") else ""
    )
    organoid["growthEnvironment"] = (
        chars.get("growth environment", [{}])[0].get("text", "")
        if chars.get("growth environment") else ""
    )

    doc["organoid"] = organoid

    # Derived from
    derived_from = []
    for rel in rels:
        if rel.get("source") == accession and rel.get("type", "").lower() == "derived from":
            derived_from.append(rel.get("target", ""))

    doc["derivedFrom"] = derived_from[0] if derived_from else ""
    doc["_derived_from_accessions"] = derived_from

    if derived_from:
        org_info = _get_organism_info_from_parent(derived_from[0], processed_documents)
        doc["organism"] = _build_organism_nested(org_info)
        doc["_organism_info"] = org_info
    else:
        doc["organism"] = {}
        doc["_organism_info"] = {}

    doc["allDeriveFromSpecimens"] = _walk_derived_from_chain(accession, processed_documents)

    # Alternative ID
    same_as = []
    for rel in rels:
        if rel.get("source") == accession:
            rel_type = rel.get("type", "").lower()
            if rel_type in ("same as", "ebi equivalent biosample"):
                same_as.append(rel.get("target", ""))
    doc["alternativeId"] = same_as

    return doc


def _transform_single_cell_specimen(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add single cell specimen-specific fields to ES document."""
    chars = raw_sample.get("characteristics", {})
    rels = raw_sample.get("relationships", [])
    accession = raw_sample.get("accession", "")

    sc: dict[str, Any] = {}
    sc["tissueDissociation"] = (chars.get("tissue dissociation", [{}])[0].get("text", "")
                                if chars.get("tissue dissociation") else "")
    sc["cellEnrichment"] = (chars.get("cell enrichment", [{}])[0].get("text", "")
                            if chars.get("cell enrichment") else "")
    sc["cellType"] = _build_multi_text_ontology(chars, "cell type")
    sc["enrichmentMarkers"] = (chars.get("enrichment markers", [{}])[0].get("text", "")
                               if chars.get("enrichment markers") else "")
    sc["singleCellIsolationProtocol"] = _build_protocol(chars, "single cell isolation protocol")
    sc["singleCellIsolation"] = (chars.get("single cell isolation", [{}])[0].get("text", "")
                                 if chars.get("single cell isolation") else "")
    sc["singleCellEntity"] = (chars.get("single cell entity", [{}])[0].get("text", "")
                              if chars.get("single cell entity") else "")
    sc["singleCellQuality"] = (chars.get("single cell quality", [{}])[0].get("text", "")
                               if chars.get("single cell quality") else "")
    sc["cellNumber"] = (chars.get("cell number", [{}])[0].get("text", "")
                        if chars.get("cell number") else "")

    doc["singleCellSpecimen"] = sc

    # Derived from
    derived_from = []
    for rel in rels:
        if rel.get("source") == accession and rel.get("type", "").lower() == "derived from":
            derived_from.append(rel.get("target", ""))

    doc["derivedFrom"] = derived_from[0] if derived_from else ""
    doc["_derived_from_accessions"] = derived_from

    if derived_from:
        org_info = _get_organism_info_from_parent(derived_from[0], processed_documents)
        doc["organism"] = _build_organism_nested(org_info)
        doc["_organism_info"] = org_info
    else:
        doc["organism"] = {}
        doc["_organism_info"] = {}

    doc["cellType"] = _build_text_ontology(chars, "cell type") or {}
    doc["allDeriveFromSpecimens"] = _walk_derived_from_chain(accession, processed_documents)

    # Alternative ID
    same_as = []
    for rel in rels:
        if rel.get("source") == accession:
            rel_type = rel.get("type", "").lower()
            if rel_type in ("same as", "ebi equivalent biosample"):
                same_as.append(rel.get("target", ""))
    doc["alternativeId"] = same_as

    return doc


def _transform_teleostei_embryo(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add teleostei embryo-specific fields (extends specimen)."""
    # First apply specimen transform
    _transform_specimen(raw_sample, doc, processed_documents)

    chars = raw_sample.get("characteristics", {})

    teleostei: dict[str, Any] = {}
    for field, key in [
        ("origin", "origin"),
        ("reproductive strategy", "reproductiveStrategy"),
        ("hatching", "hatching"),
        ("growth media", "growthMedia"),
    ]:
        val = chars.get(field, [{}])
        teleostei[key] = val[0].get("text", "") if val else ""

    for field, key in [
        ("time post fertilisation", "timePostFertilisation"),
        ("pre-hatching water temperature average", "preHatchingWaterTemperatureAverage"),
        ("post-hatching water temperature average", "postHatchingWaterTemperatureAverage"),
        ("degree days", "degreeDays"),
        ("medium replacement frequency", "mediumReplacementFrequency"),
        ("percentage total somite number", "percentageTotalSomiteNumber"),
        ("average water salinity", "averageWaterSalinity"),
    ]:
        teleostei[key] = _build_text_unit(chars, field)

    photoperiod = chars.get("photoperiod", [{}])
    teleostei["photoperiod"] = photoperiod[0].get("text", "") if photoperiod else ""

    doc["teleosteiEmbryo"] = teleostei
    return doc


def _transform_teleostei_post_hatching(
    raw_sample: dict, doc: dict, processed_documents: dict
) -> dict[str, Any]:
    """Add teleostei post-hatching fields (extends teleostei embryo)."""
    _transform_teleostei_embryo(raw_sample, doc, processed_documents)

    chars = raw_sample.get("characteristics", {})

    post_hatching: dict[str, Any] = doc.get("teleosteiEmbryo", {}).copy()

    for field, key in [
        ("gonad type", "gonadType"),
        ("method of euthanasia", "methodOfEuthanasia"),
        ("water rearing system", "waterRearingSystem"),
    ]:
        val = chars.get(field, [{}])
        post_hatching[key] = val[0].get("text", "") if val else ""

    post_hatching["maturityState"] = _build_text_ontology(chars, "maturity state")

    for field, key in [
        ("post-hatching animal density", "postHatchingAnimalDensity"),
        ("food restriction", "foodRestriction"),
        ("sampling weight", "samplingWeight"),
        ("average water oxygen", "averageWaterOxygen"),
    ]:
        post_hatching[key] = _build_text_unit(chars, field)

    # Replace embryo key with post-hatching key
    doc.pop("teleosteiEmbryo", None)
    doc["teleosteiPostHatching"] = post_hatching
    return doc


# ── Dispatch ────────────────────────────────────────────────────────────────

_TYPE_TRANSFORMERS = {
    "organism": _transform_organism,
    "specimen from organism": _transform_specimen,
    "cell specimen": _transform_cell_specimen,
    "cell culture": _transform_cell_culture,
    "cell line": _transform_cell_line,
    "pool of specimens": _transform_pool_of_specimens,
    "organoid": _transform_organoid,
    "single cell specimen": _transform_single_cell_specimen,
    "teleostei embryo": _transform_teleostei_embryo,
    "teleostei post-hatching": _transform_teleostei_post_hatching,
}


def transform_to_es_document(
    material_type: str,
    raw_sample: dict,
    pydantic_data: dict,
    custom_fields: list[dict],
    processed_documents: dict[str, dict],
    validation_status: str,
) -> dict[str, Any]:
    """Transform a validated sample into a legacy ES document.

    Args:
        material_type: The base material type string.
        raw_sample: Original BioSamples API response dict.
        pydantic_data: model_dump() output from validated Pydantic model.
        custom_fields: Unmapped characteristics for customField array.
        processed_documents: {accession: es_doc} of already-processed samples.
        validation_status: 'pass', 'warning', or 'error'.

    Returns:
        ES document dict.
    """
    doc = build_common_fields(raw_sample, custom_fields, validation_status)

    transformer = _TYPE_TRANSFORMERS.get(material_type)
    if transformer:
        transformer(raw_sample, doc, processed_documents)
    else:
        logger.warning("No transformer for material type: %s", material_type)

    # Store organism info for child resolution (internal, stripped before output)
    if material_type == "organism":
        doc["_organism_info"] = {
            "organism": doc.get("organism", {}),
            "sex": doc.get("sex", {}),
            "breed": doc.get("breed", {}),
            "biosampleId": doc.get("biosampleId", ""),
        }

    return doc


def clean_internal_fields(doc: dict) -> dict:
    """Remove internal fields (prefixed with _) before writing to JSON."""
    return {k: v for k, v in doc.items() if not k.startswith("_")}
