import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
from urllib.parse import quote

import requests
from lxml import etree

CHECK_INTERVAL_SECONDS = 60
MAX_CHECKS = 10
PARALLEL_LOOKUPS = 5
REQUEST_TIMEOUT_SECONDS = 60


def reports_base_url(submission_path: str) -> str:
    """https://host/ena/submit/drop-box/submit/ -> https://host/ena/submit/report"""
    host = submission_path.split('/ena/submit/')[0]
    return f"{host}/ena/submit/report"


class _ReportsApi:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.auth = (username, password)

    def get(self, kind: str, alias_or_accession: str) -> Optional[dict]:
        """Return the report row for one object, or None if ENA doesn't have it."""
        response = self.session.get(
            f"{self.base_url}/{kind}/{quote(alias_or_accession, safe='')}",
            params={'format': 'json'},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        rows = response.json() if response.text.strip() else []
        if not rows:
            return None
        row = rows[0]
        return row.get('report', row) if isinstance(row, dict) else None


def _aliases(xml_path: Optional[str], tag: str) -> List[str]:
    if not xml_path or not os.path.exists(xml_path):
        return []
    root = etree.parse(xml_path).getroot()
    return [elt.get('alias') for elt in root.findall(tag) if elt.get('alias')]


def _study_ref_by_experiment(experiment_xml: str) -> Dict[str, str]:
    root = etree.parse(experiment_xml).getroot()
    refs = {}
    for exp in root.findall('EXPERIMENT'):
        ref = exp.find('STUDY_REF')
        if ref is not None and exp.get('alias'):
            refs[exp.get('alias')] = ref.get('refname') or ref.get('accession') or ''
    return refs


def _unknown(reason: str) -> dict:
    return {'status': 'unknown', 'reason': reason, 'receipt': None, 'missing': []}


def reconcile_add(
    submission_path: str,
    username: str,
    password: str,
    experiment_xml: str,
    run_xml: str,
    study_xml: str,
    submission_xml: str,
    progress: Optional[Callable[[str], None]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    experiments = _aliases(experiment_xml, 'EXPERIMENT')
    runs = _aliases(run_xml, 'RUN')
    studies = _aliases(study_xml, 'STUDY')
    submission_aliases = _aliases(submission_xml, 'SUBMISSION')
    if not experiments:
        return _unknown('the experiment XML is not available to check against')

    api = _ReportsApi(reports_base_url(submission_path), username, password)

    # 1. Wait until the last experiment and last run we sent show up.
    probes = [('experiments', experiments[-1])] + ([('runs', runs[-1])] if runs else [])
    for check in range(1, MAX_CHECKS + 1):
        if progress:
            progress(f'Checking ENA for registered objects ({check}/{MAX_CHECKS} min)')
        sleep(CHECK_INTERVAL_SECONDS)
        try:
            if all(api.get(kind, alias) for kind, alias in probes):
                break
        except (requests.RequestException, ValueError) as e:
            print(f'ENA reconciliation check {check} failed: {e}')
    else:
        return _unknown(f'nothing was found in ENA after {MAX_CHECKS} minutes')

    # 2. Look up every object once.
    if progress:
        progress(f'Collecting accessions from ENA ({len(experiments) + len(runs)} objects)')
    try:
        with ThreadPoolExecutor(max_workers=PARALLEL_LOOKUPS) as pool:
            exp_rows = dict(zip(experiments, pool.map(lambda a: api.get('experiments', a), experiments)))
            run_rows = dict(zip(runs, pool.map(lambda a: api.get('runs', a), runs)))

        # Study accession comes from the experiments that reference it.
        study_refs = _study_ref_by_experiment(experiment_xml)
        study_rows = {}
        for study_alias in studies:
            study_id = next(
                (row.get('studyId') for alias, row in exp_rows.items()
                 if row and study_refs.get(alias) == study_alias and row.get('studyId')),
                None,
            )
            study_rows[study_alias] = api.get('studies', study_id) if study_id else None
    except (requests.RequestException, ValueError) as e:
        return _unknown(f'could not collect accessions from ENA: {e}')

    missing = (
        [f'study {a}' for a, r in study_rows.items() if not r]
        + [f'experiment {a}' for a, r in exp_rows.items() if not r]
        + [f'run {a}' for a, r in run_rows.items() if not r]
    )
    if missing:
        return {'status': 'partial', 'reason': f'{len(missing)} object(s) not found in ENA',
                'receipt': None, 'missing': missing}

    # 3. Rebuild the receipt ENA should have returned.
    receipt = etree.Element(
        'RECEIPT',
        receiptDate=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        submissionFile=os.path.basename(submission_xml or ''),
        success='true',
    )
    for alias, row in exp_rows.items():
        etree.SubElement(receipt, 'EXPERIMENT', accession=row.get('id', ''), alias=alias,
                         status=row.get('releaseStatus') or '')
    for alias, row in run_rows.items():
        etree.SubElement(receipt, 'RUN', accession=row.get('id', ''), alias=alias,
                         status=row.get('releaseStatus') or '')
    for alias, row in study_rows.items():
        ids = [i for i in (row.get('id'), row.get('secondaryId')) if i]
        project = next((i for i in ids if i.startswith('PRJ')), '')
        study = next((i for i in ids if not i.startswith('PRJ')), '')
        study_elt = etree.SubElement(receipt, 'STUDY', accession=study, alias=alias,
                                     status=row.get('releaseStatus') or '')
        etree.SubElement(study_elt, 'EXT_ID', accession=project, type='Project')
    for alias in submission_aliases:
        # The submission accession is not available from the Reports API.
        etree.SubElement(receipt, 'SUBMISSION', accession='', alias=alias)
    messages = etree.SubElement(receipt, 'MESSAGES')
    etree.SubElement(messages, 'INFO').text = (
        'ENA did not return a receipt; this receipt was rebuilt from the Webin Reports API. '
        'The submission accession is not available.'
    )

    return {'status': 'registered', 'reason': '', 'missing': [],
            'receipt': etree.tostring(receipt, xml_declaration=True, encoding='UTF-8')}
