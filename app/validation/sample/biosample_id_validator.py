import re
from typing import Dict, List, Tuple, Any


def validate_biosample_ids_batch(
    data_dict: Dict[str, List[Dict[str, Any]]],
    action: str
) -> Tuple[List[str], List[str]]:
    valid_ids = []
    invalid_ids = []
    skip_sheets = {'person', 'organization', 'submission', 'faang_field_values'}

    # check that correct field exists
    for sheet_name, records in data_dict.items():
        if sheet_name in skip_sheets or not records:
            continue

        # Check first record to see what fields are present
        first_record = records[0]
        print("miaw: ", first_record)
        has_sample_name = 'Sample Name' in first_record
        has_biosample_id = 'Biosample ID' in first_record

        if action == "submit":
            # NEW SUBMISSION: Must have 'Sample Name', NOT 'Biosample ID'
            if not has_sample_name:
                invalid_ids.append(
                    f"Sheet '{sheet_name}': Missing 'Sample Name' field. "
                    f"For new submissions, use the template with 'Sample Name' column."
                )
            if has_biosample_id:
                invalid_ids.append(
                    f"Sheet '{sheet_name}': Found 'Biosample ID' field. "
                    f"This field is only for updates. You may be using the UPDATE template. "
                    f"For new submissions, use 'Sample Name' instead."
                )

        elif action == "update":
            # UPDATE: Must have 'Biosample ID', NOT 'Sample Name'
            if not has_biosample_id:
                invalid_ids.append(
                    f"Sheet '{sheet_name}': Missing 'Biosample ID' field. "
                    f"For updates, use the template with 'Biosample ID' column."
                )
            if has_sample_name:
                invalid_ids.append(
                    f"Sheet '{sheet_name}': Found 'Sample Name' field. "
                    f"This field is only for new submissions. You may be using the NEW SUBMISSION template. "
                    f"For updates, use 'Biosample ID' instead."
                )

    # If header validation failed, return immediately
    if invalid_ids:
        return valid_ids, invalid_ids

    # validate biosample ID format (only for updates)
    if action != "update":
        return [], []

    for sheet_name, records in data_dict.items():
        if sheet_name in skip_sheets:
            continue

        for record in records:
            biosample_id = _extract_biosample_id(record)
            if biosample_id:
                _check_biosample_id_format(
                    biosample_id.upper(),
                    valid_ids,
                    invalid_ids
                )

            # derived_from relationship field
            derived_from_ids = _extract_relationship_ids(record, 'Derived From')
            for df_id in derived_from_ids:
                _check_biosample_id_format(
                    df_id.upper(),
                    valid_ids,
                    invalid_ids
                )

            # child_of relationship field
            child_of_ids = _extract_relationship_ids(record, 'Child Of')
            for co_id in child_of_ids:
                _check_biosample_id_format(
                    co_id.upper(),
                    valid_ids,
                    invalid_ids
                )

    # Remove duplicates
    valid_ids = list(set(valid_ids))
    invalid_ids = list(set(invalid_ids))

    return valid_ids, invalid_ids


def _extract_biosample_id(record: Dict[str, Any]) -> str:
    if 'Biosample ID' in record:
        return str(record['Biosample ID']).strip()

    return ''


def _extract_relationship_ids(record: Dict[str, Any], field_name: str) -> List[str]:
    ids = []

    relationship_data = None
    if field_name in record:
        relationship_data = record[field_name]

    if not relationship_data:
        return ids

    if isinstance(relationship_data, list):
        for item in relationship_data:
            if isinstance(item, str):
                if item.strip():
                    ids.append(item.strip())


    elif isinstance(relationship_data, str):
        if relationship_data.strip():
            ids.append(relationship_data.strip())

    return [id_str.strip() for id_str in ids
            if id_str and id_str.strip() and id_str.strip().upper().startswith('SAM')]


def _check_biosample_id_format(
    biosample_id: str,
    valid_ids: List[str],
    invalid_ids: List[str]
) -> None:
    # BioSample ID pattern: SAM + [E/D/N] + optional [A/G] + digits
    pattern = r'^SAM[EDN][AG]?\d+$'

    if re.match(pattern, biosample_id):
        valid_ids.append(biosample_id)
    else:
        invalid_ids.append(biosample_id)