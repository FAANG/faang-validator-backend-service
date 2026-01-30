from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validation.sample.base_validator import BaseValidator
from app.validation.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.sample.organoid_ruleset import FAANGOrganoidSample
from app.validation.validation_utils import auto_export_remaining_fields


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

        biosample_data["characteristics"]["sample name"] = [{
            "text": model.sample_name
        }]

        if hasattr(model, 'sample_description') and model.sample_description:
            biosample_data["characteristics"]["sample description"] = [{
                "text": model.sample_description
            }]

        if hasattr(model, 'availability') and model.availability:
            biosample_data["characteristics"]["availability"] = [{
                "text": model.availability
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

        if hasattr(model, 'project') and model.project:
            biosample_data["characteristics"]["project"] = [{
                "text": model.project
            }]

        if hasattr(model, 'secondary_project') and model.secondary_project:
            if isinstance(model.secondary_project, list):
                secondary_values = [val for val in model.secondary_project if val and val.strip()]
                if secondary_values:
                    biosample_data["characteristics"]["secondary project"] = [
                        {"text": val} for val in secondary_values
                    ]
            elif model.secondary_project.strip():
                biosample_data["characteristics"]["secondary project"] = [{
                    "text": model.secondary_project
                }]

        # Auto-export any remaining fields not explicitly handled
        excluded_fields = {
            'sample_name', 'material', 'organ_model', 'organ_model_term_source_id',
            'organ_part_model', 'organ_part_model_term_source_id', 'freezing_method',
            'freezing_date', 'freezing_date_unit', 'organoid_passage', 'organoid_passage_unit',
            'growth_environment', 'type_of_organoid_culture', 'organoid_morphology',
            'number_of_frozen_cells', 'number_of_frozen_cells_unit', 'project',
            'secondary_project', 'sample_description', 'availability', 'derived_from', 'same_as'
        }

        auto_export_remaining_fields(model, biosample_data, excluded_fields)

        # Build relationships list
        relationships = []

        # Same as relationship
        if hasattr(model, 'same_as') and model.same_as and model.same_as.strip():
            relationships.append({
                "type": "same as",
                "target": model.same_as
            })

        # Derived from relationship
        if hasattr(model, 'derived_from') and model.derived_from:
            relationships.append({
                "type": "derived from",
                "target": model.derived_from[0]
            })

        # Add relationships to biosample_data if any exist
        if relationships:
            biosample_data["relationships"] = relationships

        return biosample_data