from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validation.sample.base_validator import BaseValidator
from app.validation.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.sample.specimen_ruleset import FAANGSpecimenFromOrganismSample
from app.validation.validation_utils import auto_export_remaining_fields


class SpecimenValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGSpecimenFromOrganismSample

    def get_sample_type_name(self) -> str:
        return "specimen_from_organism"

    def export_to_biosample_format(self, model: FAANGSpecimenFromOrganismSample) -> Dict[str, Any]:

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

        # Material - should be specimen from organism
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

        # Specimen collection date
        biosample_data["characteristics"]["specimen collection date"] = [{
            "text": model.specimen_collection_date,
            "unit": model.specimen_collection_date_unit
        }]

        # Geographic location
        biosample_data["characteristics"]["geographic location"] = [{
            "text": model.geographic_location
        }]

        # Animal age at collection
        biosample_data["characteristics"]["animal age at collection"] = [{
            "text": str(model.animal_age_at_collection),
            "unit": model.animal_age_at_collection_unit
        }]

        # Developmental stage
        biosample_data["characteristics"]["developmental stage"] = [{
            "text": model.developmental_stage,
            "ontologyTerms": [convert_term_to_url(model.developmental_stage_term_source_id)]
        }]

        # Organism part
        biosample_data["characteristics"]["organism part"] = [{
            "text": model.organism_part,
            "ontologyTerms": [convert_term_to_url(model.organism_part_term_source_id)]
        }]

        # Specimen collection protocol
        biosample_data["characteristics"]["specimen collection protocol"] = [{
            "text": model.specimen_collection_protocol
        }]

        # Health status (optional)
        if model.health_status:
            biosample_data["characteristics"]["health status at collection"] = []
            for status in model.health_status:
                biosample_data["characteristics"]["health status at collection"].append({
                    "text": status.text,
                    "ontologyTerms": [convert_term_to_url(status.term)]
                })

        # Optional numeric fields
        if model.fasted_status:
            biosample_data["characteristics"]["fasted status"] = [{
                "text": model.fasted_status
            }]

        if model.number_of_pieces:
            biosample_data["characteristics"]["number of pieces"] = [{
                "text": str(model.number_of_pieces),
                "unit": model.number_of_pieces_unit
            }]

        if model.specimen_volume:
            biosample_data["characteristics"]["specimen volume"] = [{
                "text": str(model.specimen_volume),
                "unit": model.specimen_volume_unit
            }]

        if model.specimen_size:
            biosample_data["characteristics"]["specimen size"] = [{
                "text": str(model.specimen_size),
                "unit": model.specimen_size_unit
            }]

        if model.specimen_weight:
            biosample_data["characteristics"]["specimen weight"] = [{
                "text": str(model.specimen_weight),
                "unit": model.specimen_weight_unit
            }]

        if model.specimen_picture_url:
            biosample_data["characteristics"]["specimen picture url"] = [
                {"text": pic} for pic in model.specimen_picture_url
            ]

        if model.gestational_age_at_sample_collection:
            biosample_data["characteristics"]["gestational age at sample collection"] = [{
                "text": str(model.gestational_age_at_sample_collection),
                "unit": model.gestational_age_at_sample_collection_unit
            }]

        if model.average_incubation_temperature:
            biosample_data["characteristics"]["average incubation temperature"] = [{
                "text": str(model.average_incubation_temperature),
                "unit": model.average_incubation_temperature_unit
            }]

        if model.average_incubation_humidity:
            biosample_data["characteristics"]["average incubation humidity"] = [{
                "text": str(model.average_incubation_humidity),
                "unit": model.average_incubation_humidity_unit
            }]

        if model.embryonic_stage:
            biosample_data["characteristics"]["embryonic stage"] = [{
                "text": model.embryonic_stage,
                "unit": model.embryonic_stage_unit
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
            'sample_name', 'material', 'term_source_id', 'specimen_collection_date',
            'specimen_collection_date_unit', 'geographic_location', 'animal_age_at_collection',
            'animal_age_at_collection_unit', 'developmental_stage', 'developmental_stage_term_source_id',
            'organism_part', 'organism_part_term_source_id', 'specimen_collection_protocol',
            'health_status', 'fasted_status', 'number_of_pieces', 'number_of_pieces_unit',
            'specimen_volume', 'specimen_volume_unit', 'specimen_size', 'specimen_size_unit',
            'specimen_weight', 'specimen_weight_unit', 'specimen_picture_url',
            'gestational_age_at_sample_collection', 'gestational_age_at_sample_collection_unit',
            'average_incubation_temperature', 'average_incubation_temperature_unit',
            'average_incubation_humidity', 'average_incubation_humidity_unit',
            'embryonic_stage', 'embryonic_stage_unit', 'project', 'secondary_project',
            'sample_description', 'availability', 'derived_from', 'same_as'
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
            derived_from_values = model.derived_from
            if isinstance(derived_from_values, str):
                derived_from_values = [derived_from_values]

            for parent in derived_from_values:
                if parent and str(parent).strip():
                    relationships.append({
                        "type": "derived from",
                        "target": str(parent).strip()
                    })

        # Add relationships to biosample_data if any exist
        if relationships:
            biosample_data["relationships"] = relationships

        return biosample_data