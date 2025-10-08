from typing import List, Dict, Any, Type, Optional, Tuple
from pydantic import BaseModel
from app.validations.base_validator import BaseValidator
from app.validations.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.organoid_ruleset import FAANGOrganoidSample


class OrganoidValidator(BaseValidator):

    def _initialize_validators(self):
        self.ontology_validator = OntologyValidator(cache_enabled=True)
        self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGOrganoidSample

    def get_sample_type_name(self) -> str:
        return "organoid"

    def validate_organoid_sample(
        self,
        data: Dict[str, Any],
        validate_relationships: bool = True,
    ) -> Tuple[Optional[FAANGOrganoidSample], Dict[str, List[str]]]:

        model, errors = self.validate_single_record(data, validate_relationships)
        return model, errors

    def validate_with_pydantic(
        self,
        organoids: List[Dict[str, Any]],
        validate_relationships: bool = True,
        all_samples: Dict[str, List[Dict]] = None,
        validate_ontology_text: bool = True,
    ) -> Dict[str, Any]:

        return self.validate_records(
            organoids,
            validate_relationships=validate_relationships,
            all_samples=all_samples,
            validate_ontology_text=validate_ontology_text
        )

    def validate_records(
        self,
        organoids: List[Dict[str, Any]],
        validate_relationships: bool = True,
        all_samples: Dict[str, List[Dict]] = None,
        validate_ontology_text: bool = True,
        **kwargs
    ) -> Dict[str, Any]:

        # base validation results
        results = super().validate_records(organoids, validate_relationships=False, all_samples=all_samples)

        # relationship validation using the generic method
        if validate_relationships and all_samples:
            relationship_errors = self.relationship_validator.validate_derived_from_relationships(all_samples)

            # relationship errors for valid organoids
            for org in results['valid_organoids']:
                sample_name = org['sample_name']
                if sample_name in relationship_errors:
                    org['relationship_errors'] = relationship_errors[sample_name]
                    results['summary']['relationship_errors'] += 1

            # relationship errors for invalid organoids
            for org in results['invalid_organoids']:
                sample_name = org['sample_name']
                if sample_name in relationship_errors:
                    if 'relationship_errors' not in org['errors']:
                        org['errors']['relationship_errors'] = []
                    org['errors']['relationship_errors'] = relationship_errors[sample_name]
                    results['summary']['relationship_errors'] += 1

        return results


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
            "target": model.derived_from
        }]

        return biosample_data