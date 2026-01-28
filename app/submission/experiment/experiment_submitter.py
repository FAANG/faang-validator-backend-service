import uuid
import subprocess
import copy
import re
from typing import Dict, Any
from lxml import etree

from app.conversions.generate_experiment_xmls import get_xml_files
from app.validation.constants import ENA_TEST_SERVER, ENA_PROD_SERVER


def _parse_submission_results(submission_results) -> tuple:
    try:
        if isinstance(submission_results, bytes):
            result_str = submission_results.decode('utf-8')
        else:
            result_str = str(submission_results)

        # Check for access denied
        if 'Access Denied' in result_str:
            return (False, ['Access Denied'], [])

        # Parse XML
        root = etree.fromstring(submission_results)

        # Extract ERROR and INFO messages
        error_messages = []
        info_messages = []

        for messages in root.findall('MESSAGES'):
            for error in messages.findall('ERROR'):
                if error.text:
                    error_messages.append(error.text)
            for info in messages.findall('INFO'):
                if info.text:
                    info_messages.append(info.text)

        if len(error_messages) > 0:
            return (False, error_messages, info_messages)
        else:
            return (True, [], info_messages)

    except Exception as e:
        print(f"Error parsing submission results: {e}")
        return (False, [f"Failed to parse XML: {str(e)}"], [])


class ExperimentSubmitter:

    def __init__(self):
        pass

    def _prepare_experiment_data(self, json_to_convert: Dict[str, Any], submission_id: str, action: str = "submission"):
        prepared_data = copy.deepcopy(json_to_convert)

        # convert Pydantic models to dicts - experiment_results
        if 'experiment_results' in prepared_data:
            for exp_type, results in prepared_data['experiment_results'].items():
                if isinstance(results, dict) and 'valid' in results:
                    for record in results['valid']:
                        if 'model' in record and hasattr(record['model'], 'model_dump'):
                            record['model'] = record['model'].model_dump(by_alias=True)

        # convert Pydantic models to dicts - metadata_results
        if 'metadata_results' in prepared_data:
            for metadata_type, results in prepared_data['metadata_results'].items():
                if isinstance(results, dict) and 'valid' in results:
                    for record in results['valid']:
                        if 'model' in record and hasattr(record['model'], 'model_dump'):
                            record['model'] = record['model'].model_dump(by_alias=True)

        return get_xml_files(prepared_data, submission_id, action=action)


    def submit_to_ena(self, results: Dict[str, Any], credentials: Dict[str, str], action: str = "submission") -> Dict[str, Any]:
        try:
            submission_id = str(uuid.uuid4())

            submission_path = (
                ENA_TEST_SERVER if credentials['mode'] == 'test'
                else ENA_PROD_SERVER
            )

            print(f"Preparing experiment data for submission ID: {submission_id}")

            # Generate XML files
            experiment_xml, run_xml, study_xml, submission_xml = self._prepare_experiment_data(
                results, submission_id, action=action
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
            success, error_messages, info_messages = _parse_submission_results(submission_results)
            result_str = submission_results.decode('utf-8')

            print(f"Submission result: {'Success' if success else 'Failed'}")
            print(submission_results.decode('utf-8'))

            # Cleanup XML files
            try:
                import os
                for xml_file in [experiment_xml, run_xml, study_xml, submission_xml]:
                    if xml_file and os.path.exists(xml_file):
                        os.remove(xml_file)
            except Exception as e:
                print(f"Warning: Could not cleanup XML files: {e}")

            # # Return success for testing (submission is commented out)
            # return {
            #     'success': True,
            #     'message': f'XML files generated successfully (submission disabled for testing)',
            #     'submission_results': f'Generated files:\n  - {experiment_xml}\n  - {run_xml}\n  - {study_xml}\n  - {submission_xml}'
            # }

            if success:
                action_message = "updated in" if action == "update" else "submitted to"
                return {
                    'success': True,
                    'message': f'Successfully {action_message} ENA',
                    'submission_results': result_str,
                    'errors': error_messages,
                    'info_messages': info_messages
                }
            else:
                return {
                    'success': False,
                    'message': 'Submission failed',
                    'submission_results': result_str,
                    'errors': error_messages,
                    'info_messages': info_messages
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