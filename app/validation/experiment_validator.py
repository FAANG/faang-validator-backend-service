from typing import List, Dict, Any
from pydantic import ValidationError
from app.rulesets_pydantics.chip_seq_input_dna_ruleset import FAANGChipSeqInputDNA
from app.rulesets_pydantics.chip_seq_dna_binding_proteins_ruleset import FAANGChipSeqDNABindingProteins
from app.rulesets_pydantics.rna_seq_ruleset import FAANGRNASeq


class ChipSeqInputDNAValidator:
    """Validator for ChIP-seq input DNA experiments."""

    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid_chip-seq_input_dnas': [],
                'invalid_chip-seq_input_dnas': [],
                'error': "Error: data for 'chip-seq input dna' experiment was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid_chip-seq_input_dnas': [],
            'invalid_chip-seq_input_dnas': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            sample_name = record.get('Experiment Alias') or record.get('experiment_alias') or record.get('Sample Name') or f'chip-seq_input_dna_{i}'
            try:
                model = FAANGChipSeqInputDNA(**record)
                results['valid_chip-seq_input_dnas'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'model_dict': model.model_dump() if hasattr(model, 'model_dump') else model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid_chip-seq_input_dnas'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'data': record,
                    'errors': {
                        'field_errors': {'.'.join(str(x) for x in err['loc']): err['msg'] for err in e.errors()},
                        'errors': [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
                    }
                })
                results['summary']['invalid'] += 1

        return results

    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        report = []
        report.append("FAANG ChIP-seq Input DNA Experiment Validation Report")
        report.append("=" * 50)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal experiments processed: {validation_results['summary']['total']}")
        report.append(f"Valid experiments: {validation_results['summary']['valid']}")
        report.append(f"Invalid experiments: {validation_results['summary']['invalid']}")

        invalid_key = 'invalid_chip-seq_input_dnas'
        if invalid_key in validation_results and validation_results[invalid_key]:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results[invalid_key]:
                report.append(f"\nExperiment (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)


class ChipSeqDNABindingProteinsValidator:
    """Validator for ChIP-seq DNA-binding proteins experiments."""

    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid_chip-seq_dna-binding_proteins': [],
                'invalid_chip-seq_dna-binding_proteins': [],
                'error': "Error: data for 'chip-seq dna-binding proteins' experiment was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid_chip-seq_dna-binding_proteins': [],
            'invalid_chip-seq_dna-binding_proteins': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            sample_name = record.get('Experiment Alias') or record.get('experiment_alias') or record.get('Sample Name') or f'chip-seq_dna-binding_proteins_{i}'
            try:
                model = FAANGChipSeqDNABindingProteins(**record)
                results['valid_chip-seq_dna-binding_proteins'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'model_dict': model.model_dump() if hasattr(model, 'model_dump') else model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid_chip-seq_dna-binding_proteins'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'data': record,
                    'errors': {
                        'field_errors': {'.'.join(str(x) for x in err['loc']): err['msg'] for err in e.errors()},
                        'errors': [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
                    }
                })
                results['summary']['invalid'] += 1

        return results

    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        report = []
        report.append("FAANG ChIP-seq DNA-binding Proteins Experiment Validation Report")
        report.append("=" * 60)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal experiments processed: {validation_results['summary']['total']}")
        report.append(f"Valid experiments: {validation_results['summary']['valid']}")
        report.append(f"Invalid experiments: {validation_results['summary']['invalid']}")

        invalid_key = 'invalid_chip-seq_dna-binding_proteins'
        if invalid_key in validation_results and validation_results[invalid_key]:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results[invalid_key]:
                report.append(f"\nExperiment (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)


class RNASeqValidator:
    """Validator for RNA-seq experiments."""

    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid_rna-seqs': [],
                'invalid_rna-seqs': [],
                'error': "Error: data for 'rna-seq' experiment was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid_rna-seqs': [],
            'invalid_rna-seqs': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            # Get experiment alias or name for display
            sample_name = record.get('Experiment Alias') or record.get('experiment_alias') or record.get('Sample Name') or f'rna-seq_{i}'
            try:
                model = FAANGRNASeq(**record)
                results['valid_rna-seqs'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'model_dict': model.model_dump() if hasattr(model, 'model_dump') else model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid_rna-seqs'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'data': record,
                    'errors': {
                        'field_errors': {'.'.join(str(x) for x in err['loc']): err['msg'] for err in e.errors()},
                        'errors': [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
                    }
                })
                results['summary']['invalid'] += 1

        return results

    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        report = []
        report.append("FAANG RNA-seq Experiment Validation Report")
        report.append("=" * 45)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal experiments processed: {validation_results['summary']['total']}")
        report.append(f"Valid experiments: {validation_results['summary']['valid']}")
        report.append(f"Invalid experiments: {validation_results['summary']['invalid']}")

        invalid_key = 'invalid_rna-seqs'
        if invalid_key in validation_results and validation_results[invalid_key]:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results[invalid_key]:
                report.append(f"\nExperiment (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)

