from typing import List, Dict, Any, Type
from pydantic import ValidationError, BaseModel
from app.rulesets_pydantics.sample.submission_ruleset import FAANGSubmission
from app.rulesets_pydantics.sample.person_ruleset import FAANGPerson
from app.rulesets_pydantics.sample.organization_ruleset import FAANGOrganization
from app.rulesets_pydantics.analysis.submission_ruleset import AnalysisSubmission


class BaseMetadataValidator:
    def __init__(self, model_class: Type[BaseModel], type_name: str, type_name_title: str, type_name_plural: str):
        self.model_class = model_class
        self.type_name = type_name
        self.type_name_title = type_name_title
        self.type_name_plural = type_name_plural

    def validate_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records or len(records) == 0:
            return {
                'valid': [],
                'invalid': [],
                'error': f"Error: data for '{self.type_name}' sheet was not provided",
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
                model = self.model_class(**record)
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
        report.append(f"FAANG {self.type_name_title} Validation Report")
        report.append("=" * (len(f"FAANG {self.type_name_title} Validation Report")))

        if 'error' in validation_results:
            report.append(f"\nERROR: {validation_results['error']}")
            return "\n".join(report)

        report.append(f"\nTotal {self.type_name_plural} processed: {validation_results['summary']['total']}")
        report.append(f"Valid {self.type_name_plural}: {validation_results['summary']['valid']}")
        report.append(f"Invalid {self.type_name_plural}: {validation_results['summary']['invalid']}")

        if validation_results['invalid']:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results['invalid']:
                report.append(f"\n{self.type_name_title} (index: {item['index']})")
                for error in item['errors']['errors']:
                    report.append(f"  ERROR: {error}")

        return "\n".join(report)


class SubmissionValidator(BaseMetadataValidator):
    def __init__(self):
        super().__init__(FAANGSubmission, 'submission', 'Submission', 'submissions')


class PersonValidator(BaseMetadataValidator):
    def __init__(self):
        super().__init__(FAANGPerson, 'person', 'Person', 'persons')


class OrganizationValidator(BaseMetadataValidator):
    def __init__(self):
        super().__init__(FAANGOrganization, 'organization', 'Organization', 'organizations')


class AnalysisSubmissionValidator(BaseMetadataValidator):
    def __init__(self):
        super().__init__(AnalysisSubmission, 'submission', 'Submission', 'submissions')