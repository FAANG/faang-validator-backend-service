from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validation.sample.base_validator import BaseValidator
from app.validation.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.sample.cell_culture_ruleset import FAANGCellCultureSample
from app.validation.validation_utils import auto_export_remaining_fields


class CellCultureValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGCellCultureSample

    def get_sample_type_name(self) -> str:
        return "cell_culture"

    def export_to_biosample_format(self, model: FAANGCellCultureSample) -> Dict[str, Any]:

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

        # Material - should be cell culture
        biosample_data["characteristics"]["material"] = [{
            "text": model.material,
            "ontologyTerms": [convert_term_to_url(model.term_source_id)]
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

        # Culture type
        biosample_data["characteristics"]["culture type"] = [{
            "text": model.culture_type,
            "ontologyTerms": [convert_term_to_url(model.culture_type_term_source_id)]
        }]

        # Cell type
        biosample_data["characteristics"]["cell type"] = []
        for cell_type in model.cell_type:
            biosample_data["characteristics"]["cell type"].append({
                "text": cell_type.text,
                "ontologyTerms": [convert_term_to_url(cell_type.term)]
            })

        # Cell culture protocol
        biosample_data["characteristics"]["cell culture protocol"] = [{
            "text": model.cell_culture_protocol
        }]

        # Culture conditions
        biosample_data["characteristics"]["culture conditions"] = [{
            "text": model.culture_conditions
        }]

        # Number of passages
        biosample_data["characteristics"]["number of passages"] = [{
            "text": str(model.number_of_passages)
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
            'sample_name', 'material', 'term_source_id', 'culture_type', 'culture_type_term_source_id',
            'cell_type', 'cell_culture_protocol', 'culture_conditions', 'number_of_passages',
            'project', 'secondary_project', 'sample_description', 'availability', 'derived_from', 'same_as'
        }

        auto_export_remaining_fields(model, biosample_data, excluded_fields)

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