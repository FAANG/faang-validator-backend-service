from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
import requests
import asyncio
import aiohttp
import re
from contextvars import ContextVar
from app.validation.constants import SPECIES_BREED_LINKS, ALLOWED_RELATIONSHIPS, ELIXIR_VALIDATOR_URL
from app.validation.sample.base_validator import ontology_warnings_context
from app.validation.validation_utils import normalize_ontology_term

# Context variable to share OntologyValidator instance during Pydantic validation
ontology_validator_context: ContextVar[Optional['OntologyValidator']] = ContextVar('ontology_validator', default=None)


def get_ontology_validator() -> 'OntologyValidator':
    """
    Get the shared OntologyValidator instance from context, or create a new one if not available.
    This allows Pydantic validators to use the pre-fetched cache.
    """
    validator = ontology_validator_context.get(None)
    if validator is None:
        # Fallback: create a new instance if not in context (shouldn't happen during validation)
        validator = OntologyValidator(cache_enabled=True)
    return validator


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
                               field_name: str = None,
                               allow_fetch: bool = False) -> ValidationResult:

        result = ValidationResult(field_path=f"{ontology_name}:{term}")

        if term == "restricted access":
            return result

        # check OLS for term validity
        # During Pydantic validation, allow_fetch should be False to prevent blocking HTTP calls
        # All terms should be pre-fetched
        ols_data = self.fetch_from_ols(term, allow_fetch=allow_fetch)
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

    def fetch_from_ols(self, term_id: str, allow_fetch: bool = True) -> List[Dict]:
        if self.cache_enabled and term_id in self._cache:
            return self._cache[term_id]

        # During validation, we should not make blocking HTTP calls
        # All terms should be pre-fetched. If not in cache, return empty
        if not allow_fetch:
            print(f"Warning: Term {term_id} not in cache and fetching disabled. This should have been pre-fetched.")
            return []

        try:
            print(term_id)
            url = f"https://www.ebi.ac.uk/ols4/api/search?q={term_id}&rows=100"
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

    async def fetch_from_ols_async(self, term_id: str, session: aiohttp.ClientSession) -> tuple[str, List[Dict]]:
        if self.cache_enabled and term_id in self._cache:
            return term_id, self._cache[term_id]

        try:
            url = f"https://www.ebi.ac.uk/ols4/api/search?q={term_id}&rows=100"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()

                docs = data.get('response', {}).get('docs', [])
                if self.cache_enabled:
                    self._cache[term_id] = docs
                return term_id, docs
        except Exception as e:
            print(f"Error fetching from OLS for {term_id}: {e}")
            return term_id, []

    async def batch_fetch_from_ols(self, term_ids: List[str]) -> Dict[str, List[Dict]]:
        # Filter out terms already in cache
        terms_to_fetch = [tid for tid in term_ids if tid not in self._cache]

        if not terms_to_fetch:
            # all terms are cached
            return {tid: self._cache[tid] for tid in term_ids}

        # fetch terms from OLS concurrently
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_from_ols_async(term_id, session) for term_id in terms_to_fetch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        result_dict = {}
        for result in results:
            if isinstance(result, Exception):
                print(f"Task failed with exception: {result}")
                continue
            term_id, docs = result
            result_dict[term_id] = docs

        # add cached terms
        for term_id in term_ids:
            if term_id in self._cache and term_id not in result_dict:
                result_dict[term_id] = self._cache[term_id]

        return result_dict

    def batch_fetch_from_ols_sync(self, term_ids: List[str]) -> Dict[str, List[Dict]]:
        # Check if all terms are already cached
        terms_to_fetch = [tid for tid in term_ids if tid not in self._cache]

        if not terms_to_fetch:
            # All terms are cached, return them directly
            return {tid: self._cache[tid] for tid in term_ids}

        # Need to fetch some terms - check if we're in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're already in an event loop (e.g., FastAPI)
            # Create task to fetch in the current loop
            print(f"Fetching {len(terms_to_fetch)} additional terms from OLS...")
            task = loop.create_task(self.batch_fetch_from_ols(terms_to_fetch))
            # This will raise an error since we can't await here
            # The proper solution is to ensure ALL terms are pre-fetched
            raise RuntimeError(
                f"Cannot fetch ontology terms synchronously from async context. "
                f"Missing {len(terms_to_fetch)} terms. Ensure pre-fetching is complete."
            )
        except RuntimeError as e:
            if "no running event loop" in str(e).lower():
                # No event loop running, safe to use asyncio.run()
                return asyncio.run(self.batch_fetch_from_ols(term_ids))
            else:
                # Re-raise the error about missing pre-fetch
                raise


def collect_ontology_terms_from_data(data: Dict[str, List[Dict]]) -> Set[str]:
    term_ids = set()

    # common term ID field patterns to look for
    term_id_fields = [
        'Term Source ID',
        'Organism Term Source ID',
        'Sex Term Source ID',
        'Breed Term Source ID',
        'Developmental Stage Term Source ID',
        'Organism Part Term Source ID',
        'Organ Model Term Source ID',
        'Organ Part Model Term Source ID',
        'Maturity State Term Source ID',
        'Culture Type Term Source ID',
        'Disease Term Source ID',
    ]

    for sample_type, samples in data.items():
        for sample in samples:
            for field in term_id_fields:
                if field in sample and sample[field]:
                    term_value = sample[field]
                    if term_value not in ["restricted access", "not applicable", "not collected", "not provided", ""]:
                        # normalize the term
                        if '_' in term_value and ':' not in term_value:
                            term_value = term_value.replace('_', ':', 1)
                        term_ids.add(term_value)

            # check health status (nested structure)
            if 'Health Status' in sample and sample['Health Status']:
                health_statuses = sample['Health Status']
                if isinstance(health_statuses, list):
                    for status in health_statuses:
                        if isinstance(status, dict) and 'term' in status:
                            term_value = status['term']
                            if term_value not in ["restricted access", "not applicable", "not collected",
                                                  "not provided", ""]:
                                if '_' in term_value and ':' not in term_value:
                                    term_value = term_value.replace('_', ':', 1)
                                term_ids.add(term_value)

            # check cell type (nested structure)
            if 'Cell Type' in sample and sample['Cell Type']:
                cell_types = sample['Cell Type']
                if isinstance(cell_types, list):
                    for ct in cell_types:
                        if isinstance(ct, dict) and 'term' in ct:
                            term_value = ct['term']
                            if term_value not in ["restricted access", "not applicable", "not collected",
                                                  "not provided", ""]:
                                if '_' in term_value and ':' not in term_value:
                                    term_value = term_value.replace('_', ':', 1)
                                term_ids.add(term_value)

    return term_ids


def collect_ontology_terms_from_experiments(experiment_data: Dict[str, List[Dict]]) -> set:
    terms = set()

    term_fields = [
        'Experiment Target Term Source ID',
        'ChIP Target Term Source ID'
    ]

    for exp_type, records in experiment_data.items():
        for record in records:
            for field in term_fields:
                if field in record:
                    term_value = record[field]
                    if term_value and term_value not in [
                        "restricted access",
                        "not applicable",
                        "not collected",
                        "not provided",
                        ""
                    ]:
                        term_value = normalize_ontology_term(term_value)
                        terms.add(term_value)

    return terms


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

    async def fetch_biosample_async(self, sample_id: str, session: aiohttp.ClientSession) -> tuple[str, Dict]:
        if sample_id in self.biosamples_cache:
            return sample_id, self.biosamples_cache[sample_id]

        try:
            url = f"https://www.ebi.ac.uk/biosamples/samples/{sample_id}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()

                if 'error' in data:
                    return sample_id, {}

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

                return sample_id, cache_entry

        except Exception as e:
            print(f"Error fetching BioSample {sample_id} async: {e}")
            return sample_id, {}

    async def batch_fetch_biosamples(self, biosample_ids: List[str]) -> Dict[str, Dict]:
        # filter IDs already in cache
        ids_to_fetch = [bid for bid in biosample_ids if bid not in self.biosamples_cache]

        if not ids_to_fetch:
            return {bid: self.biosamples_cache[bid] for bid in biosample_ids}

        # fetch BioSamples data concurrently
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_biosample_async(sample_id, session) for sample_id in ids_to_fetch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        result_dict = {}
        for result in results:
            if isinstance(result, Exception):
                print(f"Task failed with exception: {result}")
                continue
            sample_id, cache_entry = result
            if cache_entry:
                result_dict[sample_id] = cache_entry

        # add cached IDs
        for sample_id in biosample_ids:
            if sample_id in self.biosamples_cache and sample_id not in result_dict:
                result_dict[sample_id] = self.biosamples_cache[sample_id]

        return result_dict

    def batch_fetch_biosamples_sync(self, biosample_ids: List[str]) -> Dict[str, Dict]:
        # Check if all IDs are already cached
        ids_to_fetch = [bid for bid in biosample_ids if bid not in self.biosamples_cache]

        if not ids_to_fetch:
            # All IDs are cached, return them directly
            return {bid: self.biosamples_cache[bid] for bid in biosample_ids}

        # Need to fetch some IDs - check if we're in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're already in an event loop (e.g., FastAPI)
            print(f"Missing {len(ids_to_fetch)} BioSample IDs in cache")
            raise RuntimeError(
                f"Cannot fetch BioSamples synchronously from async context. "
                f"Missing {len(ids_to_fetch)} IDs. Ensure pre-fetching is complete."
            )
        except RuntimeError as e:
            if "no running event loop" in str(e).lower():
                # No event loop running, safe to use asyncio.run()
                result = asyncio.run(self.batch_fetch_biosamples(biosample_ids))

                # update cache with results
                for sample_id, cache_entry in result.items():
                    if sample_id not in self.biosamples_cache:
                        self.biosamples_cache[sample_id] = cache_entry

                return result
            else:
                # Re-raise the error about missing pre-fetch
                raise

    def is_biosample_id(self, value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        return bool(re.match(r'^SAM[AED][AG]?\d+$', value.strip()))

    def collect_biosample_ids_from_samples(self, all_samples: Dict[str, List[Dict]]) -> Set[str]:
        biosample_ids = set()

        for sample_type, samples in all_samples.items():
            for sample in samples:
                # check derived_from field
                if 'Derived From' in sample:
                    derived_from = sample['Derived From']

                    if isinstance(derived_from, list):
                        for item in derived_from:
                            if item and self.is_biosample_id(str(item)):
                                biosample_ids.add(str(item).strip())
                    elif derived_from and self.is_biosample_id(str(derived_from)):
                        biosample_ids.add(str(derived_from).strip())

                # child_of field (organisms)
                if 'Child Of' in sample:
                    child_of = sample['Child Of']
                    if isinstance(child_of, list):
                        for parent in child_of:
                            if parent and self.is_biosample_id(str(parent)):
                                biosample_ids.add(str(parent).strip())
                    elif child_of and self.is_biosample_id(str(child_of)):
                        biosample_ids.add(str(child_of).strip())

                # same_as field (SampleCoreMetadata)
                if 'Same as' in sample:
                    same_as = sample['Same as']
                    if same_as and self.is_biosample_id(str(same_as)):
                        biosample_ids.add(str(same_as).strip())

        return biosample_ids

    def validate_organism_relationships(self, organisms: List[Dict[str, Any]]) -> Dict[str, ValidationResult]:
        results = {}

        organism_map = {self.get_organism_identifier(org): org for org in organisms}

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
                if self.is_biosample_id(parent_id):
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

    def validate_derived_from_relationships(self, all_samples: Dict[str, List[Dict]] = None) -> Dict[str, List[str]]:
        relationship_errors = {}
        relationships = {}

        if not all_samples:
            return relationship_errors

        # collect all relationships and local sample info
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

            current_material = self.normalize_material_name(rel_info['material'])
            errors = []

            if any('restricted access' == ref for ref in rel_info['relationships']):
                continue

            for derived_from_ref in rel_info['relationships']:
                # Check if reference exists in local samples OR BioSamples

                # Try local samples first
                if derived_from_ref in relationships:
                    ref_material = self.normalize_material_name(relationships[derived_from_ref]['material'])
                # Try BioSamples cache
                elif derived_from_ref in self.biosamples_cache:
                    ref_material = self.normalize_material_name(
                        self.biosamples_cache[derived_from_ref].get('material', '')
                    )
                else:
                    # Not found in either source
                    errors.append(f"Relationships part: no entity '{derived_from_ref}' found")
                    continue

                # Validate material compatibility
                allowed_materials = ALLOWED_RELATIONSHIPS.get(current_material, [])

                # Normalize allowed materials for comparison
                allowed_materials_normalized = [self.normalize_material_name(m) for m in allowed_materials]

                if ref_material not in allowed_materials_normalized:
                    errors.append(
                        f"Relationships part: referenced entity '{derived_from_ref}' "
                        f"does not match condition 'should be {' or '.join(allowed_materials)}'"
                    )

            if errors:
                relationship_errors[sample_name] = errors

        return relationship_errors

    def normalize_material_name(self, material: str) -> str:
        if not material:
            return ''
        return material.lower().replace(' ', '_')

    def extract_sample_name(self, sample: Dict) -> str:
        return sample.get('Sample Name', '')

    def extract_material(self, sample: Dict, sample_type: str) -> str:
        material = sample.get('Material', '')
        if material:
            return material

        return sample_type

    def extract_related_record(self, sample: Dict, sample_type: str) -> List[str]:
        refs = []

        # Derived From always a list after Pydantic validation
        if 'Derived From' in sample:
            derived_from = sample['Derived From']

            if isinstance(derived_from, list):
                for item in derived_from:
                    if item and str(item).strip():
                        refs.append(str(item).strip())
            elif derived_from and str(derived_from).strip():
                refs.append(str(derived_from).strip())

        # Child Of (organisms)
        if 'Child Of' in sample:
            child_of = sample['Child Of']
            if isinstance(child_of, list):
                for parent in child_of:
                    if parent and str(parent).strip():
                        refs.append(str(parent).strip())
            elif child_of and str(child_of).strip():
                refs.append(str(child_of).strip())

        return [ref for ref in refs if ref and ref.strip()]

    def get_organism_identifier(self, organism: Dict) -> str:
        sample_name = organism.get('Sample Name', '')
        if sample_name and sample_name.strip():
            return sample_name.strip()
        return 'unknown'


