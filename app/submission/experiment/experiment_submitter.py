import os
import uuid
import subprocess
import copy
import re
import traceback
from typing import Dict, Any, Optional
from lxml import etree

from app.conversions.generate_experiment_xmls import get_xml_files
from app.validation.constants import ENA_TEST_SERVER, ENA_PROD_SERVER
from app.tracking.submission_tracker import save_submission_data
from app.submission.retryable import RetryableSubmissionError, TRANSIENT_CURL_EXIT_CODES


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

    def submit_to_ena(self, results: Dict[str, Any], credentials: Dict[str, str], action: str = "submission",
                      raise_on_transient: bool = False) -> Dict[str, Any]:
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
            for name, xml in [
                ('experiment', experiment_xml),
                ('run', run_xml),
                ('study', study_xml),
                ('submission', submission_xml),
            ]:
                if xml and xml.startswith('Error:'):
                    return {
                        'success': False,
                        'message': f'Failed to generate {name} XML',
                        'errors': [xml],
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

            # curl couldn't reach ENA (connect/timeout/etc.) — the submission
            # never landed, so it's safe to retry. In a background task, raise
            # so Celery retries; the sync path falls through and reports failure.
            if raise_on_transient and submit_to_ena_process.returncode in TRANSIENT_CURL_EXIT_CODES:
                raise RetryableSubmissionError(
                    f"curl exit {submit_to_ena_process.returncode} submitting experiment to ENA"
                )

            # Parse results
            submission_results = submit_to_ena_process.stdout
            success, error_messages, info_messages = _parse_submission_results(submission_results)
            result_str = submission_results.decode('utf-8')

            print(f"Submission result: {'Success' if success else 'Failed'}")
            print(result_str)

            # -----------------------------------------------------------------
            # Submission tracking: on success, write a record per study into
            # the Elasticsearch `submissions` index. This is what the
            # tracking dashboard, the subscription system, and the FAANG
            # data-portal ingestion pipeline all read from. If this step
            # fails we log loudly but do NOT fail the submission response —
            # the data is already in ENA at this point.
            # -----------------------------------------------------------------
            if success:
                self._write_tracking_record(
                    submission_results=submission_results,
                    experiment_xml_path=experiment_xml,
                    submission_id=submission_id,
                    action=action,
                )

            # Cleanup XML files (runs AFTER tracking so the experiment
            # XML is still on disk when the tracker needs it).
            self._cleanup_xml_files(
                [experiment_xml, run_xml, study_xml, submission_xml]
            )

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

        except RetryableSubmissionError:
            # Let transient failures propagate so the background task retries.
            raise
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
        experiment_xml_path: Optional[str],
        submission_id: str,
        action: str,
    ) -> None:
        try:
            receipt_root = etree.fromstring(submission_results)

            experiment_xml_root = None
            if experiment_xml_path and os.path.exists(experiment_xml_path):
                experiment_xml_root = etree.parse(experiment_xml_path).getroot()
            else:
                print(
                    f"WARNING: experiment XML not on disk at {experiment_xml_path}; "
                    "tracking record will be written without experiments list."
                )

            save_submission_data(
                receipt_root=receipt_root,
                original_xml_roots={'experiment': experiment_xml_root},
                submission_type='experiments',
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
