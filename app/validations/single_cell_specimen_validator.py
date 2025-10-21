from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validations.base_validator import BaseValidator
from app.validations.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.single_cell_specimen_ruleset import FAANGSingleCellSpecimenSample


class SingleCellSpecimenValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGSingleCellSpecimenSample

    def get_sample_type_name(self) -> str:
        return "single_cell_specimen"

    def export_to_biosample_format(self, model: FAANGSingleCellSpecimenSample) -> Dict[str, Any]:

        def convert_term_to_url(term_id: str) -> str:
            if not term_id or term_id in ["restricted access", "not applicable", "not collected", "not provided", ""]:
                return ""
            if '_' in term_id and ':' not in term_id:
                term_colon = term_id.replace('_', ':', 1)
            else:
                term_colon = term_id
            return f"http://purl.obolibrary.org/obo/{term_colon.replace(':', '_')}"

        biosample_data = {
            "characteristics": {}
        }

        # Material - should be single cell specimen
        biosample_data["characteristics"]["material"] = [{
            "text": model.material,
            "ontologyTerms": [convert_term_to_url(model.term_source_id)]
        }]

        # Tissue dissociation
        biosample_data["characteristics"]["tissue dissociation"] = [{
            "text": model.tissue_dissociation
        }]

        # Cell enrichment
        biosample_data["characteristics"]["cell enrichment"] = [{
            "text": model.cell_enrichment
        }]

        # Enrichment markers (optional)
        if model.enrichment_markers:
            biosample_data["characteristics"]["enrichment markers"] = [{
                "text": model.enrichment_markers
            }]

        # Cell type (array)
        biosample_data["characteristics"]["cell type"] = []
        for cell_type in model.cell_type:
            biosample_data["characteristics"]["cell type"].append({
                "text": cell_type.text,
                "ontologyTerms": [convert_term_to_url(cell_type.term)]
            })

        # Single cell isolation (optional)
        if model.single_cell_isolation:
            biosample_data["characteristics"]["single cell isolation"] = [{
                "text": model.single_cell_isolation
            }]

        # Single cell entity (optional)
        if model.single_cell_entity:
            biosample_data["characteristics"]["single cell entity"] = [{
                "text": model.single_cell_entity
            }]

        # Single cell quality (optional)
        if model.single_cell_quality:
            biosample_data["characteristics"]["single cell quality"] = [{
                "text": model.single_cell_quality
            }]

        # Cell number (optional)
        if model.cell_number is not None:
            biosample_data["characteristics"]["cell number"] = [{
                "text": str(model.cell_number),
                "unit": model.cell_number_unit or "cells"
            }]

        # Single cell isolation protocol
        biosample_data["characteristics"]["single cell isolation protocol"] = [{
            "text": model.single_cell_isolation_protocol
        }]

        # Relationships - derived from
        biosample_data["relationships"] = [{
            "type": "derived from",
            "target": model.derived_from[0]
        }]

        return biosample_data