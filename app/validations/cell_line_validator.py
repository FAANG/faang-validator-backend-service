from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validations.base_validator import BaseValidator
from app.validations.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.cell_line_ruleset import FAANGCellLineSample


class CellLineValidator(BaseValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
        if self.relationship_validator is None:
            self.relationship_validator = RelationshipValidator()

    def get_model_class(self) -> Type[BaseModel]:
        return FAANGCellLineSample

    def get_sample_type_name(self) -> str:
        return "cell_line"

    def export_to_biosample_format(self, model: FAANGCellLineSample) -> Dict[str, Any]:

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

        # Material - should be cell line
        biosample_data["characteristics"]["material"] = [{
            "text": model.material,
            "ontologyTerms": [convert_term_to_url(model.term_source_id)]
        }]

        # Organism
        biosample_data["characteristics"]["organism"] = [{
            "text": model.organism,
            "ontologyTerms": [convert_term_to_url(model.organism_term_source_id)]
        }]

        # Sex
        biosample_data["characteristics"]["sex"] = [{
            "text": model.sex,
            "ontologyTerms": [convert_term_to_url(model.sex_term_source_id)]
        }]

        # Cell line
        biosample_data["characteristics"]["cell line"] = [{
            "text": model.cell_line
        }]

        # Biomaterial provider
        biosample_data["characteristics"]["biomaterial provider"] = [{
            "text": model.biomaterial_provider
        }]

        # Recommended fields
        if model.catalogue_number:
            biosample_data["characteristics"]["catalogue number"] = [{
                "text": model.catalogue_number
            }]

        if model.number_of_passages is not None:
            biosample_data["characteristics"]["number of passages"] = [{
                "text": str(model.number_of_passages)
            }]

        if model.date_established and model.date_established not in ["not applicable", "not collected", "not provided", "restricted access"]:
            biosample_data["characteristics"]["date established"] = [{
                "text": model.date_established,
                "unit": model.date_established_unit or ""
            }]

        if model.publication:
            biosample_data["characteristics"]["publication"] = [{
                "text": model.publication
            }]

        # Optional fields
        if model.breed:
            biosample_data["characteristics"]["breed"] = [{
                "text": model.breed,
                "ontologyTerms": [convert_term_to_url(model.breed_term_source_id)]
            }]

        if model.cell_type:
            biosample_data["characteristics"]["cell type"] = []
            for cell_type in model.cell_type:
                biosample_data["characteristics"]["cell type"].append({
                    "text": cell_type.text,
                    "ontologyTerms": [convert_term_to_url(cell_type.term)]
                })

        if model.culture_conditions:
            biosample_data["characteristics"]["culture conditions"] = [{
                "text": model.culture_conditions
            }]

        if model.culture_protocol:
            biosample_data["characteristics"]["culture protocol"] = [{
                "text": model.culture_protocol
            }]

        if model.disease:
            biosample_data["characteristics"]["disease"] = [{
                "text": model.disease,
                "ontologyTerms": [convert_term_to_url(model.disease_term_source_id)]
            }]

        if model.karyotype:
            biosample_data["characteristics"]["karyotype"] = [{
                "text": model.karyotype
            }]

        # Relationships - derived from (optional)
        if model.derived_from:
            biosample_data["relationships"] = [{
                "type": "derived from",
                "target": model.derived_from[0]
            }]

        return biosample_data