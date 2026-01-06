from typing import List, Dict, Any, Type
from pydantic import ValidationError
from app.rulesets_pydantics.sample.submission_ruleset import FAANGSubmission
from app.rulesets_pydantics.sample.person_ruleset import FAANGPerson
from app.rulesets_pydantics.sample.organization_ruleset import FAANGOrganization


class SubmissionValidator:

    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid': [],
                'invalid': [],
                'error': "Error: data for 'submission' sheet was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid': [],
            'invalid': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            try:
                model = FAANGSubmission(**record)
                results['valid'].append({
                    'index': i,
                    'model': model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid'].append({
                    'index': i,
                    'data': record,
                    'errors': {
                        'field_errors': {err['loc'][0]: err['msg'] for err in e.errors()},
                        'errors': [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
                    }
                })
                results['summary']['invalid'] += 1

        return results

    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        report = []
        report.append("FAANG Submission Validation Report")
        report.append("=" * 40)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal submissions processed: {validation_results['summary']['total']}")
        report.append(f"Valid submissions: {validation_results['summary']['valid']}")
        report.append(f"Invalid submissions: {validation_results['summary']['invalid']}")

        if validation_results['invalid']:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results['invalid']:
                report.append(f"\nSubmission (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)


class PersonValidator:
    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid': [],
                'invalid': [],
                'error': "Error: data for 'person' sheet was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid': [],
            'invalid': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            try:
                model = FAANGPerson(**record)
                results['valid'].append({
                    'index': i,
                    'model': model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid'].append({
                    'index': i,
                    'data': record,
                    'errors': {
                        'field_errors': {err['loc'][0]: err['msg'] for err in e.errors()},
                        'errors': [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
                    }
                })
                results['summary']['invalid'] += 1

        return results

    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        report = []
        report.append("FAANG Person Validation Report")
        report.append("=" * 40)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal persons processed: {validation_results['summary']['total']}")
        report.append(f"Valid persons: {validation_results['summary']['valid']}")
        report.append(f"Invalid persons: {validation_results['summary']['invalid']}")

        if validation_results['invalid']:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results['invalid']:
                report.append(f"\nPerson (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)


class OrganizationValidator:
    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid': [],
                'invalid': [],
                'error': "Error: data for 'organization' sheet was not provided",
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0
                }
            }

        results = {
            'valid': [],
            'invalid': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0
            }
        }

        for i, record in enumerate(records):
            try:
                model = FAANGOrganization(**record)
                results['valid'].append({
                    'index': i,
                    'model': model,
                    'data': record
                })
                results['summary']['valid'] += 1
            except ValidationError as e:
                results['invalid'].append({
                    'index': i,
                    'data': record,
                    'errors': {
                        'field_errors': {err['loc'][0]: err['msg'] for err in e.errors()},
                        'errors': [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
                    }
                })
                results['summary']['invalid'] += 1

        return results

    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        report = []
        report.append("FAANG Organization Validation Report")
        report.append("=" * 40)

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal organizations processed: {validation_results['summary']['total']}")
        report.append(f"Valid organizations: {validation_results['summary']['valid']}")
        report.append(f"Invalid organizations: {validation_results['summary']['invalid']}")

        if validation_results['invalid']:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results['invalid']:
                report.append(f"\nOrganization (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)