from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validation.sample.base_validator import BaseValidator
from app.validation.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.sample.organoid_ruleset import FAANGOrganoidSample


class OrganoidValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGOrganoidSample

    def get_sample_type_name(self) -> str:
        return "organoid"

    def export_to_biosample_format(self, model: FAANGOrganoidSample) -> Dict[str, Any]:

        def convert_term_to_url(term_id: str) -> str:
            if not term_id or term_id in ["restricted access", ""]:
                return ""
            if '_' in term_id and ':' not in term_id:
                term_colon = term_id.replace('_', ':', 1)
            else:
                term_colon = term_id
            return f"http://purl.obolibrary.org/obo/{term_colon.replace(':', '_')}"

        biosample_data = {
            "characteristics": {}
        }

        # Material - should be organoid
        biosample_data["characteristics"]["material"] = [{
            "text": "organoid",
            "ontologyTerms": [convert_term_to_url("NCIT:C172259")]
        }]

        # Organ model
        biosample_data["characteristics"]["organ model"] = [{
            "text": model.organ_model,
            "ontologyTerms": [convert_term_to_url(model.organ_model_term_source_id)]
        }]

        # Organ part model (optional)
        if model.organ_part_model:
            biosample_data["characteristics"]["organ part model"] = [{
                "text": model.organ_part_model,
                "ontologyTerms": [convert_term_to_url(model.organ_part_model_term_source_id)]
            }]

        # Freezing method
        biosample_data["characteristics"]["freezing method"] = [{
            "text": model.freezing_method
        }]

        # Freezing date (if provided and not fresh)
        if model.freezing_date and model.freezing_date != "restricted access":
            biosample_data["characteristics"]["freezing date"] = [{
                "text": model.freezing_date,
                "unit": model.freezing_date_unit or ""
            }]

        # Organoid passage
        biosample_data["characteristics"]["organoid passage"] = [{
            "text": str(model.organoid_passage),
            "unit": model.organoid_passage_unit
        }]

        # Growth environment
        biosample_data["characteristics"]["growth environment"] = [{
            "text": model.growth_environment
        }]

        # Type of organoid culture
        biosample_data["characteristics"]["type of organoid culture"] = [{
            "text": model.type_of_organoid_culture
        }]

        # Organoid morphology (optional)
        if model.organoid_morphology:
            biosample_data["characteristics"]["organoid morphology"] = [{
                "text": model.organoid_morphology
            }]

        # Number of frozen cells (optional)
        if model.number_of_frozen_cells is not None:
            biosample_data["characteristics"]["number of frozen cells"] = [{
                "text": str(model.number_of_frozen_cells),
                "unit": model.number_of_frozen_cells_unit or "organoids"
            }]

        # Relationships - derived from
        biosample_data["relationships"] = [{
            "type": "derived from",
            "target": model.derived_from[0]
        }]

        return biosample_data