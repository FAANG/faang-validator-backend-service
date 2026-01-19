import uuid
import subprocess
import re
from typing import Dict, Any

from app.conversions.generate_analysis_and_submission_xml import get_xml_files
from app.validation.constants import ENA_TEST_SERVER, ENA_PROD_SERVER


def _parse_submission_results(submission_results) -> str:
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


class AnalysisSubmitter:
    def __init__(self):
        pass

    def _prepare_analyses_data(self, json_to_convert: Dict[str, Any], submission_id: str):
        return get_xml_files(json_to_convert, submission_id)

    def submit_to_ena(self, results: Dict[str, Any], credentials: Dict[str, str]) -> Dict[str, Any]:
        try:
            submission_id = str(uuid.uuid4())

            submission_path = (
                ENA_TEST_SERVER if credentials['mode'] == 'test' 
                else ENA_PROD_SERVER
            )
            
            print(f"Preparing analysis data for submission ID: {submission_id}")

            analysis_xml, submission_xml = self._prepare_analyses_data(results, submission_id)

            if analysis_xml.startswith('Error:'):
                return {
                    'success': False,
                    'message': 'Failed to generate analysis XML',
                    'errors': [analysis_xml]
                }

            if submission_xml and submission_xml.startswith('Error:'):
                return {
                    'success': False,
                    'message': 'Failed to generate submission XML',
                    'errors': [submission_xml]
                }

            print(f"Generated XML files: {submission_xml}, {analysis_xml}")

            # Get credentials
            username = credentials["username"]
            password = credentials["password"]
            password_escaped = re.escape(password)
            
            # Submit to ENA using curl
            print(f"Submitting to ENA: {submission_path}")
            submit_to_ena_process = subprocess.run(
                f'curl -u {username}:{password_escaped} '
                f'-F "SUBMISSION=@{submission_xml}" '
                f'-F "ANALYSIS=@{analysis_xml}" '
                f'"{submission_path}"',
                shell=True, 
                capture_output=True
            )

            # parse results
            submission_results = submit_to_ena_process.stdout
            parsed_results = _parse_submission_results(submission_results)
            result_str = submission_results.decode('utf-8')
            
            print(f"Submission result: {parsed_results}")

            try:
                import os
                if os.path.exists(analysis_xml):
                    os.remove(analysis_xml)
                if os.path.exists(submission_xml):
                    os.remove(submission_xml)
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
