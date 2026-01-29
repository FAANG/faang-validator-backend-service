from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validation.sample.base_validator import BaseValidator
from app.validation.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.sample.pool_of_specimens_ruleset import FAANGPoolOfSpecimensSample


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
            'sample_name', 'material', 'term_source_id', 'pool_creation_date', 'pool_creation_date_unit',
            'pool_creation_protocol', 'specimen_volume', 'specimen_volume_unit', 'specimen_size',
            'specimen_size_unit', 'specimen_weight', 'specimen_weight_unit', 'specimen_picture_url',
            'project', 'secondary_project', 'sample_description', 'availability', 'derived_from', 'same_as'
        }

        for field_name, field_value in model.model_dump().items():
            if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
                continue
            if field_name in excluded_fields:
                continue
            if field_name.endswith('_term_source_id') or field_name.endswith('_unit'):
                continue
            if field_name in {'child_of', 'derived_from', 'same_as'}:
                continue

            char_name = field_name.replace('_', ' ')
            if char_name in biosample_data["characteristics"]:
                continue

            if isinstance(field_value, list):
                if all(isinstance(item, str) for item in field_value):
                    biosample_data["characteristics"][char_name] = [
                        {"text": item} for item in field_value if item and item.strip()
                    ]
                continue

            biosample_data["characteristics"][char_name] = [{"text": str(field_value)}]

        # Build relationships list
        relationships = []

        # Same as relationship
        if hasattr(model, 'same_as') and model.same_as and model.same_as.strip():
            relationships.append({
                "type": "same as",
                "target": model.same_as
            })

        # Derived from relationships (multiple specimens)
        if hasattr(model, 'derived_from') and model.derived_from:
            for specimen in model.derived_from:
                relationships.append({
                    "type": "derived from",
                    "target": specimen
                })

        # Add relationships to biosample_data if any exist
        if relationships:
            biosample_data["relationships"] = relationships

        return biosample_data