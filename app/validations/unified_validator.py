from datetime import datetime
from typing import Dict, List, Any, Optional, get_args, get_origin, Union
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from app.profiler import cprofiled
from app.validations.teleostei_embryo_validator import TeleosteiEmbryoValidator
from app.validations.organism_validator import OrganismValidator
from app.validations.organoid_validator import OrganoidValidator
from app.validations.specimen_validator import SpecimenValidator
from app.validations.teleostei_post_hatching_validator import TeleosteiPostHatchingValidator
from app.validations.single_cell_specimen_validator import SingleCellSpecimenValidator
from app.validations.pool_of_specimens_validator import PoolOfSpecimensValidator
from app.validations.cell_specimen_validator import CellSpecimenValidator
from app.validations.cell_culture_validator import CellCultureValidator
from app.validations.cell_line_validator import CellLineValidator
from app.validations.metadata_validator import SubmissionValidator, PersonValidator, OrganizationValidator
from app.validations.experiment_validator import ChipSeqInputDNAValidator, ChipSeqDNABindingProteinsValidator, RNASeqValidator, RNASeqValidator
from app.validations.analysis_validator import EVAAnalysisValidator, FAANGAnalysisValidator, ENAAnalysisValidator
from app.validations.generic_validator_classes import (
    collect_ontology_terms_from_data,
    OntologyValidator,
    RelationshipValidator
)
from app.validations.webin_submission import WebinBioSamplesSubmission


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
        # shared validator instances
        self.shared_ontology_validator = OntologyValidator(cache_enabled=True)
        self.shared_relationship_validator = RelationshipValidator()

        # sample validators - pass shared instances
        self.validators = {
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
        self.supported_sample_types = set(self.validators.keys())

        # metadata validators
        self.metadata_validators = {
            'submission': SubmissionValidator(),
            'person': PersonValidator(),
            'organization': OrganizationValidator()
        }
        self.supported_metadata_types = set(self.metadata_validators.keys())

        # experiment validators (keys must be lowercase with spaces)
        self.experiment_validators = {
            'chip-seq input dna': ChipSeqInputDNAValidator(),
            'chip-seq dna-binding proteins': ChipSeqDNABindingProteinsValidator(),
            'rna-seq': RNASeqValidator()
        }
        self.supported_experiment_types = set(self.experiment_validators.keys())

        # analysis validators
        self.analysis_validators = {
            'eva': EVAAnalysisValidator(),
            'faang': FAANGAnalysisValidator(),
            'ena': ENAAnalysisValidator()
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
                'invalid_analyses': 0
            },
            'results_by_type': {},
            'metadata_results': {},
            'experiment_results': {},
            'analysis_results': {},
            'reports_by_type': {},
            'metadata_reports': {},
            'experiment_reports': {},
            'analysis_reports': {}
        }

        # process each record type
        print("All sheet names in data:", list(data.keys()))
        print("Supported sample types:", list(self.supported_sample_types))
        print("Supported experiment types:", list(self.supported_experiment_types))
        print("Supported analysis types:", list(self.supported_analysis_types))
        print("Supported metadata types:", list(self.supported_metadata_types))
        print()
        
        # Track which keys have been processed to avoid double processing
        processed_keys = set()
        
        for sample_type, samples in data.items():
            if sample_type in self.supported_sample_types:
                processed_keys.add(sample_type)
                if not samples:
                    print(f"No samples found for type '{sample_type}'. Skipping.")
                    continue

                print(f"Validating {len(samples)} {sample_type} samples...")

                validator = self.validators[sample_type]

                # validate samples with appropriate parameters
                validation_kwargs = {
                    'validate_relationships': validate_relationships,
                    'all_samples': data
                }

                # Add specific parameters for sample types that support ontology text validation
                if sample_type in ['organoid', 'specimen_from_organism']:
                    validation_kwargs['validate_ontology_text'] = validate_ontology_text

                results = validator.validate_records(samples, **validation_kwargs)

                # Store results
                all_results['sample_types_processed'].append(sample_type)
                all_results['results_by_type'][sample_type] = results

                # Generate report
                report = validator.generate_validation_report(results)
                all_results['reports_by_type'][sample_type] = report

                # Update total summary
                summary = results['summary']
                all_results['total_summary']['total_samples'] += summary['total']
                all_results['total_summary']['valid_samples'] += summary['valid']
                all_results['total_summary']['invalid_samples'] += summary['invalid']
                all_results['total_summary']['warnings'] += summary['warnings']
                all_results['total_summary']['relationship_errors'] += summary['relationship_errors']

        # metadata validation
        for metadata_type, metadata_records in data.items():
            if metadata_type in self.supported_metadata_types:
                processed_keys.add(metadata_type)
                print(f"Validating {metadata_type} metadata...")

                validator = self.metadata_validators[metadata_type]
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

        # experiment validation
        print("\nChecking experiments...")
        for experiment_type, experiment_records in data.items():
            # Skip if already processed as sample or metadata
            if experiment_type in processed_keys:
                print(f"  Skipping '{experiment_type}' - already processed as sample/metadata")
                continue
                
            # Normalize experiment type name (handle both spaces and underscores)
            normalized_type = experiment_type.replace("_", " ").lower().strip()
            
            if normalized_type in self.supported_experiment_types:
                processed_keys.add(experiment_type)
                if not experiment_records:
                    print(f"No experiments found for type '{experiment_type}'. Skipping.")
                    continue

                print(f"Validating {len(experiment_records)} {normalized_type} experiments...")

                validator = self.experiment_validators[normalized_type]
                results = validator.validate_records(experiment_records)

                # Store results (use original key for consistency)
                all_results['experiment_types_processed'].append(experiment_type)
                all_results['experiment_results'][experiment_type] = results
                # Also store in results_by_type for frontend compatibility
                all_results['results_by_type'][experiment_type] = results

                # Generate report
                report = validator.generate_validation_report(results)
                all_results['experiment_reports'][experiment_type] = report

                # Update experiment summary (only if no error)
                if 'error' not in results:
                    summary = results['summary']
                    all_results['experiment_summary']['total_experiments'] += summary['total']
                    all_results['experiment_summary']['valid_experiments'] += summary['valid']
                    all_results['experiment_summary']['invalid_experiments'] += summary['invalid']
                else:
                    # If there's an error (no data), still count it
                    all_results['experiment_summary']['invalid_experiments'] += 1
            else:
                # Check if it looks like an experiment type (but not supported)
                if normalized_type in ['rna-seq', 'wgs', 'scrna-seq', 'hi-c', 'dnase-seq', 'bs-seq', 'em-seq', 'atac-seq', 'snatac-seq', 'cage-seq']:
                    print(f"  WARNING: Experiment type '{experiment_type}' is not yet supported. Supported types: {list(self.supported_experiment_types)}")
                elif normalized_type not in ['study', 'run', 'experiment ena', 'faang field values']:
                    # Unknown type, might be an experiment
                    print(f"  INFO: Unknown type '{experiment_type}' - skipping (not in supported experiment types)")

        # analysis validation
        print("\nChecking analyses...")
        for analysis_type, analysis_records in data.items():
            # Skip if already processed
            if analysis_type in processed_keys:
                print(f"  Skipping '{analysis_type}' - already processed")
                continue
                
            # Normalize analysis type name (handle both spaces and underscores)
            normalized_type = analysis_type.replace("_", " ").lower().strip()
            
            if normalized_type in self.supported_analysis_types:
                processed_keys.add(analysis_type)
                if not analysis_records:
                    print(f"No analyses found for type '{analysis_type}'. Skipping.")
                    continue

                print(f"Validating {len(analysis_records)} {normalized_type} analyses...")

                validator = self.analysis_validators[normalized_type]
                results = validator.validate_records(analysis_records)

                # Store results
                all_results['analysis_types_processed'].append(analysis_type)
                all_results['analysis_results'][analysis_type] = results
                # Also store in results_by_type for frontend compatibility
                all_results['results_by_type'][analysis_type] = results

                # Generate report
                report = validator.generate_validation_report(results)
                all_results['analysis_reports'][analysis_type] = report

                # Update analysis summary (only if no error)
                if 'error' not in results:
                    summary = results['summary']
                    all_results['analysis_summary']['total_analyses'] += summary['total']
                    all_results['analysis_summary']['valid_analyses'] += summary['valid']
                    all_results['analysis_summary']['invalid_analyses'] += summary['invalid']
                else:
                    # If there's an error (no data), still count it
                    all_results['analysis_summary']['invalid_analyses'] += 1

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
                report_lines.append(f"\n{validation_results['reports_by_type'][sample_type]}")
                report_lines.append("\n" + "-" * 60)

        # Individual experiment reports
        if validation_results.get('experiment_types_processed'):
            for experiment_type in validation_results['experiment_types_processed']:
                report_lines.append(f"\n{validation_results['experiment_reports'][experiment_type]}")
                report_lines.append("\n" + "-" * 60)

        # Individual analysis reports
        if validation_results.get('analysis_types_processed'):
            for analysis_type in validation_results['analysis_types_processed']:
                report_lines.append(f"\n{validation_results['analysis_reports'][analysis_type]}")
                report_lines.append("\n" + "-" * 60)

        return "\n".join(report_lines)

    def export_valid_samples_to_biosample(self, validation_results: Dict[str, Any]) -> Dict[str, List[Dict]]:
        biosample_exports = {}

        sample_types = validation_results.get('sample_types_processed', []) or []
        results_by_type = validation_results.get('results_by_type', {}) or {}

        for sample_type in sample_types:
            results = results_by_type.get(sample_type, {}) or {}

            st_key = sample_type.replace(" ", "_")
            valid_samples_key = f'valid_{st_key}s'
            # Handle double 's' at the end (e.g., 'pool_of_specimens' -> 'valid_pool_of_specimenss')
            # If st_key ends with 's', the key will have double 's', which is correct
            # Only remove one 's' if st_key doesn't end with 's'
            if valid_samples_key.endswith("ss") and not st_key.endswith("s"):
                valid_samples_key = valid_samples_key[:-1]

            print(f"Checking sample_type='{sample_type}', st_key='{st_key}', valid_samples_key='{valid_samples_key}'")
            print(f"  Available keys in results: {list(results.keys())}")
            print(f"  Has valid_samples_key: {valid_samples_key in results}")
            if valid_samples_key in results:
                print(
                    f"  Count in {valid_samples_key}: {len(results[valid_samples_key]) if results[valid_samples_key] else 0}")

            if valid_samples_key in results and results[valid_samples_key]:
                count = len(results[valid_samples_key])
                print(f"Type '{sample_type}': {count} valid samples found")
                validator = self.validators[sample_type]
                biosample_exports[sample_type] = []

                print(f"Processing {len(results[valid_samples_key])} samples of type '{sample_type}'")

                # Get organism samples for reference (needed for specimen samples)
                organism_samples = {}
                if 'organism' in results_by_type:
                    org_results = results_by_type.get('organism', {}) or {}
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

                for idx, valid_sample in enumerate(results[valid_samples_key]):
                    sample_name_export = valid_sample.get('sample_name')
                    try:
                        model = valid_sample.get('model')

                        # If model is a dict (serialized), convert it back to model instance
                        # Use recursive reconstruction to handle nested models (CellType, HealthStatus, etc.)
                        if isinstance(model, dict):
                            model_class = validator.get_model_class()
                            # Reconstruct model with nested models without re-validation
                            model = _reconstruct_model_from_dict(model_class, model)

                        biosample_data = validator.export_to_biosample_format(model)

                        # For specimen and pool samples, if organism/species are missing, try to get from parent organism
                        # Check the sample data for derived_from field (not relationships in biosample_data)
                        # Note: sample_type can be 'specimen from organism' (with spaces) or 'specimen_from_organism' (with underscores)
                        normalized_sample_type = sample_type.replace(" ", "_")
                        if normalized_sample_type in ['specimen_from_organism', 'pool_of_specimens']:
                            characteristics = biosample_data.get('characteristics', {})
                            if 'organism' not in characteristics or 'species' not in characteristics:
                                # Try to get from derived_from field in the sample data
                                sample_data = valid_sample.get('data', {})
                                derived_from = sample_data.get('Derived From') or sample_data.get('derived_from') or []

                                if not derived_from and hasattr(model, 'derived_from'):
                                    derived_from = getattr(model, 'derived_from', [])

                                # Also check if model is a dict and has the field
                                if not derived_from and isinstance(model, dict):
                                    derived_from = model.get('Derived From') or model.get('derived_from') or []

                                # Get parent name from derived_from
                                # For pool_of_specimens: derived_from is a list of specimen names
                                # For specimen_from_organism: derived_from is a list with one organism name
                                parent_name = None
                                if derived_from:
                                    if isinstance(derived_from, list) and len(derived_from) > 0:
                                        first = derived_from[0]
                                        if isinstance(first, dict):
                                            parent_name = first.get('value') or first.get('text') or first.get('target')
                                        else:
                                            parent_name = str(first)
                                    elif isinstance(derived_from, str):
                                        parent_name = derived_from

                                print(
                                    f"  Sample {sample_name_export}: parent_name={parent_name}, sample_type={normalized_sample_type}")

                                # Get organism from parent sample
                                # For specimen_from_organism: get from organism sample
                                # For pool_of_specimens: get from first specimen sample, then from its parent organism
                                if parent_name:
                                    parent_biosample_data = None

                                    if normalized_sample_type == 'specimen_from_organism':
                                        # Get from organism sample
                                        if parent_name in organism_samples:
                                            parent_model = organism_samples[parent_name]
                                            if hasattr(parent_model, 'organism') and hasattr(parent_model,
                                                                                             'organism_term_source_id'):
                                                from app.validations.organism_validator import OrganismValidator
                                                org_validator = OrganismValidator()
                                                parent_biosample_data = org_validator.export_to_biosample_format(
                                                    parent_model)

                                    elif normalized_sample_type == 'pool_of_specimens':
                                        # Get from first specimen sample, then from its parent organism
                                        # Find specimen sample in results
                                        # Try both formats: with spaces and with underscores
                                        specimen_results = results_by_type.get('specimen from organism',
                                                                               {}) or results_by_type.get(
                                            'specimen_from_organism', {}) or {}
                                        specimen_valid_key = 'valid_specimen_from_organisms'
                                        print(
                                            f"  Pool sample {sample_name_export}: Looking for parent specimen '{parent_name}' in {specimen_valid_key}")
                                        print(
                                            f"  Available specimen samples: {[s.get('sample_name') for s in specimen_results.get(specimen_valid_key, [])][:5]}")
                                        if specimen_valid_key in specimen_results:
                                            found_specimen = False
                                            for spec_sample in specimen_results[specimen_valid_key]:
                                                if spec_sample.get('sample_name') == parent_name:
                                                    found_specimen = True
                                                    print(f"  Found parent specimen: {parent_name}")
                                                    spec_model = spec_sample.get('model')
                                                    if isinstance(spec_model, dict):
                                                        spec_validator = self.validators.get('specimen_from_organism')
                                                        if spec_validator:
                                                            spec_model = _reconstruct_model_from_dict(
                                                                spec_validator.get_model_class(), spec_model)

                                                    # Get organism from specimen's parent
                                                    spec_data = spec_sample.get('data', {})
                                                    spec_derived_from = spec_data.get('Derived From') or spec_data.get(
                                                        'derived_from') or []
                                                    if not spec_derived_from and hasattr(spec_model, 'derived_from'):
                                                        spec_derived_from = getattr(spec_model, 'derived_from', [])

                                                    spec_parent_name = None
                                                    if spec_derived_from:
                                                        if isinstance(spec_derived_from, list) and len(
                                                                spec_derived_from) > 0:
                                                            first = spec_derived_from[0]
                                                            if isinstance(first, dict):
                                                                spec_parent_name = first.get('value') or first.get(
                                                                    'text') or first.get('target')
                                                            else:
                                                                spec_parent_name = str(first)
                                                        elif isinstance(spec_derived_from, str):
                                                            spec_parent_name = spec_derived_from

                                                    # Get organism from specimen's parent organism
                                                    if spec_parent_name and spec_parent_name in organism_samples:
                                                        print(f"  Found parent organism: {spec_parent_name}")
                                                        parent_model = organism_samples[spec_parent_name]
                                                        if hasattr(parent_model, 'organism') and hasattr(parent_model,
                                                                                                         'organism_term_source_id'):
                                                            from app.validations.organism_validator import \
                                                                OrganismValidator
                                                            org_validator = OrganismValidator()
                                                            parent_biosample_data = org_validator.export_to_biosample_format(
                                                                parent_model)
                                                            print(
                                                                f"  Got organism data from parent: {parent_biosample_data.get('characteristics', {}).get('organism')}")
                                                    else:
                                                        print(
                                                            f"  Parent organism '{spec_parent_name}' not found in organism_samples")
                                                    break
                                            if not found_specimen:
                                                print(
                                                    f"  Parent specimen '{parent_name}' not found in specimen_results")

                                    # Add organism and species if found
                                    if parent_biosample_data and 'organism' in parent_biosample_data.get(
                                            'characteristics', {}):
                                        characteristics['organism'] = parent_biosample_data['characteristics'][
                                            'organism']
                                        characteristics['species'] = parent_biosample_data['characteristics']['species']

                        biosample_exports[sample_type].append({
                            'sample_name': valid_sample['sample_name'],
                            'biosample_format': biosample_data
                        })
                        print(f"  [{idx + 1}/{len(results[valid_samples_key])}] Exported: {sample_name_export}")
                    except Exception as e:
                        print(
                            f"  [{idx + 1}/{len(results[valid_samples_key])}] Failed to export {sample_name_export}: {str(e)}")
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
            'analysis_types': list(self.supported_analysis_types)
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
