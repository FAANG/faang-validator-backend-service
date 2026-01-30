from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validation.sample.base_validator import BaseValidator
from app.validation.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.sample.teleostei_embryo_ruleset import FAANGTeleosteiEmbryoSample


class TeleosteiEmbryoValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGTeleosteiEmbryoSample

    def get_sample_type_name(self) -> str:
        return "teleostei_embryo"

    def export_to_biosample_format(self, model: FAANGTeleosteiEmbryoSample) -> Dict[str, Any]:

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

        # Material
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

        # Teleostei-specific fields
        biosample_data["characteristics"]["origin"] = [{
            "text": model.origin
        }]

        biosample_data["characteristics"]["reproductive strategy"] = [{
            "text": model.reproductive_strategy
        }]

        biosample_data["characteristics"]["hatching"] = [{
            "text": model.hatching
        }]

        biosample_data["characteristics"]["time post fertilisation"] = [{
            "text": str(model.time_post_fertilisation),
            "unit": model.time_post_fertilisation_unit
        }]

        biosample_data["characteristics"]["pre-hatching water temperature average"] = [{
            "text": str(model.pre_hatching_water_temperature_average),
            "unit": model.pre_hatching_water_temperature_average_unit
        }]

        biosample_data["characteristics"]["post-hatching water temperature average"] = [{
            "text": str(model.post_hatching_water_temperature_average),
            "unit": model.post_hatching_water_temperature_average_unit
        }]

        biosample_data["characteristics"]["degree days"] = [{
            "text": str(model.degree_days),
            "unit": model.degree_days_unit
        }]

        biosample_data["characteristics"]["growth media"] = [{
            "text": model.growth_media
        }]

        biosample_data["characteristics"]["medium replacement frequency"] = [{
            "text": str(model.medium_replacement_frequency),
            "unit": model.medium_replacement_frequency_unit
        }]

        biosample_data["characteristics"]["percentage total somite number"] = [{
            "text": str(model.percentage_total_somite_number),
            "unit": model.percentage_total_somite_number_unit
        }]

        biosample_data["characteristics"]["average water salinity"] = [{
            "text": str(model.average_water_salinity),
            "unit": model.average_water_salinity_unit
        }]

        biosample_data["characteristics"]["photoperiod"] = [{
            "text": model.photoperiod
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


        # Optional field
        if model.generations_from_wild is not None:
            biosample_data["characteristics"]["generations from wild"] = [{
                "text": str(model.generations_from_wild),
                "unit": model.generations_from_wild_unit or ""
            }]

        # Auto-export any remaining fields not explicitly handled
        excluded_fields = {
            'sample_name', 'material', 'term_source_id', 'specimen_collection_date',
            'specimen_collection_date_unit',
            'geographic_location', 'animal_age_at_collection', 'animal_age_at_collection_unit',
            'developmental_stage', 'developmental_stage_term_source_id', 'organism_part',
            'organism_part_term_source_id',
            'specimen_collection_protocol', 'health_status', 'origin', 'reproductive_strategy', 'hatching',
            'time_post_fertilisation', 'time_post_fertilisation_unit', 'pre_hatching_water_temperature_average',
            'pre_hatching_water_temperature_average_unit', 'post_hatching_water_temperature_average',
            'post_hatching_water_temperature_average_unit', 'degree_days', 'degree_days_unit', 'growth_media',
            'medium_replacement_frequency', 'medium_replacement_frequency_unit', 'percentage_total_somite_number',
            'percentage_total_somite_number_unit', 'average_water_salinity', 'average_water_salinity_unit',
            'photoperiod', 'generations_from_wild', 'generations_from_wild_unit', 'project', 'secondary_project',
            'sample_description', 'availability', 'derived_from', 'same_as'
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