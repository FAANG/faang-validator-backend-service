from typing import List, Dict, Any, Tuple, Optional, Type
from pydantic import ValidationError, BaseModel
from abc import ABC, abstractmethod
from contextvars import ContextVar

# Context variable to store ontology warnings during validation
# Reuse the same context variable from sample validation
ontology_warnings_context: ContextVar[List[str]] = ContextVar('ontology_warnings', default=[])


class BaseExperimentValidator(ABC):
    """
    Base class for all experiment validators.
    Provides common validation logic and structure.
    """
    
    def __init__(self, ontology_validator=None):
        """
        Initialize validator with optional shared ontology validator.
        
        Args:
            ontology_validator: Shared OntologyValidator instance (optional)
        """
        self.ontology_validator = ontology_validator
        
        # Initialize validators if not provided
        if self.ontology_validator is None:
            self._initialize_validators()
    
    @abstractmethod
    def _initialize_validators(self):
        """
        Initialize validators if not provided externally.
        Each subclass should implement this to create OntologyValidator if needed.
        """
        pass
    
    @abstractmethod
    def get_model_class(self) -> Type[BaseModel]:
        """
        Return the Pydantic model class for this experiment type.
        
        Returns:
            Type[BaseModel]: The Pydantic model class
        """
        pass
    
    @abstractmethod
    def get_experiment_type_name(self) -> str:
        """
        Return the experiment type name.
        
        Returns:
            str: Experiment type name (e.g., 'atac-seq', 'bs-seq')
        """
        pass
    
    def get_recommended_fields(self, model_class) -> List[str]:
        """
        Extract recommended fields from Pydantic model.
        
        Args:
            model_class: Pydantic model class
        
        Returns:
            List[str]: List of recommended field names
        """
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
        """
        Validate a single experiment record.
        
        Args:
            data: Dictionary containing experiment data
        
        Returns:
            Tuple of (validated_model, errors_dict)
            - validated_model: Pydantic model instance if valid, None otherwise
            - errors_dict: Dictionary with errors, warnings, and field-specific issues
        """
        errors_dict = {
            'errors': [],
            'warnings': [],
            'ontology_warnings': [],
            'field_errors': {},
            'field_warnings': {}
        }
        
        model_class = self.get_model_class()
        
        # Initialize context for validation
        ontology_warnings_context.set([])

        if self.ontology_validator:
            from validation.generic_validator_classes import ontology_validator_context
            ontology_validator_context.set(self.ontology_validator)
        
        # Pydantic validation
        try:
            model_instance = model_class(**data)
            
            # Collect ontology warnings from context
            ontology_warnings = ontology_warnings_context.get()
            if ontology_warnings:
                errors_dict['ontology_warnings'].extend(ontology_warnings)
        
        except ValidationError as e:
            # Collect ontology warnings even if validation failed
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
                from validation.generic_validator_classes import ontology_validator_context
                ontology_validator_context.set(None)
            except:
                pass
        
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
        validate_relationships: bool = True,
        all_experiments: Dict[str, List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validate multiple experiment records.
        
        Args:
            records: List of experiment records to validate
            validate_relationships: Whether to validate cross-experiment relationships
            all_experiments: Dict of all experiments (for relationship validation)
            **kwargs: Additional arguments for subclass-specific validation
        
        Returns:
            Dict containing validation results
        """
        experiment_type = self.get_experiment_type_name()
        
        results = {
            'valid': [],
            'invalid': [],
            'summary': {
                'total': len(records),
                'valid': 0,
                'invalid': 0,
                'warnings': 0,
                'relationship_errors': 0
            }
        }
        
        for i, record in enumerate(records):
            # Use sample_descriptor or experiment_alias as identifier
            identifier = record.get('Sample Descriptor', 
                                   record.get('Experiment Alias', f'{experiment_type}_{i}'))
            
            model, errors = self.validate_single_record(record)
            
            if model and not errors['errors']:
                valid_entry = {
                    'index': i,
                    'identifier': identifier,
                    'model': model,
                    'data': record,
                    'warnings': errors['warnings'],
                    'field_warnings': errors['field_warnings'],
                    'relationship_errors': []
                }
                
                # Add ontology warnings if any
                if errors['ontology_warnings']:
                    valid_entry['ontology_warnings'] = errors['ontology_warnings']
                
                results['valid'].append(valid_entry)
                results['summary']['valid'] += 1
                
                if errors['warnings'] or errors['ontology_warnings'] or errors['field_warnings']:
                    results['summary']['warnings'] += 1
            else:
                results['invalid'].append({
                    'index': i,
                    'identifier': identifier,
                    'data': record,
                    'errors': errors
                })
                results['summary']['invalid'] += 1
        
        # Add relationship validation if enabled
        if validate_relationships and all_experiments:
            self._add_relationship_errors(results, all_experiments)
        
        return results
    
    def _add_relationship_errors(self, results: Dict[str, Any], all_experiments: Dict[str, List[Dict]]):
        """
        Add experiment-specific relationship validation.
        
        Args:
            results: Current validation results
            all_experiments: Dict of all experiments for cross-validation
        """
        relationship_errors = self._get_relationship_errors(all_experiments)
        
        if not relationship_errors:
            return
        
        # Add to valid experiments
        for exp in results['valid']:
            identifier = exp['identifier']
            if identifier in relationship_errors:
                exp['relationship_errors'] = relationship_errors[identifier]
                results['summary']['relationship_errors'] += 1
        
        # Add to invalid experiments
        for exp in results['invalid']:
            identifier = exp['identifier']
            if identifier in relationship_errors:
                if 'relationship_errors' not in exp['errors']:
                    exp['errors']['relationship_errors'] = []
                exp['errors']['relationship_errors'] = relationship_errors[identifier]
                results['summary']['relationship_errors'] += 1
    
    def _get_relationship_errors(self, all_experiments: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
        """
        Validate experiment-specific relationships.
        Override this method in subclasses for custom relationship validation.
        
        Args:
            all_experiments: Dict of all experiments
        
        Returns:
            Dict mapping experiment identifiers to lists of relationship errors
        """
        # Default implementation: no relationship validation
        return {}
    
    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        """
        Generate a human-readable validation report.
        
        Args:
            validation_results: Validation results from validate_records()
        
        Returns:
            str: Formatted validation report
        """
        experiment_type = self.get_experiment_type_name()
        experiment_type_title = experiment_type.upper()
        
        report = []
        report.append(f"FAANG {experiment_type_title} Experiment Validation Report")
        report.append("=" * (len(f"FAANG {experiment_type_title} Experiment Validation Report")))
        report.append(f"\nTotal experiments processed: {validation_results['summary']['total']}")
        report.append(f"Valid experiments: {validation_results['summary']['valid']}")
        report.append(f"Invalid experiments: {validation_results['summary']['invalid']}")
        report.append(f"Experiments with warnings: {validation_results['summary']['warnings']}")
        
        if validation_results['summary']['relationship_errors'] > 0:
            report.append(f"Experiments with relationship errors: {validation_results['summary']['relationship_errors']}")
        
        # Validation errors
        if validation_results['invalid']:
            report.append("\n\nValidation Errors:")
            report.append("-" * 20)
            for exp in validation_results['invalid']:
                report.append(f"\nExperiment: {exp['identifier']} (index: {exp['index']})")
                
                # Field errors from Pydantic validation
                for field, field_errors in exp['errors'].get('field_errors', {}).items():
                    for error in field_errors:
                        report.append(f"  ERROR in {field}: {error}")
                
                # General errors
                for error in exp['errors'].get('errors', []):
                    if not any(error.startswith(field) for field in exp['errors'].get('field_errors', {})):
                        report.append(f"  ERROR: {error}")
                
                # Field warnings for invalid experiments
                for field, field_warnings in exp['errors'].get('field_warnings', {}).items():
                    for warning in field_warnings:
                        report.append(f"  WARNING in {field}: {warning}")
                
                # Relationship errors
                if exp['errors'].get('relationship_errors'):
                    for error in exp['errors']['relationship_errors']:
                        report.append(f"  RELATIONSHIP ERROR: {error}")
                
                # Ontology warnings
                if exp['errors'].get('ontology_warnings'):
                    for warning in exp['errors']['ontology_warnings']:
                        report.append(f"  ONTOLOGY WARNING: {warning}")
        
        # Warnings for valid experiments
        if validation_results['valid']:
            warnings_found = False
            for exp in validation_results['valid']:
                if (exp.get('warnings') or exp.get('relationship_errors') or
                    exp.get('ontology_warnings') or exp.get('field_warnings')):
                    if not warnings_found:
                        report.append("\n\nWarnings and Non-Critical Issues:")
                        report.append("-" * 30)
                        warnings_found = True
                    
                    report.append(f"\nExperiment: {exp['identifier']} (index: {exp['index']})")
                    
                    # Field warnings
                    for field, field_warnings in exp.get('field_warnings', {}).items():
                        for warning in field_warnings:
                            report.append(f"  WARNING in {field}: {warning}")
                    
                    # General warnings
                    for warning in exp.get('warnings', []):
                        report.append(f"  WARNING: {warning}")
                    
                    # Relationship errors
                    for error in exp.get('relationship_errors', []):
                        report.append(f"  RELATIONSHIP: {error}")
                    
                    # Ontology warnings
                    for warning in exp.get('ontology_warnings', []):
                        report.append(f"  ONTOLOGY: {warning}")
        
        return "\n".join(report)
