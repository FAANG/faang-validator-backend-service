from typing import List, Dict, Any
from pydantic import ValidationError
from app.rulesets_pydantics.analysis.eva_analyses_ruleset import FAANGEVAAnalysis
from app.rulesets_pydantics.analysis.faang_analyses_ruleset import FAANGFAANGAnalysis
from app.rulesets_pydantics.analysis.ena_analyses_ruleset import FAANGENAAnalysis


class EVAAnalysisValidator:
    """Validator for EVA (European Variation Archive) analyses."""

    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid_evas': [],
                'invalid_evas': [],
                'error': "Error: data for 'eva' analysis was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid_evas': [],
            'invalid_evas': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            sample_name = record.get('Analysis Alias') or record.get('analysis_alias') or record.get('Sample Name') or f'eva_{i}'
            try:
                model = FAANGEVAAnalysis(**record)
                results['valid_evas'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'model_dict': model.model_dump() if hasattr(model, 'model_dump') else model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid_evas'].append({
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
        report.append("FAANG EVA Analysis Validation Report")
        report.append("=" * 40)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal analyses processed: {validation_results['summary']['total']}")
        report.append(f"Valid analyses: {validation_results['summary']['valid']}")
        report.append(f"Invalid analyses: {validation_results['summary']['invalid']}")

        invalid_key = 'invalid_evas'
        if invalid_key in validation_results and validation_results[invalid_key]:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results[invalid_key]:
                report.append(f"\nAnalysis (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)


class FAANGAnalysisValidator:
    """Validator for FAANG analyses."""

    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid_faangs': [],
                'invalid_faangs': [],
                'error': "Error: data for 'faang' analysis was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid_faangs': [],
            'invalid_faangs': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            sample_name = record.get('Analysis Alias') or record.get('analysis_alias') or record.get('Sample Name') or f'faang_{i}'
            try:
                model = FAANGFAANGAnalysis(**record)
                results['valid_faangs'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'model_dict': model.model_dump() if hasattr(model, 'model_dump') else model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid_faangs'].append({
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
        report.append("FAANG Analysis Validation Report")
        report.append("=" * 40)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal analyses processed: {validation_results['summary']['total']}")
        report.append(f"Valid analyses: {validation_results['summary']['valid']}")
        report.append(f"Invalid analyses: {validation_results['summary']['invalid']}")

        invalid_key = 'invalid_faangs'
        if invalid_key in validation_results and validation_results[invalid_key]:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results[invalid_key]:
                report.append(f"\nAnalysis (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)


class ENAAnalysisValidator:
    """Validator for ENA (European Nucleotide Archive) analyses."""

    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid_enas': [],
                'invalid_enas': [],
                'error': "Error: data for 'ena' analysis was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid_enas': [],
            'invalid_enas': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            sample_name = record.get('Analysis Alias') or record.get('analysis_alias') or record.get('alias') or record.get('Sample Name') or f'ena_{i}'
            try:
                model = FAANGENAAnalysis(**record)
                results['valid_enas'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'model_dict': model.model_dump() if hasattr(model, 'model_dump') else model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid_enas'].append({
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
        report.append("FAANG ENA Analysis Validation Report")
        report.append("=" * 40)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal analyses processed: {validation_results['summary']['total']}")
        report.append(f"Valid analyses: {validation_results['summary']['valid']}")
        report.append(f"Invalid analyses: {validation_results['summary']['invalid']}")

        invalid_key = 'invalid_enas'
        if invalid_key in validation_results and validation_results[invalid_key]:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results[invalid_key]:
                report.append(f"\nAnalysis (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)

