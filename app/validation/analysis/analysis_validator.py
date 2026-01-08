from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from app.rulesets_pydantics.analysis.ena_analyses_ruleset import ENAAnalysis
from app.rulesets_pydantics.analysis.eva_analyses_ruleset import EVAAnalysis
from app.rulesets_pydantics.analysis.faang_analyses_ruleset import FAANGAnalysis


class BaseAnalysisValidator:
    """Base class for analysis validators with common validation logic."""
    
    def __init__(self, model_class):
        self.model_class = model_class
        self.validation_errors = []
        self.validation_warnings = []
    
    def validate_record(self, record_data: Dict[str, Any], record_index: int) -> Dict[str, Any]:
        """
        Validate a single analysis record.
        
        Args:
            record_data: Dictionary containing the analysis data
            record_index: Index of the record in the dataset
            
        Returns:
            Dictionary with validation results including model, errors, and warnings
        """
        result = {
            'record_index': record_index,
            'valid': False,
            'model': None,
            'errors': [],
            'warnings': [],
            'data': record_data
        }
        
        try:
            # Validate using Pydantic model
            model = self.model_class(**record_data)
            result['model'] = model
            result['valid'] = True
            
            # Run additional checks
            additional_warnings = self._additional_checks(model, record_data)
            if additional_warnings:
                result['warnings'].extend(additional_warnings)
                
        except ValidationError as e:
            # Convert Pydantic validation errors to readable format
            for error in e.errors():
                loc = ' -> '.join(str(l) for l in error['loc'])
                msg = error['msg']
                error_type = error['type']
                result['errors'].append(f"{loc}: {msg} (type: {error_type})")
        except Exception as e:
            result['errors'].append(f"Unexpected error during validation: {str(e)}")
        
        return result
    
    def _additional_checks(self, model, record_data: Dict[str, Any]) -> List[str]:
        """
        Perform additional validation checks beyond Pydantic schema validation.
        Override in subclasses for specific checks.
        
        Args:
            model: Validated Pydantic model
            record_data: Original record data
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check for recommended fields
        recommended_warnings = self._check_recommended_fields(model)
        if recommended_warnings:
            warnings.extend(recommended_warnings)
        
        return warnings
    
    def _check_recommended_fields(self, model) -> List[str]:
        """
        Check if recommended fields are present and not None.
        
        Args:
            model: Validated Pydantic model
            
        Returns:
            List of warning messages for missing recommended fields
        """
        warnings = []
        
        # Get all fields marked as recommended
        for field_name, field_info in model.model_fields.items():
            # Check if field is marked as recommended in json_schema_extra
            if (hasattr(field_info, 'json_schema_extra') and 
                field_info.json_schema_extra and 
                field_info.json_schema_extra.get('recommended')):
                
                value = getattr(model, field_name, None)
                if value is None or (isinstance(value, str) and value.strip() == ''):
                    # Get the field alias if it exists, otherwise use field name
                    display_name = field_info.alias if hasattr(field_info, 'alias') and field_info.alias else field_name
                    warnings.append(f"Recommended field '{display_name}' is missing or empty")
        
        return warnings
    
    def validate_batch(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a batch of analysis records.
        
        Args:
            records: List of dictionaries containing analysis data
            
        Returns:
            Dictionary with validation summary and results
        """
        results = {
            'valid': [],
            'invalid': [],
            'total_count': len(records),
            'valid_count': 0,
            'invalid_count': 0,
            'warnings_count': 0
        }
        
        for idx, record in enumerate(records):
            validation_result = self.validate_record(record, idx)
            
            if validation_result['valid']:
                results['valid'].append(validation_result)
                results['valid_count'] += 1
                if validation_result['warnings']:
                    results['warnings_count'] += 1
            else:
                results['invalid'].append(validation_result)
                results['invalid_count'] += 1
        
        return results


class ENAAnalysisValidator(BaseAnalysisValidator):
    """Validator for ENA analyses."""
    
    def __init__(self):
        super().__init__(ENAAnalysis)
    
    def _additional_checks(self, model: ENAAnalysis, record_data: Dict[str, Any]) -> List[str]:
        """
        Perform ENA-specific additional validation checks.
        
        Args:
            model: Validated ENA analysis model
            record_data: Original record data
            
        Returns:
            List of warning messages
        """
        warnings = super()._additional_checks(model, record_data)
        
        # Check that file arrays have consistent lengths (this is also in the model validator)
        # But we can add warnings here if needed
        
        # Check for date consistency if both date and unit are provided
        if model.analysis_date and model.analysis_date_unit:
            date_warning = self._validate_date_format(
                model.analysis_date, 
                model.analysis_date_unit
            )
            if date_warning:
                warnings.append(date_warning)
        
        return warnings
    
    def _validate_date_format(self, date_value: str, unit: str) -> Optional[str]:
        """
        Validate date format matches the specified unit.
        
        Args:
            date_value: Date string
            unit: Expected date format unit
            
        Returns:
            Warning message if date doesn't match format, None otherwise
        """
        import re
        
        patterns = {
            "YYYY-MM-DD": r'^[12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$',
            "YYYY-MM": r'^[12]\d{3}-(0[1-9]|1[0-2])$',
            "YYYY": r'^[12]\d{3}$'
        }
        
        if unit in patterns:
            if not re.match(patterns[unit], date_value):
                return f"Analysis date '{date_value}' does not match expected format '{unit}'"
        
        return None


class EVAAnalysisValidator(BaseAnalysisValidator):
    """Validator for EVA analyses (extends ENA)."""
    
    def __init__(self):
        super().__init__(EVAAnalysis)
    
    def _additional_checks(self, model: EVAAnalysis, record_data: Dict[str, Any]) -> List[str]:
        """
        Perform EVA-specific additional validation checks.
        
        Args:
            model: Validated EVA analysis model
            record_data: Original record data
            
        Returns:
            List of warning messages
        """
        warnings = super()._additional_checks(model, record_data)
        
        # EVA-specific checks can be added here
        # For example, checking consistency between experiment_type and platform
        
        return warnings


class FAANGAnalysisValidator(BaseAnalysisValidator):
    """Validator for FAANG analyses."""
    
    def __init__(self):
        super().__init__(FAANGAnalysis)
    
    def _additional_checks(self, model: FAANGAnalysis, record_data: Dict[str, Any]) -> List[str]:
        """
        Perform FAANG-specific additional validation checks.
        
        Args:
            model: Validated FAANG analysis model
            record_data: Original record data
            
        Returns:
            List of warning messages
        """
        warnings = super()._additional_checks(model, record_data)
        
        # FAANG-specific checks
        # Check URL fields are valid
        url_fields = ['analysis_protocol', 'analysis_code', 'nextflow_config_url', 'nextflow_spreadsheet_url']
        for field_name in url_fields:
            value = getattr(model, field_name, None)
            if value and value != "restricted access":
                if not self._is_valid_url(value):
                    warnings.append(f"Field '{field_name}' does not appear to be a valid URL: {value}")
        
        return warnings
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Check if a string is a valid URL.
        
        Args:
            url: URL string to validate
            
        Returns:
            True if valid URL, False otherwise
        """
        import re
        url_pattern = re.compile(
            r'^(https?|ftp)://'  # protocol
            r'([a-zA-Z0-9.-]+)'  # domain
            r'(:[0-9]+)?'  # optional port
            r'(/.*)?$'  # path
        )
        return bool(url_pattern.match(url))


# Helper function for easy validation
def validate_analyses(
    analyses_data: Dict[str, List[Dict[str, Any]]],
    analysis_type: str = None
) -> Dict[str, Any]:
    """
    Validate a collection of analyses.
    
    Args:
        analyses_data: Dictionary with analysis types as keys and lists of records as values
                      e.g., {'ena': [...], 'eva': [...], 'faang': [...]}
        analysis_type: Optional specific analysis type to validate. If None, validates all.
        
    Returns:
        Dictionary with validation results for each analysis type
    """
    validators = {
        'ena': ENAAnalysisValidator(),
        'eva': EVAAnalysisValidator(),
        'faang': FAANGAnalysisValidator()
    }
    
    results = {}
    
    for analysis_key, records in analyses_data.items():
        if analysis_type and analysis_key != analysis_type:
            continue
            
        if analysis_key in validators:
            validator = validators[analysis_key]
            results[analysis_key] = validator.validate_batch(records)
        else:
            results[analysis_key] = {
                'error': f"Unknown analysis type: {analysis_key}",
                'valid': [],
                'invalid': [],
                'total_count': len(records),
                'valid_count': 0,
                'invalid_count': len(records)
            }
    
    # Add summary
    total_valid = sum(r.get('valid_count', 0) for r in results.values())
    total_invalid = sum(r.get('invalid_count', 0) for r in results.values())
    total_warnings = sum(r.get('warnings_count', 0) for r in results.values())
    
    results['summary'] = {
        'total_valid': total_valid,
        'total_invalid': total_invalid,
        'total_warnings': total_warnings,
        'analysis_types': list(results.keys())
    }
    
    return results
