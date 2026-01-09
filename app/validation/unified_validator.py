from datetime import datetime
from typing import Dict, List, Any, Optional, get_args, get_origin, Union
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from app.profiler import cprofiled
from app.validation.sample.teleostei_embryo_validator import TeleosteiEmbryoValidator
from app.validation.sample.organism_validator import OrganismValidator
from app.validation.sample.organoid_validator import OrganoidValidator
from app.validation.sample.specimen_validator import SpecimenValidator
from app.validation.sample.teleostei_post_hatching_validator import TeleosteiPostHatchingValidator
from app.validation.sample.single_cell_specimen_validator import SingleCellSpecimenValidator
from app.validation.sample.pool_of_specimens_validator import PoolOfSpecimensValidator
from app.validation.sample.cell_specimen_validator import CellSpecimenValidator
from app.validation.sample.cell_culture_validator import CellCultureValidator
from app.validation.sample.cell_line_validator import CellLineValidator
from app.validation.sample.metadata_validator import SubmissionValidator, PersonValidator, OrganizationValidator, \
    AnalysisSubmissionValidator
from app.validation.experiment_validator import ChipSeqInputDNAValidator, ChipSeqDNABindingProteinsValidator, \
    RNASeqValidator, RNASeqValidator
from app.validation.analysis.analysis_validator import EVAAnalysisValidator, FAANGAnalysisValidator, \
    ENAAnalysisValidator
from app.validation.sample.generic_validator_classes import (
    collect_ontology_terms_from_data,
    OntologyValidator,
    RelationshipValidator
)
from app.validation.webin_submission import WebinBioSamplesSubmission


def _reconstruct_model_from_dict(model_class: type[BaseModel], data: dict) -> BaseModel:
    """
    Reconstruct a Pydantic model from a dict, including nested models.
    Uses model_construct for the main model and recursively constructs nested models.
    Handles field aliases by converting them to field names.
    """
    if not isinstance(data, dict):
        return data

    # Get all model fields including parent class fields
    # In Pydantic v2, model_fields includes fields from parent classes
    all_fields = model_class.model_fields

    # Convert aliases to field names if needed
    # Pydantic model_construct expects field names, not aliases
    normalized_data = {}
    alias_to_field = {}
    for field_name, field_info in all_fields.items():
        if hasattr(field_info, 'alias') and field_info.alias:
            alias_to_field[field_info.alias] = field_name

    for key, value in data.items():
        # Check if key is an alias
        if key in alias_to_field:
            normalized_data[alias_to_field[key]] = value
        elif key in all_fields:
            # Key is already a field name
            normalized_data[key] = value
        else:
            # Unknown key, keep as-is (might be extra data)
            normalized_data[key] = value

    data = normalized_data

    # Get model fields to identify nested models
    constructed_data = {}
    for field_name, field_info in all_fields.items():
        if field_name in data:
            value = data[field_name]

            # Skip PydanticUndefined values
            if value is PydanticUndefined:
                continue

            field_annotation = field_info.annotation
            # Skip if annotation is PydanticUndefined
            if field_annotation is PydanticUndefined:
                constructed_data[field_name] = value
                continue

            # Handle list of nested models
            if isinstance(value, list):
                # Check if this field is a list of models
                try:
                    origin = get_origin(field_annotation)

                    # Handle Optional types (which are Union[T, None])
                    if origin is Union:
                        args = get_args(field_annotation)
                        # Find the non-None type from Union
                        inner_type = next((t for t in args if t is not type(None)), None)
                        if inner_type:
                            field_annotation = inner_type
                            origin = get_origin(field_annotation)

                    if origin is list or (hasattr(origin, '__name__') and origin.__name__ == 'List'):
                        args = get_args(field_annotation)
                        if args and len(args) > 0:
                            inner_type = args[0]
                            # Handle Union types within list (e.g., Union[str, BaseModel])
                            inner_origin = get_origin(inner_type)
                            if inner_origin is Union:
                                # Extract BaseModel from Union if present
                                union_args = get_args(inner_type)
                                inner_type = next(
                                    (t for t in union_args if isinstance(t, type) and issubclass(t, BaseModel)), None)

                            if inner_type and isinstance(inner_type, type) and issubclass(inner_type, BaseModel):
                                constructed_data[field_name] = [
                                    _reconstruct_model_from_dict(inner_type, item) if isinstance(item,
                                                                                                 dict) and not isinstance(
                                        item, BaseModel) else item
                                    for item in value
                                ]
                            else:
                                constructed_data[field_name] = value
                        else:
                            constructed_data[field_name] = value
                    else:
                        constructed_data[field_name] = value
                except (TypeError, AttributeError) as e:
                    # If we can't determine the type, just use the value as-is
                    constructed_data[field_name] = value
            # Handle single nested model
            elif isinstance(value, dict) and not isinstance(value, BaseModel):
                # Check if this field is a model
                # Handle Optional types (which are Union[T, None])
                origin = get_origin(field_annotation)
                if origin is Union:
                    args = get_args(field_annotation)
                    # Find the non-None type from Union
                    inner_type = next((t for t in args if t is not type(None)), None)
                    if inner_type:
                        field_annotation = inner_type

                if isinstance(field_annotation, type) and issubclass(field_annotation, BaseModel):
                    constructed_data[field_name] = _reconstruct_model_from_dict(field_annotation, value)
                else:
                    constructed_data[field_name] = value
            else:
                # Simple value (str, int, float, bool, etc.) - just use it as-is
                constructed_data[field_name] = value
        else:
            # Field not in data, use default if available
            # Skip if default is PydanticUndefined (field is required or has no default)
            if hasattr(field_info, 'default') and field_info.default is not PydanticUndefined:
                try:
                    # Check if default is callable (default_factory)
                    if callable(field_info.default):
                        constructed_data[field_name] = field_info.default()
                    else:
                        constructed_data[field_name] = field_info.default
                except (TypeError, AttributeError):
                    # Skip if we can't determine the default
                    pass

    # Also include any fields from data that might not be in model_fields (e.g., from parent classes)
    # This ensures we don't miss any fields, but we need to check if they are nested models
    for key, value in data.items():
        if key not in constructed_data and value is not PydanticUndefined:
            # Check if this field should be a nested model by looking at the field info
            if key in all_fields:
                field_info = all_fields[key]
                field_annotation = field_info.annotation

                # Handle list of nested models
                if isinstance(value, list):
                    try:
                        origin = get_origin(field_annotation)

                        # Handle Optional types (which are Union[T, None])
                        if origin is Union:
                            args = get_args(field_annotation)
                            # Find the non-None type from Union
                            inner_type = next((t for t in args if t is not type(None)), None)
                            if inner_type:
                                field_annotation = inner_type
                                origin = get_origin(field_annotation)

                        if origin is list or (hasattr(origin, '__name__') and origin.__name__ == 'List'):
                            args = get_args(field_annotation)
                            if args and len(args) > 0:
                                inner_type = args[0]
                                # Handle Union types within list (e.g., Union[str, BaseModel])
                                inner_origin = get_origin(inner_type)
                                if inner_origin is Union:
                                    # Extract BaseModel from Union if present
                                    union_args = get_args(inner_type)
                                    inner_type = next(
                                        (t for t in union_args if isinstance(t, type) and issubclass(t, BaseModel)),
                                        None)

                                if inner_type and isinstance(inner_type, type) and issubclass(inner_type, BaseModel):
                                    constructed_data[key] = [
                                        _reconstruct_model_from_dict(inner_type, item) if isinstance(item,
                                                                                                     dict) and not isinstance(
                                            item, BaseModel) else item
                                        for item in value
                                    ]
                                else:
                                    constructed_data[key] = value
                            else:
                                constructed_data[key] = value
                        else:
                            constructed_data[key] = value
                    except (TypeError, AttributeError):
                        constructed_data[key] = value
                # Handle single nested model
                elif isinstance(value, dict) and not isinstance(value, BaseModel):
                    # Handle Optional types (which are Union[T, None])
                    origin = get_origin(field_annotation)
                    if origin is Union:
                        args = get_args(field_annotation)
                        # Find the non-None type from Union
                        inner_type = next((t for t in args if t is not type(None)), None)
                        if inner_type:
                            field_annotation = inner_type

                    if isinstance(field_annotation, type) and issubclass(field_annotation, BaseModel):
                        constructed_data[key] = _reconstruct_model_from_dict(field_annotation, value)
                    else:
                        constructed_data[key] = value
                else:
                    constructed_data[key] = value
            else:
                # Field not in model_fields, just use as-is
                constructed_data[key] = value

    return model_class.model_construct(**constructed_data)


class UnifiedFAANGValidator:
    def __init__(self):
        # shared validator instances - samples
        self.shared_ontology_validator = OntologyValidator(cache_enabled=True)
        self.shared_relationship_validator = RelationshipValidator()

        # sample validators - pass shared instances
        self.sample_validators = {
            'organism': OrganismValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'organoid': OrganoidValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'specimen from organism': SpecimenValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'teleostei embryo': TeleosteiEmbryoValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'teleostei post-hatching': TeleosteiPostHatchingValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'single cell specimen': SingleCellSpecimenValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'pool of specimens': PoolOfSpecimensValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'cell specimen': CellSpecimenValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'cell culture': CellCultureValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            ),
            'cell line': CellLineValidator(
                ontology_validator=self.shared_ontology_validator,
                relationship_validator=self.shared_relationship_validator
            )
        }
        self.supported_sample_types = set(self.sample_validators.keys())

        # metadata validators - samples
        self.metadata_validators = {
            'submission': SubmissionValidator(),
            'person': PersonValidator(),
            'organization': OrganizationValidator()
        }
        self.supported_metadata_types = set(self.metadata_validators.keys())

        # metadata validators - analyses
        self.analysis_metadata_validators = {
            'submission': AnalysisSubmissionValidator(),
        }


        self.supported_analysis_metadata_types = set(self.analysis_metadata_validators.keys())

        # experiment validators (keys must be lowercase with spaces)
        self.experiment_validators = {
            'chip-seq input dna': ChipSeqInputDNAValidator(),
            'chip-seq dna-binding proteins': ChipSeqDNABindingProteinsValidator(),
            'rna-seq': RNASeqValidator()
        }
        self.supported_experiment_types = set(self.experiment_validators.keys())

        # analysis validators
        self.analysis_validators = {
            'ena': ENAAnalysisValidator(),
            'eva': EVAAnalysisValidator(),
            'faang': FAANGAnalysisValidator()
        }
        self.supported_analysis_types = set(self.analysis_validators.keys())

    def prefetch_all_ontology_terms(self, data: Dict[str, List[Dict[str, Any]]]):
        # collect unique term IDs
        term_ids = collect_ontology_terms_from_data(data)

        if not term_ids:
            print("No ontology terms to pre-fetch")
            return

        # shared ontology validator
        self.shared_ontology_validator.batch_fetch_from_ols_sync(list(term_ids))
        print(f"Pre-fetch complete. Cache now contains {len(self.shared_ontology_validator._cache)} terms.")

    @cprofiled()
    # async version for use in FastAPI endpoints
    async def prefetch_all_ontology_terms_async(self, data: Dict[str, List[Dict[str, Any]]]):
        # collect unique term IDs
        term_ids = collect_ontology_terms_from_data(data)

        if not term_ids:
            print("No ontology terms to pre-fetch")
            return

        # Use shared ontology validator
        result = await self.shared_ontology_validator.batch_fetch_from_ols(list(term_ids))
        self.shared_ontology_validator._cache.update(result)
        print(f"Pre-fetch complete. Cache now contains {len(self.shared_ontology_validator._cache)} terms.")

    def prefetch_all_biosample_ids(self, data: Dict[str, List[Dict[str, Any]]]):
        # shared relationship validator
        biosample_ids = self.shared_relationship_validator.collect_biosample_ids_from_samples(data)

        if not biosample_ids:
            print("No BioSample IDs to pre-fetch")
            return

        print(f"Found {len(biosample_ids)} BioSample IDs to fetch")

        # fetch all BioSample IDs concurrently
        self.shared_relationship_validator.batch_fetch_biosamples_sync(list(biosample_ids))

        print(
            f"Pre-fetch complete. BioSample cache now contains {len(self.shared_relationship_validator.biosamples_cache)} entries.")

    @cprofiled()
    # async version for FastAPI endpoint
    async def prefetch_all_biosample_ids_async(self, data: Dict[str, List[Dict[str, Any]]]):
        # shared relationship validator
        biosample_ids = self.shared_relationship_validator.collect_biosample_ids_from_samples(data)

        if not biosample_ids:
            print("No BioSample IDs to pre-fetch")
            return

        print(f"Found {len(biosample_ids)} BioSample IDs to fetch")

        # fetch all BioSample IDs concurrently using async method
        result = await self.shared_relationship_validator.batch_fetch_biosamples(list(biosample_ids))
        self.shared_relationship_validator.biosamples_cache.update(result)

        print(
            f"Pre-fetch complete. BioSample cache now contains {len(self.shared_relationship_validator.biosamples_cache)} entries.")

    @cprofiled()
    def validate_all_records(
        self,
        data: Dict[str, List[Dict[str, Any]]],
        validate_relationships: bool = True,
        validate_ontology_text: bool = True
    ) -> Dict[str, Any]:

        all_results = {
            'sample_types_processed': [],
            'metadata_types_processed': [],
            'experiment_types_processed': [],
            'analysis_types_processed': [],
            'total_summary': {
                'total_samples': 0,
                'valid_samples': 0,
                'invalid_samples': 0,
                'warnings': 0,
                'relationship_errors': 0
            },
            'metadata_summary': {
                'total_metadata': 0,
                'valid_metadata': 0,
                'invalid_metadata': 0
            },
            'experiment_summary': {
                'total_experiments': 0,
                'valid_experiments': 0,
                'invalid_experiments': 0
            },
            'analysis_summary': {
                'total_analyses': 0,
                'valid_analyses': 0,
                'invalid_analyses': 0,
                'warnings': 0
            },
            'sample_results': {},
            'metadata_results': {},
            'experiment_results': {},
            'analysis_results': {},
            'sample_reports': {},
            'metadata_reports': {},
            'experiment_reports': {},
            'analysis_reports': {}
        }

        has_samples = any(k in self.supported_sample_types for k in data.keys())
        has_analyses = any(k in self.supported_analysis_types for k in data.keys())

        if has_samples:
            print("Sample types in data:", [k for k in data.keys() if k in self.supported_sample_types])
            for sample_type, samples in data.items():
                if sample_type in self.supported_sample_types:
                    if not samples:
                        print(f"No samples found for type '{sample_type}'. Skipping.")
                        continue

                    print(f"Validating {len(samples)} {sample_type} samples...")

                    validator = self.sample_validators[sample_type]

                    validation_kwargs = {
                        'validate_relationships': validate_relationships,
                        'all_samples': data
                    }

                    if sample_type in ['organoid', 'specimen_from_organism']:
                        validation_kwargs['validate_ontology_text'] = validate_ontology_text

                    results = validator.validate_records(samples, **validation_kwargs)

                    # Store results
                    all_results['sample_types_processed'].append(sample_type)
                    all_results['sample_results'][sample_type] = results

                    # Generate report
                    report = validator.generate_validation_report(results)
                    all_results['sample_reports'][sample_type] = report

                    # Update total summary
                    summary = results['summary']
                    all_results['total_summary']['total_samples'] += summary['total']
                    all_results['total_summary']['valid_samples'] += summary['valid']
                    all_results['total_summary']['invalid_samples'] += summary['invalid']
                    all_results['total_summary']['warnings'] += summary['warnings']
                    all_results['total_summary']['relationship_errors'] += summary['relationship_errors']

        # Process metadata types
        for metadata_type, metadata_records in data.items():
            if metadata_type in self.supported_metadata_types or metadata_type in self.supported_analysis_metadata_types:
                print(f"Validating {metadata_type} metadata...")

                if has_analyses and not has_samples and metadata_type in self.supported_analysis_metadata_types:
                    validator = self.analysis_metadata_validators[metadata_type]
                elif metadata_type in self.supported_metadata_types:
                    validator = self.metadata_validators[metadata_type]
                else:
                    continue

                results = validator.validate_records(metadata_records)

                # Store results
                all_results['metadata_types_processed'].append(metadata_type)
                all_results['metadata_results'][metadata_type] = results

                # Generate report
                report = validator.generate_validation_report(results)
                all_results['metadata_reports'][metadata_type] = report

                # Update metadata summary (only if no error)
                if 'error' not in results:
                    summary = results['summary']
                    all_results['metadata_summary']['total_metadata'] += summary['total']
                    all_results['metadata_summary']['valid_metadata'] += summary['valid']
                    all_results['metadata_summary']['invalid_metadata'] += summary['invalid']
                else:
                    # If there's an error (no data), still count it
                    all_results['metadata_summary']['invalid_metadata'] += 1

        # Process analysis types
        if has_analyses:
            print("Analysis types in data:", [k for k in data.keys() if k in self.supported_analysis_types])
            for analysis_type, analyses in data.items():
                if analysis_type in self.supported_analysis_types:
                    if not analyses:
                        print(f"No analyses found for type '{analysis_type}'. Skipping.")
                        continue

                    print(f"Validating {len(analyses)} {analysis_type} analyses...")

                    validator = self.analysis_validators[analysis_type]
                    results = validator.validate_records(analyses)

                    # Store results
                    all_results['analysis_types_processed'].append(analysis_type)
                    all_results['analysis_results'][analysis_type] = results

                    # Generate report
                    report = validator.generate_validation_report(results)
                    all_results['analysis_reports'][analysis_type] = report

                    # Update analysis summary
                    summary = results['summary']
                    all_results['analysis_summary']['total_analyses'] += summary['total']
                    all_results['analysis_summary']['valid_analyses'] += summary['valid']
                    all_results['analysis_summary']['invalid_analyses'] += summary['invalid']
                    all_results['analysis_summary']['warnings'] += summary['warnings']

        return all_results

    def generate_unified_report(self, validation_results: Dict[str, Any]) -> str:
        report_lines = []

        # Individual metadata reports
        if validation_results['metadata_types_processed']:
            for metadata_type in validation_results['metadata_types_processed']:
                report_lines.append(f"\n{validation_results['metadata_reports'][metadata_type]}")
                report_lines.append("\n" + "-" * 60)

        # Individual sample reports
        if validation_results['sample_types_processed']:
            for sample_type in validation_results['sample_types_processed']:
                report_lines.append(f"\n{validation_results['sample_reports'][sample_type]}")
                report_lines.append("\n" + "-" * 60)

        # Individual experiment reports
        if validation_results.get('experiment_types_processed'):
            for experiment_type in validation_results['experiment_types_processed']:
                report_lines.append(f"\n{validation_results['experiment_reports'][experiment_type]}")
                report_lines.append("\n" + "-" * 60)

        # Analysis reports
        if validation_results.get('analysis_types_processed'):
            for analysis_type in validation_results['analysis_types_processed']:
                report_lines.append(f"\n{validation_results['analysis_reports'][analysis_type]}")
                report_lines.append("\n" + "-" * 60)

        return "\n".join(report_lines)

    def export_valid_samples_to_biosample(self, validation_results: Dict[str, Any]) -> Dict[str, List[Dict]]:
        biosample_exports = {}

        sample_types = validation_results.get('sample_types_processed', []) or []
        sample_results = validation_results.get('sample_results', {}) or {}

        # Get organism samples for reference
        organism_samples = {}
        if 'organism' in sample_results:
            org_results = sample_results.get('organism', {}) or {}
            org_valid_key = 'valid_organisms'
            if org_valid_key in org_results:
                for org_sample in org_results[org_valid_key]:
                    org_name = org_sample.get('sample_name')
                    org_model = org_sample.get('model')
                    if org_name and org_model:
                        if isinstance(org_model, dict):
                            org_validator = self.validators.get('organism')
                            if org_validator:
                                org_model = _reconstruct_model_from_dict(org_validator.get_model_class(),
                                                                         org_model)
                        organism_samples[org_name] = org_model

        # Build lookup tables: taxon_ids (samples with organism), missing_ids (samples needing lookup)
        taxon_ids = {}  # record_name -> organism term
        taxons = {}  # record_name -> organism text
        missing_ids = {}  # record_name -> parent_id (to look up)

        # PHASE 1: Initial Collection - iterate through ALL sheets and collect organism info or parent IDs
        print("Phase 1: Collecting organism information and missing IDs...")
        for sample_type in sample_types:
            results = results_by_type.get(sample_type, {}) or {}

            # Get validator to use its get_sample_type_name() method to construct the correct key
            validator = self.validators.get(sample_type)
            if not validator:
                print(f"  Warning: No validator found for sample type '{sample_type}', skipping")
                continue

            # Use the validator's get_sample_type_name() to get the normalized name used in results keys
            normalized_sample_type = validator.get_sample_type_name()
            valid_samples_key = f'valid_{normalized_sample_type}s'
            if valid_samples_key.endswith("ss") and not normalized_sample_type.endswith("s"):
                valid_samples_key = valid_samples_key[:-1]

            if valid_samples_key in results and results[valid_samples_key]:

                for valid_sample in results[valid_samples_key]:
                    record_name = valid_sample.get('sample_name')
                    if not record_name:
                        continue

                    model = valid_sample.get('model')
                    if isinstance(model, dict):
                        model = _reconstruct_model_from_dict(validator.get_model_class(), model)

                    # Check if model has organism field (for organism samples)
                    has_organism_directly = False
                    if hasattr(model, 'organism') and hasattr(model, 'organism_term_source_id'):
                        # This is an organism sample - extract organism info
                        from app.validation.sample.organism_validator import OrganismValidator
                        org_validator = OrganismValidator()
                        org_biosample_data = org_validator.export_to_biosample_format(model)
                        org_chars = org_biosample_data.get('characteristics', {})
                        if 'organism' in org_chars:
                            org_entry = org_chars['organism']
                            if isinstance(org_entry, list) and len(org_entry) > 0:
                                org_item = org_entry[0]
                                if isinstance(org_item, dict):
                                    if 'ontologyTerms' in org_item and len(org_item['ontologyTerms']) > 0:
                                        taxon_ids[record_name] = org_item['ontologyTerms'][0]
                                    taxons[record_name] = org_item.get('text', '')
                            has_organism_directly = True

                    # Also check exported biosample_data (some validators might add organism)
                    if not has_organism_directly:
                        biosample_data = validator.export_to_biosample_format(model)
                        characteristics = biosample_data.get('characteristics', {})

                        if 'organism' in characteristics and 'species' in characteristics:
                            # Direct organism information available in exported data
                            org_entry = characteristics['organism']
                            if isinstance(org_entry, list) and len(org_entry) > 0:
                                org_item = org_entry[0]
                                if isinstance(org_item, dict):
                                    if 'ontologyTerms' in org_item and len(org_item['ontologyTerms']) > 0:
                                        taxon_ids[record_name] = org_item['ontologyTerms'][0]
                                    taxons[record_name] = org_item.get('text', '')
                            has_organism_directly = True

                    if has_organism_directly:
                        print(f"  {record_name}: has organism directly")
                    else:
                        # No organism, check if has derived_from
                        sample_data = valid_sample.get('data', {})
                        derived_from = sample_data.get('Derived From') or sample_data.get('derived_from') or []
                        if not derived_from and hasattr(model, 'derived_from'):
                            derived_from = getattr(model, 'derived_from', [])
                        if not derived_from and isinstance(model, dict):
                            derived_from = model.get('Derived From') or model.get('derived_from') or []

                        if derived_from:
                            # Extract parent ID from derived_from
                            parent_id = None
                            if isinstance(derived_from, dict):
                                parent_id = derived_from.get('value') or derived_from.get('text') or derived_from.get(
                                    'target')
                            elif isinstance(derived_from, list) and len(derived_from) > 0:
                                first = derived_from[0]
                                if isinstance(first, dict):
                                    parent_id = first.get('value') or first.get('text') or first.get('target')
                                else:
                                    parent_id = str(first)
                            elif isinstance(derived_from, str):
                                parent_id = derived_from

                            if parent_id:
                                missing_ids[record_name] = parent_id
                                print(f"  {record_name}: missing organism, will look up from parent '{parent_id}'")

        # PHASE 2: Recursive Lookup - resolve missing_ids by recursively fetching from parents
        print(f"\nPhase 2: Recursively resolving {len(missing_ids)} missing organism IDs...")

        def fetch_taxon_information(record_name: str, parent_id: str, visited: set = None) -> bool:
            """
            Recursively fetch organism information for a record by following derived_from chain.
            Returns True if organism was found and added to taxon_ids/taxons.
            """
            if visited is None:
                visited = set()

            if record_name in visited:
                print(f"    Circular reference detected for '{record_name}', skipping")
                return False

            visited.add(record_name)

            # If parent_id already has organism info, use it
            if parent_id in taxon_ids:
                taxon_ids[record_name] = taxon_ids[parent_id]
                taxons[record_name] = taxons[parent_id]
                print(f"    {record_name}: got organism from cached parent '{parent_id}'")
                return True

            # Look up parent_id using recursive function
            parent_biosample_data = self._fetch_taxon_information_recursive(
                parent_id,
                results_by_type,
                organism_samples,
                biosample_exports,
                set()  # Use fresh visited set for recursive call
            )

            if parent_biosample_data and 'organism' in parent_biosample_data.get('characteristics', {}):
                org_entry = parent_biosample_data['characteristics']['organism']
                if isinstance(org_entry, list) and len(org_entry) > 0:
                    org_item = org_entry[0]
                    if isinstance(org_item, dict):
                        org_term = None
                        if 'ontologyTerms' in org_item and len(org_item['ontologyTerms']) > 0:
                            org_term = org_item['ontologyTerms'][0]
                        org_text = org_item.get('text', '')

                        # Cache for both record_name and parent_id (if parent_id also needs it)
                        if org_term:
                            taxon_ids[record_name] = org_term
                            # Also cache for parent_id if it's in missing_ids (for future lookups)
                            if parent_id in missing_ids and parent_id not in taxon_ids:
                                taxon_ids[parent_id] = org_term
                        if org_text:
                            taxons[record_name] = org_text
                            if parent_id in missing_ids and parent_id not in taxons:
                                taxons[parent_id] = org_text

                        print(
                            f"    {record_name}: got organism from parent '{parent_id}' (term: {org_term}, text: {org_text})")
                        return True

            print(f"    {record_name}: could not resolve organism from parent '{parent_id}'")
            return False

        # Resolve all missing_ids
        for record_name, parent_id in missing_ids.items():
            if record_name not in taxon_ids:  # Only process if not already resolved
                fetch_taxon_information(record_name, parent_id)

        # PHASE 3: Export all samples with organism information added
        print(f"\nPhase 3: Exporting all samples with organism information...")
        for sample_type in sample_types:
            results = results_by_type.get(sample_type, {}) or {}

            # Get validator to use its get_sample_type_name() method to construct the correct key
            # This ensures we use the same normalization logic that was used when creating the results
            validator = self.validators.get(sample_type)
            if not validator:
                print(f"  Warning: No validator found for sample type '{sample_type}', skipping")
                continue

            # Use the validator's get_sample_type_name() to get the normalized name used in results keys
            normalized_sample_type = validator.get_sample_type_name()
            valid_samples_key = f'valid_{normalized_sample_type}s'
            if valid_samples_key.endswith("ss") and not normalized_sample_type.endswith("s"):
                valid_samples_key = valid_samples_key[:-1]

            if valid_samples_key in results and results[valid_samples_key]:
                count = len(results[valid_samples_key])
                print(f"Type '{sample_type}': {count} valid samples found")
                biosample_exports[sample_type] = []

                for idx, valid_sample in enumerate(results[valid_samples_key]):
                    sample_name_export = valid_sample.get('sample_name')
                    try:
                        model = valid_sample.get('model')

                        if isinstance(model, dict):
                            model = _reconstruct_model_from_dict(validator.get_model_class(), model)

                        biosample_data = validator.export_to_biosample_format(model)
                        characteristics = biosample_data.get('characteristics', {})

                        # Add organism if we resolved it in Phase 2
                        if sample_name_export in taxon_ids:
                            # Build organism entry from resolved taxon info
                            organism_entry = [{
                                'text': taxons.get(sample_name_export, ''),
                                'ontologyTerms': [taxon_ids[sample_name_export]] if taxon_ids[
                                    sample_name_export] else []
                            }]
                            characteristics['organism'] = organism_entry
                            characteristics['species'] = organism_entry
                            print(f"  {sample_name_export}: added resolved organism")
                        elif 'organism' not in characteristics or 'species' not in characteristics:
                            # Final attempt: try recursive lookup as fallback
                            sample_data = valid_sample.get('data', {})
                            derived_from = sample_data.get('Derived From') or sample_data.get('derived_from') or []
                            if not derived_from and hasattr(model, 'derived_from'):
                                derived_from = getattr(model, 'derived_from', [])
                            if not derived_from and isinstance(model, dict):
                                derived_from = model.get('Derived From') or model.get('derived_from') or []

                            parent_name = None
                            if derived_from:
                                if isinstance(derived_from, list) and len(derived_from) > 0:
                                    first = derived_from[0]
                                    if isinstance(first, dict):
                                        parent_name = first.get('value') or first.get('text') or first.get('target')
                                    else:
                                        parent_name = str(first)
                                elif isinstance(derived_from, dict):
                                    parent_name = derived_from.get('value') or derived_from.get(
                                        'text') or derived_from.get('target')
                                elif isinstance(derived_from, str):
                                    parent_name = derived_from

                            if parent_name:
                                parent_biosample_data = self._fetch_taxon_information_recursive(
                                    parent_name,
                                    results_by_type,
                                    organism_samples,
                                    biosample_exports
                                )

                                if parent_biosample_data and 'organism' in parent_biosample_data.get('characteristics',
                                                                                                     {}):
                                    characteristics['organism'] = parent_biosample_data['characteristics']['organism']
                                    characteristics['species'] = parent_biosample_data['characteristics']['species']
                                    print(f"  {sample_name_export}: added organism via fallback lookup")

                        biosample_exports[sample_type].append({
                            'sample_name': valid_sample['sample_name'],
                            'biosample_format': biosample_data
                        })

                        print(f"  [{idx + 1}/{count}] Exported: {sample_name_export}")
                    except Exception as e:
                        print(
                            f"  [{idx + 1}/{count}] Failed to export {sample_name_export}: {str(e)}")
                        import traceback
                        traceback.print_exc()

        total_exported = sum(len(samples) for samples in biosample_exports.values())
        print(f"Exported samples: {total_exported}")
        for sample_type, sample_list in biosample_exports.items():
            print(f"  - {sample_type}: {len(sample_list)} samples")
        return biosample_exports

    def get_supported_types(self) -> Dict[str, List[str]]:
        return {
            'sample_types': list(self.supported_sample_types),
            'metadata_types': list(self.supported_metadata_types),
            'experiment_types': list(self.supported_experiment_types),
            'analysis_types': list(self.supported_analysis_types),
            'analysis_metadata_types': list(self.supported_analysis_metadata_types)
        }

    def submit_to_biosamples(
        self,
        validation_results: Dict[str, Any],
        webin_username: str,
        webin_password: str,
        domain: str,
        mode: str = 'test',
        person_data: Optional[Dict[str, Any]] = None,
        organization_data: Optional[Dict[str, Any]] = None,
        update_existing: bool = False
    ) -> Dict[str, Any]:
        try:
            # Print validation summary
            total_summary = validation_results.get('total_summary', {}) or {}
            valid_samples = total_summary.get('valid_samples', 0)
            invalid_samples = total_summary.get('invalid_samples', 0)
            print(f"Valid samples: {valid_samples}")
            print(f"Invalid samples: {invalid_samples}")

            biosample_exports = self.export_valid_samples_to_biosample(validation_results)

            if not biosample_exports:
                return {
                    'success': False,
                    'error': 'No valid samples to submit',
                    'biosamples_ids': {}
                }

            metadata_results = validation_results.get('metadata_results', {}) or {}

            if person_data is None and 'person' in metadata_results:
                person_results = metadata_results['person']
                if person_results.get('valid') and len(person_results['valid']) > 0:
                    person_data = person_results['valid'][0]

            if organization_data is None and 'organization' in metadata_results:
                org_results = metadata_results['organization']
                if org_results.get('valid') and len(org_results['valid']) > 0:
                    organization_data = org_results['valid'][0]

            contact_list = None
            organization_list = None

            if person_data:
                person_model = person_data.get('model') if isinstance(person_data, dict) else person_data
                if hasattr(person_model, 'person_first_name'):
                    contact_list = [{
                        'FirstName': person_model.person_first_name,
                        'LastName': person_model.person_last_name,
                        'MidInitials': getattr(person_model, 'person_initials', '') or '',
                        'E-mail': person_model.person_email,
                        'Role': person_model.person_role
                    }]

            if organization_data:
                org_model = organization_data.get('model') if isinstance(organization_data, dict) else organization_data
                if hasattr(org_model, 'organization_name'):
                    organization_list = [{
                        'Name': org_model.organization_name,
                        'Address': org_model.organization_address,
                        'URL': org_model.organization_uri,
                        'Role': org_model.organization_role
                    }]

            submission_data = []

            for sample_type, sample_list in biosample_exports.items():
                for sample in sample_list:
                    sample_name = sample.get('sample_name')
                    biosample_format = sample.get('biosample_format', {}) or {}

                    characteristics = biosample_format.get('characteristics', {}) or {}
                    relationships_raw = biosample_format.get('relationships', []) or []

                    release_value = biosample_format.get('release')
                    if not release_value:
                        release_value = datetime.utcnow().replace(microsecond=0).isoformat()

                    submission_item = {
                        'name': sample_name,
                        'release': release_value,
                        'characteristics': characteristics,
                    }

                    if relationships_raw:
                        rels = []
                        for rel in relationships_raw:
                            rels.append({
                                'source': sample_name,
                                'type': rel.get('type', ''),
                                'target': rel.get('target', '')
                            })
                        if rels:
                            submission_item['relationships'] = rels

                    if contact_list:
                        submission_item['contact'] = contact_list
                    if organization_list:
                        submission_item['organization'] = organization_list

                    submission_data.append(submission_item)

            print(f"Prepared for submission: {len(submission_data)} samples")

            submission = WebinBioSamplesSubmission(
                username=webin_username,
                password=webin_password,
                json_to_submit=submission_data,
                mode=mode,
                domain=domain
            )

            if update_existing:
                biosamples_ids = submission.update_records()
            else:
                biosamples_ids = submission.submit_records()

            if isinstance(biosamples_ids, dict) and 'Error' in biosamples_ids:
                return {
                    'success': False,
                    'error': biosamples_ids['Error'],
                    'biosamples_ids': {},
                    'errors': [biosamples_ids['Error']]
                }

            return {
                'success': True,
                'biosamples_ids': biosamples_ids,
                'submitted_count': len(biosamples_ids),
                'errors': []
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'biosamples_ids': {},
                'errors': [str(e)]
            }