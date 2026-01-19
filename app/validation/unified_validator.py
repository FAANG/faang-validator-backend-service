from typing import Dict, List, Any
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
from app.validation.analysis.analysis_validator import (
    ENAAnalysisValidator,
    EVAAnalysisValidator,
    FAANGAnalysisValidator
)
from app.validation.generic_validator_classes import (
    collect_ontology_terms_from_data,
    collect_ontology_terms_from_experiments,
    OntologyValidator,
    RelationshipValidator
)
from app.validation.experiment.atac_seq_validator import ATACSeqValidator
from app.validation.experiment.chip_seq_validator import (
    ChIPSeqDNABindingProteinsValidator,
    ChIPSeqInputDNAValidator
)
from app.validation.experiment.additional_experiment_validators import (
    BSSeqValidator,
    CAGESeqValidator,
    DNaseSeqValidator,
    EMSeqValidator,
    HiCValidator,
    RNASeqValidator,
    scRNASeqValidator,
    scATACSeqValidator,
    WGSValidator
)


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

        # analysis validators
        self.analysis_validators = {
            'ena': ENAAnalysisValidator(),
            'eva': EVAAnalysisValidator(),
            'faang': FAANGAnalysisValidator()
        }
        self.supported_analysis_types = set(self.analysis_validators.keys())

        # experiment validators
        self.experiment_validators = {
            'atac-seq': ATACSeqValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'bs-seq': BSSeqValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'cage-seq': CAGESeqValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'chip-seq dna-binding proteins': ChIPSeqDNABindingProteinsValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'chip-seq input dna': ChIPSeqInputDNAValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'dnase-seq': DNaseSeqValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'em-seq': EMSeqValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'hi-c': HiCValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'rna-seq': RNASeqValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'scrna-seq': scRNASeqValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'snatac-seq': scATACSeqValidator(
                ontology_validator=self.shared_ontology_validator
            ),
            'wgs': WGSValidator(
                ontology_validator=self.shared_ontology_validator
            )
        }
        self.supported_experiment_types = set(self.experiment_validators.keys())


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
    async def prefetch_all_ontology_terms_async(self, data_type, data: Dict[str, List[Dict[str, Any]]]):
        # collect unique term IDs
        if data_type == "experiment":
            term_ids = collect_ontology_terms_from_experiments(data)
        else:
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
            'analysis_types_processed': [],
            'experiment_types_processed': [],
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
            'analysis_summary': {
                'total_analyses': 0,
                'valid_analyses': 0,
                'invalid_analyses': 0,
                'warnings': 0
            },
            'experiment_summary': {
                'total_experiments': 0,
                'valid_experiments': 0,
                'invalid_experiments': 0,
                'warnings': 0,
                'relationship_errors': 0
            },
            'sample_results': {},
            'metadata_results': {},
            'analysis_results': {},
            'experiment_results': {},
            'sample_reports': {},
            'metadata_reports': {},
            'analysis_reports': {},
            'experiment_reports': {}
        }

        has_samples = any(k in self.supported_sample_types for k in data.keys())
        has_analyses = any(k in self.supported_analysis_types for k in data.keys())
        has_experiments = any(k in self.supported_experiment_types for k in data.keys())

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

        if has_experiments:
            print("Experiment types in data:", [k for k in data.keys() if k in self.supported_experiment_types])
            for exp_type, experiments in data.items():
                if exp_type in self.supported_experiment_types:
                    if not experiments:
                        print(f"No experiments found for type '{exp_type}'. Skipping.")
                        continue

                    print(f"Validating {len(experiments)} {exp_type} experiments...")

                    validator = self.experiment_validators[exp_type]

                    results = validator.validate_records(
                        experiments,
                        validate_relationships=validate_relationships,
                        all_experiments=data
                    )

                    all_results['experiment_types_processed'].append(exp_type)
                    all_results['experiment_results'][exp_type] = results

                    report = validator.generate_validation_report(results)
                    all_results['experiment_reports'][exp_type] = report

                    summary = results['summary']
                    all_results['experiment_summary']['total_experiments'] += summary['total']
                    all_results['experiment_summary']['valid_experiments'] += summary['valid']
                    all_results['experiment_summary']['invalid_experiments'] += summary['invalid']
                    all_results['experiment_summary']['warnings'] += summary['warnings']
                    all_results['experiment_summary']['relationship_errors'] += summary.get('relationship_errors', 0)
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

        # analysis reports
        if validation_results['analysis_types_processed']:
            for analysis_type in validation_results['analysis_types_processed']:
                report_lines.append(f"\n{validation_results['analysis_reports'][analysis_type]}")
                report_lines.append("\n" + "-" * 60)

        # experiment reports
        if validation_results['experiment_types_processed']:
            for exp_type in validation_results['experiment_types_processed']:
                report_lines.append(f"\n{validation_results['experiment_reports'][exp_type]}")
                report_lines.append("\n" + "-" * 60)

        return "\n".join(report_lines)

    def get_supported_types(self) -> Dict[str, List[str]]:
        return {
            'sample_types': list(self.supported_sample_types),
            'metadata_types': list(self.supported_metadata_types),
            'analysis_types': list(self.supported_analysis_types),
            'analysis_metadata_types': list(self.supported_analysis_metadata_types),
            'experiment_types': list(self.supported_experiment_types)
        }


