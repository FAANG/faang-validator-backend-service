from typing import List, Dict, Any, Type, Optional, Tuple
from pydantic import BaseModel
from app.validations.base_validator import BaseValidator
from app.validations.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.teleostei_post_hatching_ruleset import FAANGTeleosteiPostHatchingSample


class TeleosteiPostHatchingValidator(BaseValidator):

    def _initialize_validators(self):
        self.ontology_validator = OntologyValidator(cache_enabled=True)
        self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGTeleosteiPostHatchingSample

    def get_sample_type_name(self) -> str:
        return "teleostei_post_hatching"

    def validate_teleostei_post_hatching_sample(
        self,
        data: Dict[str, Any],
        validate_relationships: bool = True,
    ) -> Tuple[Optional[FAANGTeleosteiPostHatchingSample], Dict[str, List[str]]]:

        model, errors = self.validate_single_record(data)
        return model, errors

    def validate_with_pydantic(
        self,
        teleostei_post_hatchings: List[Dict[str, Any]],
        validate_relationships: bool = True,
        all_samples: Dict[str, List[Dict]] = None,
        validate_ontology_text: bool = True,
    ) -> Dict[str, Any]:

        return self.validate_records(
            teleostei_post_hatchings,
            validate_relationships=validate_relationships,
            all_samples=all_samples,
            validate_ontology_text=validate_ontology_text
        )

    def validate_records(
        self,
        sheet_records: List[Dict[str, Any]],
        validate_relationships: bool = True,
        all_samples: Dict[str, List[Dict]] = None,
        validate_ontology_text: bool = True,
        **kwargs
    ) -> Dict[str, Any]:

        # base validation results
        results = super().validate_records(sheet_records, validate_relationships=False, all_samples=all_samples)

        # relationship validation
        if validate_relationships and all_samples:
            relationship_errors = self.relationship_validator.validate_derived_from_relationships(all_samples)

            # relationship errors for valid post-hatching samples
            for sample in results['valid_teleostei_post_hatchings']:
                sample_name = sample['sample_name']
                if sample_name in relationship_errors:
                    sample['relationship_errors'] = relationship_errors[sample_name]
                    results['summary']['relationship_errors'] += 1

            # relationship errors for invalid post-hatching samples
            for sample in results['invalid_teleostei_post_hatchings']:
                sample_name = sample['sample_name']
                if sample_name in relationship_errors:
                    if 'relationship_errors' not in sample['errors']:
                        sample['errors']['relationship_errors'] = []
                    sample['errors']['relationship_errors'] = relationship_errors[sample_name]
                    results['summary']['relationship_errors'] += 1

        return results


    def export_to_biosample_format(self, model: FAANGTeleosteiPostHatchingSample) -> Dict[str, Any]:

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

        # Teleostei post-hatching specific fields
        biosample_data["characteristics"]["origin"] = [{
            "text": model.origin
        }]

        biosample_data["characteristics"]["reproductive strategy"] = [{
            "text": model.reproductive_strategy
        }]

        biosample_data["characteristics"]["gonad type"] = [{
            "text": model.gonad_type
        }]

        biosample_data["characteristics"]["hatching"] = [{
            "text": model.hatching
        }]

        biosample_data["characteristics"]["maturity state"] = [{
            "text": model.maturity_state,
            "ontologyTerms": [convert_term_to_url(model.maturity_state_term_source_id)]
        }]

        biosample_data["characteristics"]["time post fertilisation"] = [{
            "text": str(model.time_post_fertilisation),
            "unit": model.time_post_fertilisation_unit
        }]

        biosample_data["characteristics"]["post-hatching animal density"] = [{
            "text": str(model.post_hatching_animal_density),
            "unit": model.post_hatching_animal_density_unit
        }]

        biosample_data["characteristics"]["food restriction"] = [{
            "text": str(model.food_restriction),
            "unit": model.food_restriction_unit
        }]

        biosample_data["characteristics"]["post-hatching water temperature average"] = [{
            "text": str(model.post_hatching_water_temperature_average),
            "unit": model.post_hatching_water_temperature_average_unit
        }]

        biosample_data["characteristics"]["average water salinity"] = [{
            "text": str(model.average_water_salinity),
            "unit": model.average_water_salinity_unit
        }]

        biosample_data["characteristics"]["photoperiod"] = [{
            "text": model.photoperiod
        }]

        biosample_data["characteristics"]["sampling weight"] = [{
            "text": str(model.sampling_weight),
            "unit": model.sampling_weight_unit
        }]

        biosample_data["characteristics"]["method of euthanasia"] = [{
            "text": model.method_of_euthanasia
        }]

        # Optional/Recommended fields
        if model.generations_from_wild is not None:
            biosample_data["characteristics"]["generations from wild"] = [{
                "text": str(model.generations_from_wild),
                "unit": model.generations_from_wild_unit or ""
            }]

        if model.diet:
            biosample_data["characteristics"]["diet"] = [{
                "text": model.diet
            }]

        if model.experimental_strain_id:
            biosample_data["characteristics"]["experimental strain ID"] = [{
                "text": model.experimental_strain_id
            }]

        if model.genetic_background:
            biosample_data["characteristics"]["genetic background"] = [{
                "text": model.genetic_background
            }]

        if model.water_rearing_system:
            biosample_data["characteristics"]["water rearing system"] = [{
                "text": model.water_rearing_system
            }]

        if model.standard_length is not None:
            biosample_data["characteristics"]["standard length"] = [{
                "text": str(model.standard_length),
                "unit": model.standard_length_unit or ""
            }]

        if model.total_length is not None:
            biosample_data["characteristics"]["total length"] = [{
                "text": str(model.total_length),
                "unit": model.total_length_unit or ""
            }]

        if model.fork_length is not None:
            biosample_data["characteristics"]["fork length"] = [{
                "text": str(model.fork_length),
                "unit": model.fork_length_unit or ""
            }]

        if model.average_water_oxygen is not None:
            biosample_data["characteristics"]["average water oxygen"] = [{
                "text": str(model.average_water_oxygen),
                "unit": model.average_water_oxygen_unit or ""
            }]

        if model.sampling_day_start_time:
            biosample_data["characteristics"]["sampling day start time"] = [{
                "text": model.sampling_day_start_time
            }]

        if model.sampling_day_end_time:
            biosample_data["characteristics"]["sampling day end time"] = [{
                "text": model.sampling_day_end_time
            }]

        if model.anaesthetic_or_sedative_name:
            biosample_data["characteristics"]["anaesthetic or sedative name"] = [{
                "text": model.anaesthetic_or_sedative_name
            }]

        # Relationships - derived from
        biosample_data["relationships"] = [{
            "type": "derived from",
            "target": model.derived_from
        }]

        return biosample_data