from typing import Dict, Any, Type
from pydantic import BaseModel
from app.validations.base_validator import BaseValidator
from app.validations.generic_validator_classes import OntologyValidator, RelationshipValidator
from app.rulesets_pydantics.specimen_ruleset import FAANGSpecimenFromOrganismSample


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

    def export_to_biosample_format(self, model: Any) -> Dict[str, Any]:
        def convert_term_to_url(term_id: str) -> str:
            if not term_id or term_id in ["restricted access", "not applicable", "not collected", "not provided", ""]:
                return ""
            if "_" in term_id and ":" not in term_id:
                term_colon = term_id.replace("_", ":", 1)
            else:
                term_colon = term_id
            return f"http://purl.obolibrary.org/obo/{term_colon.replace(':', '_')}"

        def get(obj: Any, field: str, default=None):
            if hasattr(obj, field):
                return getattr(obj, field)
            if isinstance(obj, dict):
                return obj.get(field, default)
            return default

        biosample_data: Dict[str, Any] = {"characteristics": {}}

        material = get(model, "material") or "specimen from organism"
        term_source_id = get(model, "term_source_id") or "OBI_0001479"
        biosample_data["characteristics"]["material"] = [{
            "text": material,
            "ontologyTerms": [convert_term_to_url(term_source_id)]
        }]

        organism_name = get(model, "organism") or get(model, "species")
        organism_term_id = (
                get(model, "organism_term_source_id")
                or get(model, "species_term_source_id")
                or get(model, "organism_term_id")
        )
        # Organism and species are required by BioSamples API
        # If not in model, they should be obtained from parent organism sample
        # For now, we'll add them if available, but they should always be present
        if organism_name:
            organism_entry = {
                "text": organism_name,
                "organism": organism_name  # Required by API schema validation
            }
            url = convert_term_to_url(organism_term_id or "")
            if url:
                organism_entry["ontologyTerms"] = [url]
            
            species_entry = {
                "text": organism_name,
                "species": organism_name  # Required by API schema validation
            }
            if url:
                species_entry["ontologyTerms"] = [url]
            
            biosample_data["characteristics"]["organism"] = [organism_entry]
            biosample_data["characteristics"]["species"] = [species_entry]

        specimen_collection_date = get(model, "specimen_collection_date")
        if specimen_collection_date:
            biosample_data["characteristics"]["specimen collection date"] = [{
                "text": specimen_collection_date,
                "unit": get(model, "specimen_collection_date_unit")
            }]

        geographic_location = get(model, "geographic_location")
        if geographic_location:
            biosample_data["characteristics"]["geographic location (country and/or sea)"] = [{
                "text": geographic_location
            }]

        animal_age_at_collection = get(model, "animal_age_at_collection")
        if animal_age_at_collection is not None:
            biosample_data["characteristics"]["animal age at collection"] = [{
                "text": str(animal_age_at_collection),
                "unit": get(model, "animal_age_at_collection_unit")
            }]

        developmental_stage = get(model, "developmental_stage")
        if developmental_stage:
            biosample_data["characteristics"]["developmental stage"] = [{
                "text": developmental_stage,
                "ontologyTerms": [convert_term_to_url(get(model, "developmental_stage_term_source_id"))]
            }]

        organism_part = get(model, "organism_part")
        if organism_part:
            biosample_data["characteristics"]["organism part"] = [{
                "text": organism_part,
                "ontologyTerms": [convert_term_to_url(get(model, "organism_part_term_source_id"))]
            }]

        specimen_collection_protocol = get(model, "specimen_collection_protocol")
        if specimen_collection_protocol:
            biosample_data["characteristics"]["specimen collection protocol"] = [{
                "text": specimen_collection_protocol
            }]

        health_status_list = get(model, "health_status") or []
        if health_status_list:
            hs_chars = []
            for status in health_status_list:
                text = get(status, "text")
                term = get(status, "term")
                if not (text or term):
                    continue
                entry = {"text": text or term}
                if term:
                    url = convert_term_to_url(term)
                    if url:
                        entry["ontologyTerms"] = [url]
                hs_chars.append(entry)
            if hs_chars:
                biosample_data["characteristics"]["health status at collection"] = hs_chars

        fasted_status = get(model, "fasted_status")
        if fasted_status:
            biosample_data["characteristics"]["fasted status"] = [{
                "text": fasted_status
            }]

        number_of_pieces = get(model, "number_of_pieces")
        if number_of_pieces is not None:
            biosample_data["characteristics"]["number of pieces"] = [{
                "text": str(number_of_pieces),
                "unit": get(model, "number_of_pieces_unit")
            }]

        specimen_volume = get(model, "specimen_volume")
        if specimen_volume is not None:
            biosample_data["characteristics"]["specimen volume"] = [{
                "text": str(specimen_volume),
                "unit": get(model, "specimen_volume_unit")
            }]

        specimen_size = get(model, "specimen_size")
        if specimen_size is not None:
            biosample_data["characteristics"]["specimen size"] = [{
                "text": str(specimen_size),
                "unit": get(model, "specimen_size_unit")
            }]

        specimen_weight = get(model, "specimen_weight")
        if specimen_weight is not None:
            biosample_data["characteristics"]["specimen weight"] = [{
                "text": str(specimen_weight),
                "unit": get(model, "specimen_weight_unit")
            }]

        specimen_picture_url = get(model, "specimen_picture_url") or []
        if specimen_picture_url:
            biosample_data["characteristics"]["specimen picture url"] = [
                {"text": pic} for pic in specimen_picture_url
            ]

        gest_age = get(model, "gestational_age_at_sample_collection")
        if gest_age is not None:
            biosample_data["characteristics"]["gestational age at sample collection"] = [{
                "text": str(gest_age),
                "unit": get(model, "gestational_age_at_sample_collection_unit")
            }]

        avg_temp = get(model, "average_incubation_temperature")
        if avg_temp is not None:
            biosample_data["characteristics"]["average incubation temperature"] = [{
                "text": str(avg_temp),
                "unit": get(model, "average_incubation_temperature_unit")
            }]

        avg_hum = get(model, "average_incubation_humidity")
        if avg_hum is not None:
            biosample_data["characteristics"]["average incubation humidity"] = [{
                "text": str(avg_hum),
                "unit": get(model, "average_incubation_humidity_unit")
            }]

        embryonic_stage = get(model, "embryonic_stage")
        if embryonic_stage:
            biosample_data["characteristics"]["embryonic stage"] = [{
                "text": embryonic_stage,
                "unit": get(model, "embryonic_stage_unit")
            }]

        derived_from = get(model, "derived_from") or []
        target = None
        if derived_from:
            first = derived_from[0]
            if isinstance(first, dict):
                target = first.get("value") or first.get("text")
            else:
                target = str(first)

        if target:
            biosample_data["relationships"] = [{
                "type": "derived from",
                "target": target
            }]

        return biosample_data
