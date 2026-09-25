import os
import uuid
import subprocess
import copy
import traceback
from typing import Dict, Any, Optional, Callable
from lxml import etree

from app.conversions.generate_experiment_xmls import get_xml_files
from app.validation.constants import ENA_TEST_SERVER, ENA_PROD_SERVER
from app.tracking.submission_tracker import save_submission_data
from app.submission.retryable import RetryableSubmissionError, TRANSIENT_CURL_EXIT_CODES
from app.submission.experiment.ena_reconciliation import reconcile_add

# curl exit codes where the request provably never reached ENA
# (6 could not resolve host, 7 could not connect, 35 TLS handshake failed).
# Only these are safe to retry for an ADD
PRE_SEND_CURL_EXIT_CODES = {6, 7, 35}


def _is_safe_to_retry(exit_code: int, action: str) -> bool:
    if action == "update":
        return exit_code in TRANSIENT_CURL_EXIT_CODES
    # ADD: retry only when ENA cannot have received the request.
    return exit_code in PRE_SEND_CURL_EXIT_CODES


def _is_receipt_xml(body: bytes) -> bool:
    try:
        return etree.fromstring(body).tag == 'RECEIPT'
    except Exception:
        return False


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
                      raise_on_transient: bool = False,
                      progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
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

            print(f"Submitting to ENA: {submission_path}")
            submit_to_ena_process = subprocess.run(
                [
                    'curl', '--silent', '--show-error',
                    '--write-out', '\nFAANG_HTTP_STATUS:%{http_code}',
                    '-u', f'{username}:{password}',
                    '-F', f'SUBMISSION=@{submission_xml}',
                    '-F', f'EXPERIMENT=@{experiment_xml}',
                    '-F', f'RUN=@{run_xml}',
                    '-F', f'STUDY=@{study_xml}',
                    submission_path,
                ],
                capture_output=True,
            )

            # curl's response body can be empty even though stderr explains why.
            response = submit_to_ena_process.stdout or b''
            body, separator, status = response.rpartition(b'\nFAANG_HTTP_STATUS:')
            submission_results = body if separator else response
            http_status = status.decode(errors='replace').strip() if separator else 'unknown'
            stderr = (submit_to_ena_process.stderr or b'').decode(errors='replace').strip()
            if password:
                stderr = stderr.replace(password, '[REDACTED]')
            result_str = submission_results.decode(errors='replace')
            exit_code = submit_to_ena_process.returncode

            if exit_code != 0 or not submission_results.strip():
                reason = 'ENA request failed' if exit_code != 0 else 'ENA returned an empty response'
                error_message = f'{reason} (curl exit {exit_code}, HTTP {http_status}).'
                if stderr:
                    error_message += f' {stderr}'
                print(error_message)
                if raise_on_transient and _is_safe_to_retry(exit_code, action):
                    raise RetryableSubmissionError(error_message)
                if (action != 'update' and exit_code in TRANSIENT_CURL_EXIT_CODES
                        and exit_code not in PRE_SEND_CURL_EXIT_CODES):
                    # Not retried: ENA may have received this ADD.
                    return self._check_what_ena_registered(
                        error_message, submission_path, username, password, submission_id, action,
                        experiment_xml, run_xml, study_xml, submission_xml, progress_callback,
                    )
                return {
                    'success': False,
                    'message': 'Submission failed',
                    'submission_results': result_str,
                    'errors': [error_message],
                    'info_messages': [],
                }

            # HTTP 5xx is never retried automatically (exit code is 0): for an ADD
            success, error_messages, info_messages = _parse_submission_results(submission_results)
            if http_status.isdigit() and int(http_status) >= 400:
                success = False
                error_messages.insert(0, f'ENA returned HTTP {http_status}.')

            print(f"Submission result: {'Success' if success else 'Failed'}")
            print(result_str)

            # HTTP 5xx, or a reply that is not a receipt: ENA may still have
            # registered this ADD (e.g. its web front end timed out), so ask it.
            http_code = int(http_status) if http_status.isdigit() else 0
            if not success and action != 'update' and (
                    http_code >= 500 or (http_code < 400 and not _is_receipt_xml(submission_results))):
                return self._check_what_ena_registered(
                    '; '.join(error_messages), submission_path, username, password, submission_id,
                    action, experiment_xml, run_xml, study_xml, submission_xml, progress_callback,
                )

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

            # Cleanup XML files
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
    # Unclear ADD outcome: ask ENA what it registered
    # -------------------------------------------------------------------

    def _check_what_ena_registered(self, original_error, submission_path, username, password,
                                   submission_id, action, experiment_xml, run_xml, study_xml,
                                   submission_xml, progress_callback) -> Dict[str, Any]:
        print(f"Unclear ENA response ({original_error}); checking what ENA registered.")
        try:
            outcome = reconcile_add(
                submission_path, username, password,
                experiment_xml, run_xml, study_xml, submission_xml,
                progress=progress_callback,
            )
        except Exception as e:
            traceback.print_exc()
            outcome = {'status': 'unknown', 'reason': f'the check itself failed: {e}',
                       'receipt': None, 'missing': []}
        print(f"ENA check result: {outcome['status']} {outcome['reason']}")

        if outcome['status'] == 'registered':
            receipt = outcome['receipt']
            self._write_tracking_record(
                submission_results=receipt,
                experiment_xml_path=experiment_xml,
                submission_id=submission_id,
                action=action,
            )
            self._cleanup_xml_files([experiment_xml, run_xml, study_xml, submission_xml])
            return {
                'success': True,
                'message': 'Successfully submitted to ENA',
                'submission_results': receipt.decode(),
                'errors': [],
                'info_messages': [
                    f'ENA did not return a receipt ({original_error}), but all objects were '
                    'found in ENA. The receipt was rebuilt from the Webin Reports API.'
                ],
            }

        # XML files are kept on purpose: they show exactly what was sent.
        if outcome['status'] == 'partial':
            missing = outcome['missing']
            shown = ', '.join(missing[:20]) + (f' and {len(missing) - 20} more' if len(missing) > 20 else '')
            return {
                'success': False,
                'message': 'Submission partly registered in ENA',
                'submission_results': '',
                'errors': [original_error, f"{outcome['reason']}: {shown}. "
                           'Check the Webin portal before resubmitting.'],
                'info_messages': [],
            }

        return {
            'success': False,
            'message': 'Submission status unknown',
            'submission_results': '',
            'errors': [f"{original_error} ENA may have registered these objects, but "
                       f"{outcome['reason']}. Check the Webin portal before resubmitting."],
            'info_messages': [],
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
