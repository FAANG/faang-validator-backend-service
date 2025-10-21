from typing import List, Dict, Any, Type
from pydantic import BaseModel
from app.validations.base_validator import BaseValidator
from app.validations.generic_validator_classes import OntologyValidator, BreedSpeciesValidator, RelationshipValidator
from app.rulesets_pydantics.organism_ruleset import FAANGOrganismSample


class OrganismValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGOrganismSample

    def get_sample_type_name(self) -> str:
        return "organism"

    def _get_relationship_errors(self, all_samples: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
        organisms = all_samples.get('organism', [])
        if not organisms:
            return {}

        raw_errors = self.relationship_validator.validate_organism_relationships(organisms)

        # return only records that have errors
        return {
            sample_name: result.errors
            for sample_name, result in raw_errors.items()
            if result.errors
        }

    def export_to_biosample_format(self, model: FAANGOrganismSample) -> Dict[str, Any]:

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

        biosample_data["characteristics"]["material"] = [{
            "text": model.material,
            "ontologyTerms": [convert_term_to_url(model.term_source_id)]
        }]

        biosample_data["characteristics"]["organism"] = [{
            "text": model.organism,
            "ontologyTerms": [convert_term_to_url(model.organism_term_source_id)]
        }]

        biosample_data["characteristics"]["sex"] = [{
            "text": model.sex,
            "ontologyTerms": [convert_term_to_url(model.sex_term_source_id)]
        }]

        if model.birth_date and model.birth_date.strip():
            biosample_data["characteristics"]["birth date"] = [{
                "text": model.birth_date,
                "unit": model.birth_date_unit or ""
            }]

        if model.breed and model.breed.strip():
            biosample_data["characteristics"]["breed"] = [{
                "text": model.breed,
                "ontologyTerms": [convert_term_to_url(model.breed_term_source_id)]
            }]

        if model.health_status:
            biosample_data["characteristics"]["health status"] = []
            for status in model.health_status:
                biosample_data["characteristics"]["health status"].append({
                    "text": status.text,
                    "ontologyTerms": [f"http://purl.obolibrary.org/obo/{status.term.replace(':', '_')}"]
                })

        if model.child_of:
            biosample_data["relationships"] = []
            for parent in model.child_of:
                if parent and parent.strip():
                    biosample_data["relationships"].append({
                        "type": "child of",
                        "target": parent
                    })

        return biosample_data