from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validation.sample.base_validator import BaseValidator
from app.validation.sample.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.sample.cell_specimen_ruleset import FAANGCellSpecimenSample


class CellSpecimenValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGCellSpecimenSample

    def get_sample_type_name(self) -> str:
        return "cell_specimen"

    def export_to_biosample_format(self, model: FAANGCellSpecimenSample) -> Dict[str, Any]:

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

        # Material - should be cell specimen
        biosample_data["characteristics"]["material"] = [{
            "text": model.material,
            "ontologyTerms": [convert_term_to_url(model.term_source_id)]
        }]

        # Markers (optional)
        if model.markers:
            biosample_data["characteristics"]["markers"] = [{
                "text": model.markers
            }]

        # Cell type (array)
        biosample_data["characteristics"]["cell type"] = []
        for cell_type in model.cell_type:
            biosample_data["characteristics"]["cell type"].append({
                "text": cell_type.text,
                "ontologyTerms": [convert_term_to_url(cell_type.term)]
            })

        # Purification protocol
        biosample_data["characteristics"]["purification protocol"] = [{
            "text": model.purification_protocol
        }]

        # Relationships - derived from
        biosample_data["relationships"] = [{
            "type": "derived from",
            "target": model.derived_from[0]
        }]

        return biosample_data