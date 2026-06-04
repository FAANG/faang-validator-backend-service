import os
import uuid
import copy
import traceback
from typing import Dict, Any, Optional

import requests
from lxml import etree

from app.conversions.generate_analysis_and_submission_xml import get_xml_files
from app.validation.constants import ENA_TEST_SERVER, ENA_PROD_SERVER
from app.tracking.submission_tracker import save_submission_data


def _read_file_bytes(path: str) -> bytes:
    """Read a file's contents as bytes (used to build multipart upload parts)."""
    with open(path, 'rb') as fh:
        return fh.read()


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

        # Extract ERROR and INFO messages (Django pattern)
        error_messages = []
        info_messages = []

        for messages in root.findall('MESSAGES'):
            for error in messages.findall('ERROR'):
                if error.text:
                    error_messages.append(error.text)
            for info in messages.findall('INFO'):
                if info.text:
                    info_messages.append(info.text)

        # Django logic: if there are errors, it fails
        if len(error_messages) > 0:
            return (False, error_messages, info_messages)
        else:
            return (True, [], info_messages)

    except Exception as e:
        print(f"Error parsing submission results: {e}")
        return (False, [f"Failed to parse XML: {str(e)}"], [])


class AnalysisSubmitter:
    def __init__(self):
        pass

    def _prepare_analyses_data(self, json_to_convert: Dict[str, Any], submission_id: str, action: str = "submission"):
        prepared_data = copy.deepcopy(json_to_convert)

        # convert Pydantic models to dicts - analysis_results
        if 'analysis_results' in prepared_data:
            for analysis_type, results in prepared_data['analysis_results'].items():
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

    def submit_to_ena(self, results: Dict[str, Any], credentials: Dict[str, str], action: str = "submission") -> Dict[
        str, Any]:
        try:
            submission_id = str(uuid.uuid4())

            submission_path = (
                ENA_TEST_SERVER if credentials['mode'] == 'test'
                else ENA_PROD_SERVER
            )

            print(f"Preparing analysis data for submission ID: {submission_id}")

            analysis_xml, submission_xml = self._prepare_analyses_data(results, submission_id, action=action)

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

            # Submit to ENA via an HTTP multipart POST. Credentials are passed
            # through requests' HTTP basic auth and the XML payloads as form
            # files. This avoids spawning a shell (no command injection) and
            # keeps the password off any process command line.
            print(f"Submitting to ENA: {submission_path}")
            files = {
                'SUBMISSION': (os.path.basename(submission_xml),
                               _read_file_bytes(submission_xml), 'application/xml'),
                'ANALYSIS': (os.path.basename(analysis_xml),
                             _read_file_bytes(analysis_xml), 'application/xml'),
            }
            ena_response = requests.post(
                submission_path,
                auth=(username, password),
                files=files,
            )

            # parse results
            submission_results = ena_response.content
            success, error_messages, info_messages = _parse_submission_results(submission_results)
            result_str = submission_results.decode('utf-8')

            print(f"Submission result: {'Success' if success else 'Failed'}")
            print(result_str)

            # -----------------------------------------------------------------
            # Submission tracking: on success, write a record per study into
            # the Elasticsearch `submissions` index.
            # -----------------------------------------------------------------
            if success:
                self._write_tracking_record(
                    submission_results=submission_results,
                    analysis_xml_path=analysis_xml,
                    submission_id=submission_id,
                    action=action,
                )

            self._cleanup_xml_files([analysis_xml, submission_xml])

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
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Submission error: {str(e)}',
                'errors': [str(e)]
            }

    # -------------------------------------------------------------------
    # Tracking + cleanup helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _write_tracking_record(
        submission_results: bytes,
        analysis_xml_path: Optional[str],
        submission_id: str,
        action: str,
    ) -> None:

        try:
            receipt_root = etree.fromstring(submission_results)

            analysis_xml_root = None
            if analysis_xml_path and os.path.exists(analysis_xml_path):
                analysis_xml_root = etree.parse(analysis_xml_path).getroot()
            else:
                print(
                    f"WARNING: analysis XML not on disk at {analysis_xml_path}; "
                    "tracking record will be written without analyses list."
                )

            save_submission_data(
                receipt_root=receipt_root,
                original_xml_roots={'analysis': analysis_xml_root},
                submission_type='analyses',
                action=action,
            )
        except Exception as tracking_exc:
            print(
                f"WARNING: ENA submission succeeded but tracking write "
                f"failed for submission_id={submission_id}: {tracking_exc}"
            )
            traceback.print_exc()

    @staticmethod
    def _cleanup_xml_files(paths) -> None:
        for xml_file in paths:
            try:
                if xml_file and os.path.exists(xml_file):
                    os.remove(xml_file)
            except Exception as e:
                print(f"Warning: Could not cleanup {xml_file}: {e}")