from typing import List, Dict, Any, Tuple, Optional, Type
from pydantic import ValidationError, BaseModel
from abc import ABC, abstractmethod
from app.rulesets_pydantics.analysis.ena_analyses_ruleset import ENAAnalysis
from app.rulesets_pydantics.analysis.eva_analyses_ruleset import EVAAnalysis
from app.rulesets_pydantics.analysis.faang_analyses_ruleset import FAANGAnalysis


class BaseAnalysisValidator(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def get_model_class(self) -> Type[BaseModel]:
        pass

    @abstractmethod
    def get_analysis_type_name(self) -> str:
        pass

    def get_recommended_fields(self, model_class) -> List[str]:
        recommended_fields = []

        for field_name, field_info in model_class.model_fields.items():
            if (field_info.json_schema_extra and
                isinstance(field_info.json_schema_extra, dict) and
                field_info.json_schema_extra.get("recommended", False)):
                recommended_fields.append(field_name)

        return recommended_fields

    def validate_single_record(
        self,
        data: Dict[str, Any],
    ) -> Tuple[Optional[Any], Dict[str, List[str]]]:
        errors_dict = {
            'errors': [],
            'warnings': [],
            'field_errors': {},
            'field_warnings': {}
        }

        model_class = self.get_model_class()

        # pydantic validation
        try:
            model_instance = model_class(**data)

        except ValidationError as e:
            for error in e.errors():
                field_path = '.'.join(str(x) for x in error['loc'])
                error_msg = error['msg']

                if field_path not in errors_dict['field_errors']:
                    errors_dict['field_errors'][field_path] = []
                errors_dict['field_errors'][field_path].append(error_msg)
                errors_dict['errors'].append(f"{field_path}: {error_msg}")

            return None, errors_dict
        except Exception as e:
            errors_dict['errors'].append(str(e))
            return None, errors_dict

        # Check recommended fields
        recommended_fields = self.get_recommended_fields(model_class)
        for field in recommended_fields:
            if getattr(model_instance, field, None) is None:
                field_info = model_class.model_fields.get(field)
                field_display_name = field_info.alias if field_info and field_info.alias else field

                if field_display_name not in errors_dict['field_warnings']:
                    errors_dict['field_warnings'][field_display_name] = []
                errors_dict['field_warnings'][field_display_name].append(
                    "is recommended but was not provided"
                )

        return model_instance, errors_dict

    def validate_records(
        self,
        records: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        analysis_type = self.get_analysis_type_name()

        results = {
            'valid': [],
            'invalid': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0,
                'warnings': 0
            }
        }

        for i, record in enumerate(records):
            # Try to get alias for identification
            alias = record.get('Alias', f'{analysis_type}_{i}')

            model, errors = self.validate_single_record(record)

            if model and not errors['errors']:
                valid_entry = {
                    'index': i,
                    'alias': alias,
                    'model': model,
                    'data': record,
                    'warnings': errors['warnings'],
                    'field_warnings': errors['field_warnings']
                }

                results['valid'].append(valid_entry)
                results['summary']['valid'] += 1

                if errors['warnings'] or errors['field_warnings']:
                    results['summary']['warnings'] += 1
            else:
                results['invalid'].append({
                    'index': i,
                    'alias': alias,
                    'data': record,
                    'errors': errors
                })
                results['summary']['invalid'] += 1

        return results

    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        analysis_type = self.get_analysis_type_name()
        analysis_type_title = analysis_type.upper()

        report = []
        report.append(f"FAANG {analysis_type_title} Analysis Validation Report")
        report.append("=" * (len(f"FAANG {analysis_type_title} Analysis Validation Report")))
        report.append(f"\nTotal {analysis_type} analyses processed: {validation_results['summary']['total']}")
        report.append(f"Valid {analysis_type} analyses: {validation_results['summary']['valid']}")
        report.append(f"Invalid {analysis_type} analyses: {validation_results['summary']['invalid']}")
        report.append(f"{analysis_type_title} analyses with warnings: {validation_results['summary']['warnings']}")

        # Validation errors
        if validation_results['invalid']:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for item in validation_results['invalid']:
                report.append(f"\nAnalysis: {item['alias']} (index: {item['index']})")

                # Field errors from Pydantic validation
                for field, field_errors in item['errors'].get('field_errors', {}).items():
                    for error in field_errors:
                        report.append(f"  ERROR in {field}: {error}")

                # General errors
                for error in item['errors'].get('errors', []):
                    if not any(error.startswith(field) for field in item['errors'].get('field_errors', {})):
                        report.append(f"  ERROR: {error}")

                # Field warnings for invalid records
                for field, field_warnings in item['errors'].get('field_warnings', {}).items():
                    for warning in field_warnings:
                        report.append(f"  WARNING in {field}: {warning}")

        # Warnings for valid records
        if validation_results['valid']:
            warnings_found = False
            for item in validation_results['valid']:
                if item.get('warnings') or item.get('field_warnings'):
                    if not warnings_found:
                        report.append("\n\nWarnings and Non-Critical Issues:")
                        report.append("-" * 30)
                        warnings_found = True

                    report.append(f"\nAnalysis: {item['alias']} (index: {item['index']})")

                    # Show field warnings with field names
                    for field, field_warnings in item.get('field_warnings', {}).items():
                        for warning in field_warnings:
                            report.append(f"  WARNING in {field}: {warning}")

                    # Keep general warnings if any
                    for warning in item.get('warnings', []):
                        report.append(f"  WARNING: {warning}")

        return "\n".join(report)




class ENAAnalysisValidator(BaseAnalysisValidator):
    def get_model_class(self) -> Type[BaseModel]:
        return ENAAnalysis

    def get_analysis_type_name(self) -> str:
        return "ena"


class EVAAnalysisValidator(BaseAnalysisValidator):
    def get_model_class(self) -> Type[BaseModel]:
        return EVAAnalysis

    def get_analysis_type_name(self) -> str:
        return "eva"


class FAANGAnalysisValidator(BaseAnalysisValidator):
    def get_model_class(self) -> Type[BaseModel]:
        return FAANGAnalysis

    def get_analysis_type_name(self) -> str:
        return "faang"



def get_validator(analysis_type: str) -> BaseAnalysisValidator:
    validators = {
        'ena': ENAAnalysisValidator(),
        'eva': EVAAnalysisValidator(),
        'faang': FAANGAnalysisValidator()
    }
    
    if analysis_type not in validators:
        raise ValueError(
            f"Unknown analysis type: {analysis_type}. "
            f"Must be one of: {', '.join(validators.keys())}"
        )
    
    return validators[analysis_type]


def get_all_validators() -> Dict[str, BaseAnalysisValidator]:
    return {
        'ena': ENAAnalysisValidator(),
        'eva': EVAAnalysisValidator(),
        'faang': FAANGAnalysisValidator()
    }


def get_supported_types() -> List[str]:
    return ['ena', 'eva', 'faang']

__all__ = [
    'BaseAnalysisValidator',
    'ENAAnalysisValidator',
    'EVAAnalysisValidator',
    'FAANGAnalysisValidator',
    'get_validator',
    'get_all_validators',
    'get_supported_types'
]
