from typing import Dict, List, Any

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
from app.validations.generic_validator_classes import (
    collect_ontology_terms_from_data,
    OntologyValidator,
    RelationshipValidator
)


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
            'results_by_type': {},
            'metadata_results': {},
            'reports_by_type': {},
            'metadata_reports': {}
        }

        # process each record type
        print("Sample types in data:", list(data.keys()))
        for sample_type, samples in data.items():
            if sample_type in self.supported_sample_types:
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

        return "\n".join(report_lines)

    def export_valid_samples_to_biosample(self, validation_results: Dict[str, Any]) -> Dict[str, List[Dict]]:
        biosample_exports = {}

        for sample_type in validation_results['sample_types_processed']:
            results = validation_results['results_by_type'][sample_type]
            valid_samples_key = f'valid_{sample_type}s'

            if valid_samples_key in results and results[valid_samples_key]:
                validator = self.validators[sample_type]
                biosample_exports[sample_type] = []

                for valid_sample in results[valid_samples_key]:
                    biosample_data = validator.export_to_biosample_format(valid_sample['model'])
                    biosample_exports[sample_type].append({
                        'sample_name': valid_sample['sample_name'],
                        'biosample_format': biosample_data
                    })
        return biosample_exports

    def get_supported_types(self) -> Dict[str, List[str]]:
        return {
            'sample_types': list(self.supported_sample_types),
            'metadata_types': list(self.supported_metadata_types)
        }