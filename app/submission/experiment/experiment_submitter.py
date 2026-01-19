import uuid
import subprocess
import re
from typing import Dict, Any

from app.conversions.generate_experiment_xmls import get_xml_files
from app.validation.constants import ENA_TEST_SERVER, ENA_PROD_SERVER


def _parse_submission_results(submission_results) -> str:
    """
    Parse ENA submission results to determine success or failure.
    
    Args:
        submission_results: Response from ENA submission
    
    Returns:
        str: 'Success' or 'Error'
    """
    try:
        if isinstance(submission_results, bytes):
            result_str = submission_results.decode('utf-8')
        else:
            result_str = str(submission_results)
        
        # Check for success indicators in ENA response
        if 'success="true"' in result_str or '<RECEIPT' in result_str:
            return 'Success'
        elif 'error' in result_str.lower() or 'ERROR' in result_str:
            return 'Error'
        else:
            # Default to success if no clear error
            return 'Success'
    except Exception as e:
        print(f"Error parsing submission results: {e}")
        return 'Error'


class ExperimentSubmitter:
    """
    Handles submission of experiment data to ENA.
    """
    
    def __init__(self):
        pass
    
    def _prepare_experiment_data(self, json_to_convert: Dict[str, Any], submission_id: str):
        """
        Prepare experiment data by generating XML files.
        
        Args:
            json_to_convert: Validated experiment data
            submission_id: Unique submission ID
        
        Returns:
            Tuple of XML file paths (experiment, run, study, submission)
        """
        return get_xml_files(json_to_convert, submission_id)
    
    def submit_to_ena(self, results: Dict[str, Any], credentials: Dict[str, str]) -> Dict[str, Any]:
        """
        Submit experiment data to ENA.
        
        Args:
            results: Validation results containing experiment data
            credentials: Dictionary containing username, password, and mode (test/prod)
        
        Returns:
            Dict containing submission results
        """
        try:
            submission_id = str(uuid.uuid4())
            
            submission_path = (
                ENA_TEST_SERVER if credentials['mode'] == 'test'
                else ENA_PROD_SERVER
            )
            
            print(f"Preparing experiment data for submission ID: {submission_id}")
            
            # Generate XML files
            experiment_xml, run_xml, study_xml, submission_xml = self._prepare_experiment_data(
                results, submission_id
            )
            
            # Check for errors in XML generation
            if experiment_xml and experiment_xml.startswith('Error:'):
                return {
                    'success': False,
                    'message': 'Failed to generate experiment XML',
                    'errors': [experiment_xml]
                }
            
            if run_xml and run_xml.startswith('Error:'):
                return {
                    'success': False,
                    'message': 'Failed to generate run XML',
                    'errors': [run_xml]
                }
            
            if study_xml and study_xml.startswith('Error:'):
                return {
                    'success': False,
                    'message': 'Failed to generate study XML',
                    'errors': [study_xml]
                }
            
            if submission_xml and submission_xml.startswith('Error:'):
                return {
                    'success': False,
                    'message': 'Failed to generate submission XML',
                    'errors': [submission_xml]
                }
            
            print(f"Generated XML files: {submission_xml}, {experiment_xml}, {run_xml}, {study_xml}")
            
            # Get credentials
            username = credentials["username"]
            password = credentials["password"]
            password_escaped = re.escape(password)
            
            # Submit to ENA using curl
            print(f"Submitting to ENA: {submission_path}")
            submit_to_ena_process = subprocess.run(
                f'curl -u {username}:{password_escaped} '
                f'-F "SUBMISSION=@{submission_xml}" '
                f'-F "EXPERIMENT=@{experiment_xml}" '
                f'-F "RUN=@{run_xml}" '
                f'-F "STUDY=@{study_xml}" '
                f'"{submission_path}"',
                shell=True,
                capture_output=True
            )
            
            # Parse results
            submission_results = submit_to_ena_process.stdout
            parsed_results = _parse_submission_results(submission_results)
            result_str = submission_results.decode('utf-8')
            
            print(f"Submission result: {parsed_results}")
            
            # Cleanup XML files
            try:
                import os
                for xml_file in [experiment_xml, run_xml, study_xml, submission_xml]:
                    if xml_file and os.path.exists(xml_file):
                        os.remove(xml_file)
            except Exception as e:
                print(f"Warning: Could not cleanup XML files: {e}")
            
            if parsed_results == 'Success':
                return {
                    'success': True,
                    'message': 'Successfully submitted to ENA',
                    'submission_results': result_str
                }
            else:
                return {
                    'success': False,
                    'message': 'Submission failed',
                    'submission_results': result_str,
                    'errors': [result_str]
                }
        
        except Exception as e:
            print(f"Error during ENA submission: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Submission error: {str(e)}',
                'errors': [str(e)]
            }
