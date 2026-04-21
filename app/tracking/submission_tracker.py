import logging
from datetime import datetime
from typing import Any, Optional

from lxml import etree

from .es_client import get_es_client


logger = logging.getLogger(__name__)

SUBMISSIONS_INDEX = "submissions"


def save_submission_data(
    receipt_root: etree._Element,
    original_xml_roots: dict,
    submission_type: str,
    action: str = "submission",
) -> list[dict]:

    if receipt_root.get("success") != "true":
        logger.info("save_submission_data: receipt success != 'true', skipping.")
        return []

    if submission_type == "experiments":
        study_objs = parse_experiments_data(
            receipt_root, original_xml_roots.get("experiment"), action
        )
    elif submission_type == "analyses":
        study_objs = parse_analysis_data(
            receipt_root, original_xml_roots.get("analysis"), action
        )
    else:
        logger.warning(
            "save_submission_data: unknown submission_type %r", submission_type
        )
        return []

    if not study_objs:
        logger.info("save_submission_data: no study objects produced from receipt.")
        return []

    es = get_es_client()
    written: list[dict] = []
    for study_obj in study_objs:
        study_id = study_obj.get("study_id")
        if not study_id:
            logger.warning(
                "save_submission_data: skipping study object with empty study_id: %r",
                study_obj,
            )
            continue

        existing = get_doc(study_id)
        if existing is not None:
            if "submission_date" in existing:
                study_obj["submission_date"] = existing["submission_date"]

            if "subscribers" in existing:
                study_obj["subscribers"] = existing["subscribers"]

        print("study_id --->", study_id)
        print("study_obj --->", study_obj)
        es.index(index=SUBMISSIONS_INDEX, id=study_id, body=study_obj)
        written.append(study_obj)
        logger.info(
            "save_submission_data: indexed study_id=%s action=%s",
            study_id, action,
        )

    return written


def get_doc(study_id: str) -> Optional[dict]:
    es = get_es_client()
    query = {
        "query": {
            "bool": {
                "filter": [{"terms": {"study_id": [study_id]}}]
            }
        }
    }
    data = es.search(
        index=SUBMISSIONS_INDEX,
        size=1,
        from_=0,
        track_total_hits=True,
        body=query,
    )
    hits = data.get("hits", {}).get("hits", [])
    if hits and hits[0].get("_source"):
        return hits[0]["_source"]
    return None


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

def parse_experiments_data(
    receipt_root: etree._Element,
    experiment_xml_root: Optional[etree._Element],
    action: str,
) -> list[dict]:
    if receipt_root.get("success") != "true":
        return []

    object_types = {
        "EXPERIMENT": "experiments",
        "STUDY": "studies",
        "PROJECT": "studies",
    }

    submission_elts = receipt_root.findall("SUBMISSION")
    if not submission_elts:
        logger.warning("parse_experiments_data: no SUBMISSION element in receipt.")
        return []
    submission_elt = submission_elts[0]

    submission_data: dict[str, Any] = {
        "alias": submission_elt.get("alias") or "",
        "accession": submission_elt.get("accession") or "",
    }

    # Harvest aliases + accessions for studies + experiments from the receipt.
    for xml_tag, field in object_types.items():
        objects = receipt_root.findall(xml_tag)
        if not objects:
            continue
        submission_data.setdefault(field, [])
        for obj in objects:
            obj_data = {"alias": obj.get("alias") or ""}
            if field == "studies":
                # Study accessions live on an EXT_ID child, not on the
                # STUDY element itself. ENA quirk.
                ext_ids = obj.findall("EXT_ID")
                obj_data["accession"] = (
                    ext_ids[0].get("accession") if ext_ids else ""
                )
            else:
                obj_data["accession"] = obj.get("accession") or ""
            submission_data[field].append(obj_data)

    study_objs: list[dict] = []
    current_date = datetime.today().strftime("%Y-%m-%d")

    for study in submission_data.get("studies", []):
        study_obj: dict[str, Any] = {
            "study_id": study["accession"],
            "study_alias": study["alias"],
            "experiments": [],
            "available_in_portal": "false",
        }
        if action == "submission":
            study_obj["submission_date"] = current_date
        elif action == "update":
            study_obj["update_date"] = current_date


        if experiment_xml_root is not None:
            assay_types: list[str] = []
            secondary_projects: list[str] = []

            for exp in experiment_xml_root.findall("EXPERIMENT"):
                study_refs = exp.findall("STUDY_REF")
                if not study_refs:
                    continue
                if study_refs[0].get("refname") != study["alias"]:
                    continue

                # match experiment alias against receipt to pick up its accession.
                exp_alias = exp.get("alias")
                for experiment in submission_data.get("experiments", []):
                    if experiment["alias"] == exp_alias:
                        study_obj["experiments"].append({
                            "alias": experiment["alias"],
                            "accession": experiment["accession"],
                            "available_in_portal": "false",
                        })

                # pull tag/value pairs from EXPERIMENT_ATTRIBUTES.
                attr_containers = exp.findall("EXPERIMENT_ATTRIBUTES")
                if not attr_containers:
                    continue
                for attr in attr_containers[0].findall("EXPERIMENT_ATTRIBUTE"):
                    tag = _first_text(attr, "TAG")
                    value = _first_text(attr, "VALUE")
                    if tag == "assay type" and value:
                        assay_types.append(value)
                    elif tag == "secondary project" and value:
                        secondary_projects.append(value)

            study_obj["assay_type"] = ", ".join(sorted(set(assay_types)))
            study_obj["secondary_project"] = ", ".join(
                sorted(set(secondary_projects))
            )

        study_objs.append(study_obj)

    return study_objs


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------

def parse_analysis_data(
    receipt_root: etree._Element,
    analysis_xml_root: Optional[etree._Element],
    action: str,
) -> list[dict]:
    """
    Build one study-tracking object per unique study_id referenced by
    the submitted analyses.

    The receipt gives us (alias -> accession) for each ANALYSIS. The
    original analysis XML gives us the STUDY_REF accession that
    anchors each analysis to a study, plus the `Assay Type` and
    `Secondary Project` attributes (note the capitalisation — the old
    code uses capitalised tags for analyses but lowercase for
    experiments, and we preserve that quirk).

    :param receipt_root: parsed ENA receipt
    :param analysis_xml_root: parsed original analysis XML
    :param action: 'submission' or 'update'
    """
    if receipt_root.get("success") != "true":
        return []

    receipt_analyses = receipt_root.findall("ANALYSIS")
    if not receipt_analyses:
        return []

    # Step 1: seed a per-analysis dict from the receipt.
    analyses_objs: dict[str, dict] = {}
    for obj in receipt_analyses:
        alias = obj.get("alias")
        if not alias:
            continue
        analyses_objs[alias] = {
            "alias": alias,
            "accession": obj.get("accession") or "",
            "study_id": "",
            "assay_type": "",
            "secondary_project": "",
        }

    # Step 2: enrich with study_id + attributes from the original XML.
    if analysis_xml_root is not None:
        for a in analysis_xml_root.findall("ANALYSIS"):
            a_alias = a.get("alias")
            if a_alias not in analyses_objs:
                continue

            study_refs = a.findall("STUDY_REF")
            if study_refs:
                analyses_objs[a_alias]["study_id"] = (
                    study_refs[0].get("accession") or ""
                )

            attr_containers = a.findall("ANALYSIS_ATTRIBUTES")
            if not attr_containers:
                continue
            for attr in attr_containers[0].findall("ANALYSIS_ATTRIBUTE"):
                tag = _first_text(attr, "TAG")
                value = _first_text(attr, "VALUE")
                if tag == "Assay Type":
                    analyses_objs[a_alias]["assay_type"] = value or ""
                elif tag == "Secondary Project":
                    analyses_objs[a_alias]["secondary_project"] = value or ""

    # Step 3: group analyses by study_id.
    current_date = datetime.today().strftime("%Y-%m-%d")
    study_objs_dict: dict[str, dict] = {}

    for analysis in analyses_objs.values():
        sid = analysis["study_id"]
        if sid not in study_objs_dict:
            study_objs_dict[sid] = {
                "study_id": sid,
                "study_alias": "",
                "assay_type": [],
                "secondary_project": [],
                "analyses": [],
                "available_in_portal": "false",
            }
            if action == "submission":
                study_objs_dict[sid]["submission_date"] = current_date
            elif action == "update":
                study_objs_dict[sid]["update_date"] = current_date

        study_objs_dict[sid]["analyses"].append({
            "alias": analysis["alias"],
            "accession": analysis["accession"],
            "available_in_portal": "false",
        })
        if analysis["assay_type"]:
            study_objs_dict[sid]["assay_type"].append(analysis["assay_type"])
        if analysis["secondary_project"]:
            study_objs_dict[sid]["secondary_project"].append(
                analysis["secondary_project"]
            )

    # Step 4: flatten the assay_type / secondary_project lists.
    for study_obj in study_objs_dict.values():
        study_obj["assay_type"] = ", ".join(sorted(set(study_obj["assay_type"])))
        study_obj["secondary_project"] = ", ".join(
            sorted(set(study_obj["secondary_project"]))
        )

    return list(study_objs_dict.values())


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _first_text(parent: etree._Element, tag: str) -> Optional[str]:
    """Return the .text of the first matching child, or None."""
    children = parent.findall(tag)
    if not children:
        return None
    return children[0].text
