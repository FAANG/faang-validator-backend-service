from typing import List, Dict, Any, Type
from pydantic import BaseModel
from app.validation.sample.base_validator import BaseValidator
from app.validation.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.sample.organism_ruleset import FAANGOrganismSample


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

        biosample_data: Dict[str, Any] = {"characteristics": {}}

        biosample_data["characteristics"]["material"] = [{
            "text": model.material,
            "ontologyTerms": [convert_term_to_url(model.term_source_id)]
        }]

        # BioSamples API expects organism and species as arrays of objects
        # Each object contains: text (required), ontologyTerms (optional), unit (optional)
        # The API schema validation requires a field with the same name as the characteristic key
        ontology_url = convert_term_to_url(model.organism_term_source_id)
        
        organism_entry = {
            "text": model.organism,
            "organism": model.organism  # Required by API schema validation
        }
        if ontology_url:
            organism_entry["ontologyTerms"] = [ontology_url]
        
        species_entry = {
            "text": model.organism,
            "species": model.organism  # Required by API schema validation
        }
        if ontology_url:
            species_entry["ontologyTerms"] = [ontology_url]
        
        biosample_data["characteristics"]["organism"] = [organism_entry]
        biosample_data["characteristics"]["species"] = [species_entry]

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
            hs_list = []
            for status in model.health_status:
                hs_list.append({
                    "text": status.text,
                    "ontologyTerms": [f"http://purl.obolibrary.org/obo/{status.term.replace(':', '_')}"]
                })
            if hs_list:
                biosample_data["characteristics"]["health status"] = hs_list

        if model.child_of:
            rels = []
            for parent in model.child_of:
                if parent and parent.strip():
                    rels.append({
                        "type": "child of",
                        "target": parent
                    })
            if rels:
                biosample_data["relationships"] = rels

        return biosample_data
