import base64
import io
import json
import re
import unicodedata
from typing import List, Any, Dict

import pandas as pd

from app.profiler import cprofiled


def parse_contents(contents, filename):
    """
    Parse the contents of an uploaded file and convert it to a structured format.

    Args:
        contents (str): The base64-encoded contents of the file
        filename (str): The name of the uploaded file

    Returns:
        tuple: (all_sheets_data, sheet_names, error_message)
            - all_sheets_data: Dictionary with sheet names as keys and lists of dictionaries containing the parsed data as values
            - sheet_names: List of sheet names
            - error_message: Error message if any, None otherwise
    """
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        if 'csv' in filename:
            # For CSV files, we only have one sheet
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8-sig')), dtype=str)
            df = df.fillna("")

            # Extract headers and rows from DataFrame
            headers = df.columns.tolist()
            rows = df.values.tolist()

            # Process headers using the same logic as in Google Sheet processor
            processed_headers = process_headers(headers)
            # For CSV, we use a default sheet name
            sheet_name = "Sheet 1"
            # Build JSON data using the same logic as in Google Sheet processor
            records = build_json_data(processed_headers, rows, sheet_name)
            all_sheets_data = {sheet_name: records}
            sheet_names = [sheet_name]

        elif 'xls' in filename or 'xlsx' in filename:
            # For Excel files, process all sheets
            excel_file = pd.ExcelFile(io.BytesIO(decoded), engine="openpyxl")
            sheet_names = excel_file.sheet_names

            all_sheets_data = {}

            for sheet_name in sheet_names:
                df = excel_file.parse(sheet_name, dtype=str)
                df = df.fillna("")

                # Handle empty sheets by adding an empty list
                if df.empty:
                    all_sheets_data[sheet_name] = []
                    continue

                # Extract headers and rows from DataFrame
                headers = df.columns.tolist()
                rows = df.values.tolist()

                # Process headers using the same logic as in Google Sheet processor
                processed_headers = process_headers(headers)
                # Build JSON data using the same logic as in Google Sheet processor
                records = build_json_data(processed_headers, rows, sheet_name)

                all_sheets_data[sheet_name] = records

            # If no valid sheets were found, return an error
            if not all_sheets_data:
                return None, None, "No valid data found in the Excel file."

        else:
            return None, None, "Invalid file type. Please upload a CSV or Excel file."

    except Exception as e:
        print(e)
        return None, None, f"There was an error processing this file: {e}"

    return all_sheets_data, sheet_names, None

@cprofiled()
def parse_contents_api(contents, filename):
    """
    Parse the contents of an uploaded file from FastAPI and convert it to a structured format.

    Args:
        contents (bytes): The binary contents of the file
        filename (str): The name of the uploaded file

    Returns:
        tuple: (all_sheets_data, sheet_names, error_message)
            - all_sheets_data: Dictionary with sheet names as keys and lists of dictionaries containing the parsed data as values
            - sheet_names: List of sheet names
            - error_message: Error message if any, None otherwise
    """
    try:
        if not filename:
            return None, None, "Filename is required."

        if not contents:
            return None, None, "File contents are empty."

        if 'csv' in filename:
            # For CSV files, we only have one sheet
            df = pd.read_csv(io.BytesIO(contents), dtype=str)
            df = df.fillna("")

            # Extract headers and rows from DataFrame
            headers = df.columns.tolist()
            rows = df.values.tolist()

            # Process headers using the same logic as in Google Sheet processor
            processed_headers = process_headers(headers)
            # For CSV, we use a default sheet name
            sheet_name = "Sheet 1"
            # Build JSON data using the same logic as in Google Sheet processor
            records = build_json_data(processed_headers, rows, sheet_name)
            all_sheets_data = {sheet_name: records}
            sheet_names = [sheet_name]

        elif 'xls' in filename or 'xlsx' in filename:
            # For Excel files, process all sheets
            excel_file = pd.ExcelFile(io.BytesIO(contents), engine="openpyxl")
            sheet_names = excel_file.sheet_names

            all_sheets_data = {}

            for sheet_name in sheet_names:
                df = excel_file.parse(sheet_name, dtype=str)
                df = df.fillna("")

                # Handle empty sheets by adding an empty list
                if df.empty:
                    all_sheets_data[sheet_name] = []
                    continue

                # Extract headers and rows from DataFrame
                headers = df.columns.tolist()
                rows = df.values.tolist()

                # Process headers using the same logic as in Google Sheet processor
                processed_headers = process_headers(headers)
                # Build JSON data using the same logic as in Google Sheet processor
                records = build_json_data(processed_headers, rows, sheet_name)

                all_sheets_data[sheet_name] = records
                # print(json.dumps(records, indent=2, default=str))
            # If no valid sheets were found, return an error
            if not all_sheets_data:
                return None, None, "No valid data found in the Excel file."

        else:
            return None, None, "Invalid file type. Please upload a CSV or Excel file."

    except Exception as e:
        print(e)
        return None, None, f"There was an error processing this file: {e}"

    return all_sheets_data, sheet_names, None


def read_workbook_xlsx(path: str):
    def to_ascii_str(x: object) -> str:
        if x is None:
            return ""
        s = str(x)
        s = unicodedata.normalize("NFKD", s)
        s = s.encode("ascii", "ignore").decode("ascii", errors="ignore")
        s = re.sub(r"[^\x20-\x7E\s]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.dropna(how="all").dropna(axis=1, how="all")

        df = df.fillna("")
        df = df.applymap(to_ascii_str)

        df.columns = [to_ascii_str(c) for c in df.columns]
        return df

    xls = pd.ExcelFile(path, engine="openpyxl")

    raw = {name: xls.parse(sheet_name=name, dtype=str) for name in xls.sheet_names}

    return {name: _clean_df(df) for name, df in raw.items()}


def process_headers(headers: List[str]) -> List[str]:
    """Process headers according to the rules for duplicates."""
    new_headers = []
    i = 0
    while i < len(headers):
        h = headers[i]

        # Case 1: Header contains a period (.)
        if '.' in h and new_headers:
            # Concatenate with the previous header name
            prev_header = new_headers[-1]
            new_header = h.split('.')[0]
            new_headers.append(f"{prev_header} {new_header}")
            # Case 2: Consecutive duplicates
        elif i + 1 < len(headers) and headers[i + 1] == h:
            new_headers.append(h)
            while i + 1 < len(headers) and headers[i + 1] == h:
                i += 1
                new_headers.append(h)
        else:
            # Case 3: Non-consecutive duplicate
            if h in new_headers:
                # Concatenate with the last header name
                last_header = new_headers[-1] if new_headers else ""
                new_headers.append(f"{last_header}_{h}")
            else:
                new_headers.append(h)
        i += 1
    return new_headers


def build_json_data(headers: List[str], rows: List[List[str]], sheet_name: str = "") -> List[Dict[str, Any]]:
    """
    Build JSON structure from processed headers and rows.
    Only include 'Health Status' if it exists in the headers.
    Always treat 'Child Of', 'Specimen Picture URL', 'Derived From' as lists.
    'Secondary Project' is treated as a list only for analysis and experiment sheets.
    'File Names', 'File Types', 'Checksum Methods', 'Checksums', 'Samples', 'Experiments', and 'Runs' 
    are treated as lists only for analysis sheets (faang, ena, eva).
    Also handles experiment and analysis specific fields.
    """
    grouped_data = []
    # Check if this is an analysis sheet
    is_analysis_sheet = sheet_name.lower() in ['faang', 'ena', 'eva']
    # Check if this is an experiment sheet (normalize sheet name like in unified_validator)
    normalized_sheet_name = sheet_name.replace("_", " ").lower().strip()
    is_experiment_sheet = normalized_sheet_name in ['chip-seq input dna', 'chip-seq dna-binding proteins', 'rna-seq']
    # Secondary Project should be a list for analysis and experiment sheets only
    is_analysis_or_experiment_sheet = is_analysis_sheet or is_experiment_sheet
    
    has_health_status = any(h.startswith("Health Status") for h in headers)
    has_cell_type = any(h.startswith("Cell Type") for h in headers)
    has_child_of = any(h == "Child Of" for h in headers)
    has_specimen_picture_url = any(h == "Specimen Picture URL" for h in headers)
    has_derived_from = any(h == "Derived From" for h in headers)
    # Experiment fields
    has_chip_target = any(h.startswith("Chip Target") for h in headers)
    has_experiment_target = any(h.startswith("Experiment Target") for h in headers)
    # Analysis fields
    has_experiment_type = any(h.startswith("Experiment Type") for h in headers)
    has_platform = any(h.startswith("Platform") for h in headers)
    has_secondary_project = any(h.startswith("Secondary Project") for h in headers)
    # Secondary Project should be a list only for analysis/experiment sheets
    has_secondary_project_as_list = is_analysis_or_experiment_sheet and has_secondary_project
    # List fields that should be arrays only for analysis sheets
    has_file_names = is_analysis_sheet and any(h.startswith("File Names") for h in headers)
    has_file_types = is_analysis_sheet and any(h.startswith("File Types") for h in headers)
    has_checksum_methods = is_analysis_sheet and any(h.startswith("Checksum Methods") for h in headers)
    has_checksums = is_analysis_sheet and any(h.startswith("Checksums") for h in headers)
    has_samples = is_analysis_sheet and any(h.startswith("Samples") for h in headers)
    has_experiments = is_analysis_sheet and any(h.startswith("Experiments") for h in headers)
    has_runs = is_analysis_sheet and any(h.startswith("Runs") for h in headers)

    for row in rows:
        record: Dict[str, Any] = {}
        if has_health_status:
            record["Health Status"] = []
        if has_cell_type:
            record["Cell Type"] = []
        if has_child_of:
            record["Child Of"] = []
        if has_specimen_picture_url:
            record["Specimen Picture URL"] = []
        if has_derived_from:
            record["Derived From"] = []
        if has_chip_target:
            record["Chip Target"] = {}
        if has_experiment_target:
            record["Experiment Target"] = {}
        if has_experiment_type:
            record["Experiment Type"] = []
        if has_platform:
            record["Platform"] = []
        if has_secondary_project_as_list:
            record["Secondary Project"] = []
        if has_file_names:
            record["File Names"] = []
        if has_file_types:
            record["File Types"] = []
        if has_checksum_methods:
            record["Checksum Methods"] = []
        if has_checksums:
            record["Checksums"] = []
        if has_samples:
            record["Samples"] = []
        if has_experiments:
            record["Experiments"] = []
        if has_runs:
            record["Runs"] = []

        i = 0
        while i < len(headers):
            col = headers[i]
            val = row[i] if i < len(row) else ""

            # Special handling if Health Status is in headers
            if has_health_status and col.startswith("Health Status"):
                # Check next column for Term Source ID
                if i + 1 < len(headers) and "Term Source ID" in headers[i + 1]:
                    term_val = row[i + 1] if i + 1 < len(row) else ""

                    record["Health Status"].append({
                        "text": val,
                        "term": term_val
                    })
                    i += 2
                else:
                    if val:
                        record["Health Status"].append({
                            "text": val.strip(),
                            "term": ""
                        })
                    i += 1
                continue
            if has_health_status and col.startswith("Cell Type"):
                # Check next column for Term Source ID
                if i + 1 < len(headers) and "Term Source ID" in headers[i + 1]:
                    term_val = row[i + 1] if i + 1 < len(row) else ""

                    record["Cell Type"].append({
                        "text": val,
                        "term": term_val
                    })
                    i += 2
                else:
                    if val:
                        record["Cell Type"].append({
                            "text": val.strip(),
                            "term": ""
                        })
                    i += 1
                continue

            # Special handling for Child Of headers
            elif has_child_of and col.startswith("Child Of"):
                if val:  # Only append non-empty values
                    record["Child Of"].append(val)
                i += 1
                continue

            # Special handling for Specimen Picture URL headers
            elif has_specimen_picture_url and col.startswith("Specimen Picture URL"):
                if val:  # Only append non-empty values
                    record["Specimen Picture URL"].append(val)
                i += 1
                continue

            # Special handling for Derived From headers
            elif has_derived_from and col.startswith("Derived From"):
                if val:  # Only append non-empty values
                    record["Derived From"].append(val)
                i += 1
                continue

            # Special handling for chip target (experiment field)
            elif has_chip_target and col.startswith("chip target"):
                # Check next column for Term Source ID or Term
                if i + 1 < len(headers) and ("Term Source ID" in headers[i + 1] or "Term" in headers[i + 1]):
                    term_val = row[i + 1] if i + 1 < len(row) else ""
                    record["Chip Target"] = {
                        "text": val,
                        "term": term_val
                    }
                    i += 2
                else:
                    # If only text is provided, set term to empty
                    if val:
                        record["Chip Target"] = {
                            "text": val,
                            "term": ""
                        }
                    i += 1
                continue

            # Special handling for experiment target (experiment field)
            elif has_experiment_target and col.startswith("Experiment Target"):
                # Check next column for Term Source ID or Term
                if i + 1 < len(headers) and ("Term Source ID" in headers[i + 1] or "Term" in headers[i + 1]):
                    term_val = row[i + 1] if i + 1 < len(row) else ""
                    record["Experiment Target"] = {
                        "text": val,
                        "term": term_val
                    }
                    i += 2
                else:
                    # If only text is provided, set term to empty
                    if val:
                        record["Experiment Target"] = {
                            "text": val,
                            "term": ""
                        }
                    i += 1
                continue
            
            # Skip "Term Source ID" if it's already processed as part of experiment target
            elif col == "Term Source ID" and "Experiment Target" in record:
                i += 1
                continue

            # Special handling for experiment type (analysis field - array of objects)
            elif has_experiment_type and col.startswith("Experiment type"):
                if val:  # Only append non-empty values
                    record["Experiment Type"].append({"value": val})
                i += 1
                continue

            # Special handling for platform (analysis field - array of objects)
            elif has_platform and col.startswith("Platform"):
                if val:  # Only append non-empty values
                    record["Platform"].append({"value": val})
                i += 1
                continue

            # Special handling for Secondary Project (list for analysis/experiment sheets, single value for sample sheets)
            elif has_secondary_project and col.startswith("Secondary Project"):
                if has_secondary_project_as_list:
                    # For analysis/experiment sheets: treat as list
                    if val:  # Only append non-empty values
                        record["Secondary Project"].append(val)
                else:
                    # For sample sheets: treat as single value (use first non-empty value)
                    if "Secondary Project" not in record:
                        record["Secondary Project"] = val if val else None
                    elif not record["Secondary Project"] and val:
                        # Update if current value is empty/None and we have a non-empty value
                        record["Secondary Project"] = val
                i += 1
                continue

            # Special handling for File Names (list field)
            elif has_file_names and col.startswith("File Names"):
                if val:  # Only append non-empty values
                    record["File Names"].append(val)
                i += 1
                continue

            # Special handling for File Types (list field)
            elif has_file_types and col.startswith("File Types"):
                if val:  # Only append non-empty values
                    record["File Types"].append(val)
                i += 1
                continue

            # Special handling for Checksum Methods (list field)
            elif has_checksum_methods and col.startswith("Checksum Methods"):
                if val:  # Only append non-empty values
                    record["Checksum Methods"].append(val)
                i += 1
                continue

            # Special handling for Checksums (list field)
            elif has_checksums and col.startswith("Checksums"):
                if val:  # Only append non-empty values
                    record["Checksums"].append(val)
                i += 1
                continue

            # Special handling for Samples (list field)
            elif has_samples and col.startswith("Samples"):
                if val:  # Only append non-empty values
                    record["Samples"].append(val)
                i += 1
                continue

            # Special handling for Experiments (list field)
            elif has_experiments and col.startswith("Experiments"):
                if val:  # Only append non-empty values
                    record["Experiments"].append(val)
                i += 1
                continue

            # Special handling for Runs (list field)
            elif has_runs and col.startswith("Runs"):
                if val:  # Only append non-empty values
                    record["Runs"].append(val)
                i += 1
                continue

            # Normal processing for all other columns
            if col in record:
                if not isinstance(record[col], list):
                    record[col] = [record[col]]
                record[col].append(val)
            else:
                record[col] = val
            i += 1

        grouped_data.append(record)

    return grouped_data
