from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
import requests

from app.validations.constants import SPECIES_BREED_LINKS, ALLOWED_RELATIONSHIPS, ELIXIR_VALIDATOR_URL

# import context variable from base_validator
try:
    from base_validator import ontology_warnings_context
except ImportError:
    from contextvars import ContextVar

    ontology_warnings_context: ContextVar[List[str]] = ContextVar('ontology_warnings', default=[])


class ValidationResult(BaseModel):
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    field_path: str
    value: Any = None

# for elixir validation - might need to be removed
def validate_term_against_classes(term_id: str, ontology_name: str,
                                  allowed_classes: List[str]) -> List[str]:
    errors = []

    # schema for Elixir validator
    schema = {
        "type": "string",
        "graph_restriction": {
            "ontologies": [f"obo:{ontology_name.lower()}"],
            "classes": allowed_classes,
            "relations": ["rdfs:subClassOf"],
            "direct": False,
            "include_self": True
        }
    }

    json_to_send = {
        'schema': schema,
        'object': term_id
    }

    try:
        response = requests.post(ELIXIR_VALIDATOR_URL, json=json_to_send, timeout=10)
        response.raise_for_status()
        validation_results = response.json()

        # validation errors
        for item in validation_results:
            for error in item.get('errors', []):
                if error != 'should match exactly one schema in oneOf':
                    errors.append(error)

    except requests.exceptions.RequestException as e:
        errors.append(f"Failed to connect to Elixir validator: {str(e)}")
    except Exception as e:
        errors.append(f"Error during validation: {str(e)}")

    return errors

class OntologyValidator:
    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, Any] = {}

    def validate_ontology_term(self, term: str, ontology_name: str,
                               allowed_classes: List[str],
                               text: str = None,
                               field_name: str = None) -> ValidationResult:

        result = ValidationResult(field_path=f"{ontology_name}:{term}")

        if term == "restricted access":
            return result

        # check OLS for term validity
        ols_data = self.fetch_from_ols(term)
        if not ols_data:
            result.errors.append(f"Term {term} not found in OLS")
            return result

        # text-term consistency check
        if text:
            term_with_colon = term.replace('_', ':', 1) if '_' in term and ':' not in term else term
            actual_ontology = term_with_colon.split(':')[0] if ':' in term_with_colon else ontology_name

            ols_labels = []
            for doc in ols_data:
                doc_ontology = doc.get('ontology_name', '').upper()
                if doc_ontology == actual_ontology.upper():
                    ols_labels.append(doc.get('label', '').lower())

            # if no labels found with specific ontology, get all labels
            if not ols_labels:
                ols_labels = [doc.get('label', '').lower() for doc in ols_data]

            # check if text matches any label
            if text.lower() not in ols_labels:
                expected_label = ols_labels[0] if ols_labels else "unknown"
                warning_msg = (
                    f"Provided value '{text}' doesn't precisely match '{expected_label}' "
                    f"for term '{term}'"
                )
                if field_name:
                    warning_msg += f" in field '{field_name}'"

                result.warnings.append(warning_msg)

                # store warning in context so it can be collected by BaseValidator
                try:
                    current_warnings = ontology_warnings_context.get()
                    current_warnings.append(warning_msg)
                    ontology_warnings_context.set(current_warnings)
                except LookupError:
                    pass

        return result

    def fetch_from_ols(self, term_id: str) -> List[Dict]:
        if self.cache_enabled and term_id in self._cache:
            return self._cache[term_id]

        try:
            url = f"http://www.ebi.ac.uk/ols/api/search?q={term_id.replace(':', '_')}&rows=100"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            docs = data.get('response', {}).get('docs', [])
            if self.cache_enabled:
                self._cache[term_id] = docs
            return docs
        except Exception as e:
            print(f"Error fetching from OLS: {e}")
            return []

class BreedSpeciesValidator:

    def __init__(self, ontology_validator):
        self.ontology_validator = ontology_validator

    def validate_breed_for_species(self, organism_term: str, breed_term: str, breed_text: str) -> List[str]:
        errors = []

        if organism_term not in SPECIES_BREED_LINKS:
            errors.append(f"Organism '{organism_term}' has no defined breed links.")
            return errors

        if breed_term in ["not applicable", "restricted access"]:
            return errors

        validation_result = self.ontology_validator.validate_ontology_term(
            term=breed_term,
            ontology_name="obo:lbo",
            allowed_classes=[SPECIES_BREED_LINKS[organism_term]],
            text=breed_text
        )
        if validation_result.errors:
            errors.append("Breed doesn't match the animal species")

        return errors


class RelationshipValidator:
    def __init__(self):
        self.biosamples_cache: Dict[str, Dict] = {}

    def validate_organism_relationships(self, organisms: List[Dict[str, Any]]) -> Dict[str, ValidationResult]:
        results = {}

        organism_map = {self.get_organism_identifier(org): org for org in organisms}

        biosample_ids = self.collect_biosample_ids(organisms)
        if biosample_ids:
            self.fetch_biosample_data(list(biosample_ids))

        # validate each organism's relationships
        for org in organisms:
            sample_name = self.get_organism_identifier(org)
            validation_result = self.validate_single_organism_relationships(
                org, sample_name, organism_map
            )

            if validation_result.errors or validation_result.warnings:
                results[sample_name] = validation_result

        return results

    def collect_biosample_ids(self, organisms: List[Dict[str, Any]]) -> Set[str]:
        biosample_ids = set()

        for org in organisms:
            for parent_id in self.normalize_child_of(org.get('Child Of')):
                if parent_id.startswith('SAM'):
                    biosample_ids.add(parent_id)

        return biosample_ids

    def normalize_child_of(self, child_of) -> List[str]:
        if isinstance(child_of, str):
            child_of = [child_of]
        elif not isinstance(child_of, list):
            child_of = []

        return [pid.strip() for pid in child_of if pid and str(pid).strip()]

    def validate_single_organism_relationships(
        self,
        organism: Dict[str, Any],
        sample_name: str,
        organism_map: Dict[str, Dict]
    ) -> ValidationResult:
        result = ValidationResult(field_path=f"organism.{sample_name}.child_of")
        current_species = organism.get('Organism', '')

        parent_ids = self.normalize_child_of(organism.get('Child Of'))

        for parent_id in parent_ids:
            if parent_id == 'restricted access':
                continue

            # check parent exists
            parent_data = self.get_parent_data(parent_id, organism_map)
            if parent_data is None:
                result.errors.append(f"Relationships part: no entity '{parent_id}' found")
                continue

            # species match
            self.validate_species_match(
                current_species,
                parent_data['species'],
                parent_id,
                result
            )

            # material type
            self.validate_parent_material(parent_data['material'], parent_id, result)

            # circular relationships
            if parent_id in organism_map:
                self.check_circular_relationship(
                    sample_name,
                    parent_id,
                    organism_map[parent_id],
                    result
                )

        return result

    def get_parent_data(self, parent_id: str, organism_map: Dict[str, Dict]) -> Optional[Dict]:
        if parent_id in organism_map:
            parent_org = organism_map[parent_id]
            return {
                'species': parent_org.get('Organism', ''),
                'material': 'organism',
                'data': parent_org
            }
        elif parent_id in self.biosamples_cache:
            biosample = self.biosamples_cache[parent_id]
            return {
                'species': biosample.get('organism', ''),
                'material': biosample.get('material', '').lower(),
                'data': biosample
            }

        return None

    def validate_species_match(
        self,
        current_species: str,
        parent_species: str,
        parent_id: str,
        result: ValidationResult
    ):
        if current_species and parent_species and current_species != parent_species:
            result.errors.append(
                f"Relationships part: the specie of the child '{current_species}' "
                f"doesn't match the specie of the parent '{parent_species}'"
            )

    def validate_parent_material(self, parent_material: str, parent_id: str, result: ValidationResult):
        allowed_materials = ALLOWED_RELATIONSHIPS.get('organism', [])

        if parent_material and parent_material not in allowed_materials:
            result.errors.append(
                f"Relationships part: referenced entity '{parent_id}' "
                f"does not match condition 'should be {' or '.join(allowed_materials)}'"
            )

    def check_circular_relationship(
        self,
        sample_name: str,
        parent_id: str,
        parent_data: Dict,
        result: ValidationResult
    ):
        parent_child_of = self.normalize_child_of(parent_data.get('Child Of'))

        if sample_name in parent_child_of:
            result.errors.append(
                f"Relationships part: parent '{parent_id}' "
                f"is listing the child as its parent"
            )


    # handles both 'Derived From' and 'Child Of' relationships
    # uses ALLOWED_RELATIONSHIPS from constants.py
    def validate_derived_from_relationships(self, all_samples: Dict[str, List[Dict]] = None) -> Dict[str, List[str]]:
        relationship_errors = {}
        relationships = {}

        if all_samples:
            for sample_type, samples in all_samples.items():
                for sample in samples:
                    sample_name = self.extract_sample_name(sample)
                    if sample_name:
                        relationships[sample_name] = {}

                        # get material type
                        material = self.extract_material(sample, sample_type)
                        relationships[sample_name]['material'] = material

                        # get derived_from/child_of relationships
                        related_records = self.extract_related_record(sample, sample_type)
                        if related_records:
                            relationships[sample_name]['relationships'] = related_records

        # validate relationships
        for sample_name, rel_info in relationships.items():
            if 'relationships' not in rel_info:
                continue

            current_material = rel_info['material']
            errors = []

            if any('restricted access' == ref for ref in rel_info['relationships']):
                continue

            for derived_from_ref in rel_info['relationships']:
                # check if referenced sample exists
                if derived_from_ref not in relationships:
                    errors.append(f"Relationships part: no entity '{derived_from_ref}' found")
                else:
                    # check material compatibility
                    ref_material = relationships[derived_from_ref]['material']
                    allowed_materials = ALLOWED_RELATIONSHIPS.get(current_material, [])

                    if ref_material not in allowed_materials:
                        errors.append(
                            f"Relationships part: referenced entity '{derived_from_ref}' "
                            f"does not match condition 'should be {' or '.join(allowed_materials)}'"
                        )

            if errors:
                relationship_errors[sample_name] = errors

        return relationship_errors

    def extract_sample_name(self, sample: Dict) -> str:
        return sample.get('Sample Name', '')

    def extract_material(self, sample: Dict, sample_type: str) -> str:
        material = sample.get('Material', '')
        if material:
            return material

        return sample_type

    def extract_related_record(self, sample: Dict, sample_type: str) -> List[str]:
        refs = []

        if 'Derived From' in sample:
            derived_from = sample['Derived From']
            if derived_from and derived_from.strip():
                refs.append(derived_from.strip())

        if 'Child Of' in sample:
            child_of = sample['Child Of']
            if isinstance(child_of, list):
                for parent in child_of:
                    if parent and parent.strip():
                        refs.append(parent.strip())
            elif child_of and child_of.strip():
                refs.append(child_of.strip())

        return [ref for ref in refs if ref and ref.strip()]

    def get_organism_identifier(self, organism: Dict) -> str:
        sample_name = organism.get('Sample Name', '')
        if sample_name and sample_name.strip():
            return sample_name.strip()
        return 'unknown'

    def fetch_biosample_data(self, biosample_ids: List[str]):
        for sample_id in biosample_ids:
            if sample_id in self.biosamples_cache:
                continue

            try:
                url = f"https://www.ebi.ac.uk/biosamples/samples/{sample_id}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()

                    cache_entry = {}

                    characteristics = data.get('characteristics', {})
                    if 'organism' in characteristics:
                        cache_entry['organism'] = characteristics['organism'][0].get('text', '')

                    if 'material' in characteristics:
                        cache_entry['material'] = characteristics['material'][0].get('text', '')

                    # relationships
                    relationships = []
                    for rel in data.get('relationships', []):
                        if rel['source'] == sample_id and rel['type'] in ['child of', 'derived from']:
                            relationships.append(rel['target'])
                    cache_entry['relationships'] = relationships

                    self.biosamples_cache[sample_id] = cache_entry
                else:
                    print(f"BioSample {sample_id} returned status {response.status_code}")
            except Exception as e:
                print(f"Error fetching BioSample {sample_id}: {e}")
