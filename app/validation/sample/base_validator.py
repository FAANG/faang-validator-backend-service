from typing import List, Dict, Any, Tuple, Optional, Type
from pydantic import ValidationError, BaseModel
from abc import ABC, abstractmethod
from contextvars import ContextVar

# context variable to store ontology warnings during validation
ontology_warnings_context: ContextVar[List[str]] = ContextVar('ontology_warnings', default=[])


class BaseValidator(ABC):
    def __init__(self, ontology_validator=None, relationship_validator=None):
        # Accept shared validators or create new ones
        self.ontology_validator = ontology_validator
        self.relationship_validator = relationship_validator

        # Only initialize if not provided
        if self.ontology_validator is None or self.relationship_validator is None:
            self._initialize_validators()

    @abstractmethod
    def _initialize_validators(self):
        pass

    @abstractmethod
    def get_model_class(self) -> Type[BaseModel]:
        pass

    @abstractmethod
    def get_sample_type_name(self) -> str:
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
            'ontology_warnings': [],
            'field_errors': {},
            'field_warnings': {}
        }

        model_class = self.get_model_class()

        # initialize context for validation
        ontology_warnings_context.set([])
        
        # Set the shared ontology validator in context so Pydantic validators can use it
        if self.ontology_validator:
            from app.validation.sample.generic_validator_classes import ontology_validator_context
            ontology_validator_context.set(self.ontology_validator)

        # pydantic validation
        try:
            model_instance = model_class(**data)

            # collect ontology warnings from context
            ontology_warnings = ontology_warnings_context.get()
            if ontology_warnings:
                errors_dict['ontology_warnings'].extend(ontology_warnings)

        except ValidationError as e:
            # collect ontology warnings even if validation failed
            ontology_warnings = ontology_warnings_context.get()
            if ontology_warnings:
                errors_dict['ontology_warnings'].extend(ontology_warnings)

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
        finally:
            ontology_warnings_context.set([])
            # Clear the ontology validator from context
            try:
                from app.validation.sample.generic_validator_classes import ontology_validator_context
                ontology_validator_context.set(None)
            except:
                pass

        # recommended fields
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
        sheet_records: List[Dict[str, Any]],
        validate_relationships: bool = True,
        all_samples: Dict[str, List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        sample_type = self.get_sample_type_name()

        results = {
            f'valid_{sample_type}s': [],
            f'invalid_{sample_type}s': [],
            'summary': {
                'total': len(sheet_records),
                'valid': 0,
                'invalid': 0,
                'warnings': 0,
                'relationship_errors': 0
            }
        }

        for i, record in enumerate(sheet_records):
            sample_name = record.get('Sample Name', f'{sample_type}_{i}')

            model, errors = self.validate_single_record(record)

            if model and not errors['errors']:
                valid_entry = {
                    'index': i,
                    'sample_name': sample_name,
                    'model': model,
                    'data': record,
                    'warnings': errors['warnings'],
                    'field_warnings': errors['field_warnings'],
                    'relationship_errors': []
                }

                # add ontology warnings if any
                if errors['ontology_warnings']:
                    valid_entry['ontology_warnings'] = errors['ontology_warnings']

                results[f'valid_{sample_type}s'].append(valid_entry)
                results['summary']['valid'] += 1

                if errors['warnings'] or errors['ontology_warnings'] or errors['field_warnings']:
                    results['summary']['warnings'] += 1
            else:
                results[f'invalid_{sample_type}s'].append({
                    'index': i,
                    'sample_name': sample_name,
                    'data': record,
                    'errors': errors
                })
                results['summary']['invalid'] += 1

        # Add relationship validation if enabled
        if validate_relationships and all_samples:
            self._add_relationship_errors(results, all_samples)

        return results

    def _add_relationship_errors(self, results: Dict[str, Any], all_samples: Dict[str, List[Dict]]):
        sample_type = self.get_sample_type_name()
        relationship_errors = self._get_relationship_errors(all_samples)

        if not relationship_errors:
            return

        # Add to valid samples
        for sample in results[f'valid_{sample_type}s']:
            sample_name = sample['sample_name']
            if sample_name in relationship_errors:
                sample['relationship_errors'] = relationship_errors[sample_name]
                results['summary']['relationship_errors'] += 1

        # Add to invalid samples
        for sample in results[f'invalid_{sample_type}s']:
            sample_name = sample['sample_name']
            if sample_name in relationship_errors:
                if 'relationship_errors' not in sample['errors']:
                    sample['errors']['relationship_errors'] = []
                sample['errors']['relationship_errors'] = relationship_errors[sample_name]
                results['summary']['relationship_errors'] += 1

    def _get_relationship_errors(self, all_samples: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
        if not self.relationship_validator:
            return {}

        return self.relationship_validator.validate_derived_from_relationships(all_samples)

    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        sample_type = self.get_sample_type_name()
        sample_type_title = sample_type.title()

        report = []
        report.append(f"FAANG {sample_type_title} Validation Report")
        report.append("=" * (25 + len(sample_type_title)))
        report.append(f"\nTotal {sample_type}s processed: {validation_results['summary']['total']}")
        report.append(f"Valid {sample_type}s: {validation_results['summary']['valid']}")
        report.append(f"Invalid {sample_type}s: {validation_results['summary']['invalid']}")
        report.append(f"{sample_type_title}s with warnings: {validation_results['summary']['warnings']}")

        # validation errors
        if validation_results[f'invalid_{sample_type}s']:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for sample in validation_results[f'invalid_{sample_type}s']:
                report.append(f"\n{sample_type_title}: {sample['sample_name']} (index: {sample['index']})")

                # field errors from Pydantic validation
                for field, field_errors in sample['errors'].get('field_errors', {}).items():
                    for error in field_errors:
                        report.append(f"  ERROR in {field}: {error}")

                # general errors
                for error in sample['errors'].get('errors', []):
                    if not any(error.startswith(field) for field in sample['errors'].get('field_errors', {})):
                        report.append(f"  ERROR: {error}")

                # field warnings for invalid samples (NEW)
                for field, field_warnings in sample['errors'].get('field_warnings', {}).items():
                    for warning in field_warnings:
                        report.append(f"  WARNING in {field}: {warning}")

                # relationship errors for invalid samples
                if sample['errors'].get('relationship_errors'):
                    for error in sample['errors']['relationship_errors']:
                        report.append(f"  RELATIONSHIP ERROR: {error}")

                # show ontology warnings for invalid samples
                if sample['errors'].get('ontology_warnings'):
                    for warning in sample['errors']['ontology_warnings']:
                        report.append(f"  ONTOLOGY WARNING: {warning}")

        # warnings and relationship issues for valid samples
        if validation_results[f'valid_{sample_type}s']:
            warnings_found = False
            for sample in validation_results[f'valid_{sample_type}s']:
                if (sample.get('warnings') or sample.get('relationship_errors') or
                    sample.get('ontology_warnings') or sample.get('field_warnings')):
                    if not warnings_found:
                        report.append("\n\nWarnings and Non-Critical Issues:")
                        report.append("-" * 30)
                        warnings_found = True

                    report.append(f"\n{sample_type_title}: {sample['sample_name']} (index: {sample['index']})")

                    # Show field warnings with field names (CHANGED)
                    for field, field_warnings in sample.get('field_warnings', {}).items():
                        for warning in field_warnings:
                            report.append(f"  WARNING in {field}: {warning}")

                    # Keep general warnings if any
                    for warning in sample.get('warnings', []):
                        report.append(f"  WARNING: {warning}")

                    for error in sample.get('relationship_errors', []):
                        report.append(f"  RELATIONSHIP: {error}")

                    for warning in sample.get('ontology_warnings', []):
                        report.append(f"  ONTOLOGY: {warning}")

        return "\n".join(report)