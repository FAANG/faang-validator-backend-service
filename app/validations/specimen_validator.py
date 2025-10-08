from typing import List, Dict, Any, Type, Optional, Tuple
from pydantic import BaseModel
from app.validations.base_validator import BaseValidator
from app.validations.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.specimen_ruleset import FAANGSpecimenFromOrganismSample


class SpecimenValidator(BaseValidator):

    def _initialize_validators(self):
        self.ontology_validator = OntologyValidator(cache_enabled=True)
        self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGSpecimenFromOrganismSample

    def get_sample_type_name(self) -> str:
        return "specimen_from_organism"

    def validate_specimen_sample(
        self,
        data: Dict[str, Any],
        validate_relationships: bool = True,
        validate_with_json_schema: bool = True
    ) -> Tuple[Optional[FAANGSpecimenFromOrganismSample], Dict[str, List[str]]]:

        model, errors = self.validate_single_record(data)
        return model, errors

    def validate_with_pydantic(
        self,
        specimens: List[Dict[str, Any]],
        validate_relationships: bool = True,
        all_samples: Dict[str, List[Dict]] = None,
        validate_ontology_text: bool = True,
    ) -> Dict[str, Any]:

        return self.validate_records(
            specimens,
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

        # Base validation results
        results = super().validate_records(sheet_records, validate_relationships=False, all_samples=all_samples)

        # relationship validation
        if validate_relationships and all_samples:
            relationship_errors = self.relationship_validator.validate_derived_from_relationships(all_samples)

            # relationship errors for specimens
            for specimen in results['valid_specimen_from_organisms']:
                sample_name = specimen['sample_name']
                if sample_name in relationship_errors:
                    specimen['relationship_errors'] = relationship_errors[sample_name]
                    results['summary']['relationship_errors'] += 1

            # relationship errors for invalid specimens
            for specimen in results['invalid_specimen_from_organisms']:
                sample_name = specimen['sample_name']
                if sample_name in relationship_errors:
                    if 'relationship_errors' not in specimen['errors']:
                        specimen['errors']['relationship_errors'] = []
                    specimen['errors']['relationship_errors'] = relationship_errors[sample_name]
                    results['summary']['relationship_errors'] += 1

        return results


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

        # Relationships - derived from
        biosample_data["relationships"] = [{
            "type": "derived from",
            "target": model.derived_from
        }]

        return biosample_data