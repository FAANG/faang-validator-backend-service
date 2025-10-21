from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validations.base_validator import BaseValidator
from app.validations.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.pool_of_specimens_ruleset import FAANGPoolOfSpecimensSample


class PoolOfSpecimensValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGPoolOfSpecimensSample

    def get_sample_type_name(self) -> str:
        return "pool_of_specimens"

    def export_to_biosample_format(self, model: FAANGPoolOfSpecimensSample) -> Dict[str, Any]:

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

        # Material - should be pool of specimens
        biosample_data["characteristics"]["material"] = [{
            "text": model.material,
            "ontologyTerms": [convert_term_to_url(model.term_source_id)]
        }]

        # Pool creation date
        biosample_data["characteristics"]["pool creation date"] = [{
            "text": model.pool_creation_date,
            "unit": model.pool_creation_date_unit
        }]

        # Pool creation protocol
        biosample_data["characteristics"]["pool creation protocol"] = [{
            "text": model.pool_creation_protocol
        }]

        # Optional fields
        if model.specimen_volume is not None:
            biosample_data["characteristics"]["specimen volume"] = [{
                "text": str(model.specimen_volume),
                "unit": model.specimen_volume_unit or ""
            }]

        if model.specimen_size is not None:
            biosample_data["characteristics"]["specimen size"] = [{
                "text": str(model.specimen_size),
                "unit": model.specimen_size_unit or ""
            }]

        if model.specimen_weight is not None:
            biosample_data["characteristics"]["specimen weight"] = [{
                "text": str(model.specimen_weight),
                "unit": model.specimen_weight_unit or ""
            }]

        if model.specimen_picture_url:
            biosample_data["characteristics"]["specimen picture url"] = [
                {"text": pic} for pic in model.specimen_picture_url
            ]

        # Relationships - derived from (multiple specimens)
        biosample_data["relationships"] = []
        for specimen in model.derived_from:
            biosample_data["relationships"].append({
                "type": "derived from",
                "target": specimen
            })

        return biosample_data