import base64
import io
import json
import re
import unicodedata
from typing import List, Any, Dict

import pandas as pd


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
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), dtype=str)
            df = df.fillna("")

            # Extract headers and rows from DataFrame
            headers = df.columns.tolist()
            rows = df.values.tolist()

            # Process headers using the same logic as in Google Sheet processor
            processed_headers = process_headers(headers)
            # Build JSON data using the same logic as in Google Sheet processor
            records = build_json_data(processed_headers, rows)

            # For CSV, we use a default sheet name
            sheet_name = "Sheet 1"
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
                records = build_json_data(processed_headers, rows)

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
            # Build JSON data using the same logic as in Google Sheet processor
            records = build_json_data(processed_headers, rows)

            # For CSV, we use a default sheet name
            sheet_name = "Sheet 1"
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
                records = build_json_data(processed_headers, rows)

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


def build_json_data(headers: List[str], rows: List[List[str]]) -> List[Dict[str, Any]]:
    """
    Build JSON structure from processed headers and rows.
    Only include 'Health Status' if it exists in the headers.
    Always treat 'Child Of', 'Specimen Picture URL', and 'Derived From' as lists.
    """
    grouped_data = []
    has_health_status = any(h.startswith("Health Status") for h in headers)
    has_child_of = any(h == "Child Of" for h in headers)
    has_specimen_picture_url = any(h == "Specimen Picture URL" for h in headers)
    has_derived_from = any(h == "Derived From" for h in headers)

    for row in rows:
        record: Dict[str, Any] = {}
        if has_health_status:
            record["Health Status"] = []
        if has_child_of:
            record["Child Of"] = []
        if has_specimen_picture_url:
            record["Specimen Picture URL"] = []
        if has_derived_from:
            record["Derived From"] = []

        i = 0
        while i < len(headers):
            col = headers[i]
            val = row[i] if i < len(row) else ""

            # ✅ Special handling if Health Status is in headers
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

            # ✅ Special handling for Child Of headers
            elif has_child_of and col.startswith("Child Of"):
                if val:  # Only append non-empty values
                    record["Child Of"].append(val)
                i += 1
                continue

            # ✅ Special handling for Specimen Picture URL headers
            elif has_specimen_picture_url and col.startswith("Specimen Picture URL"):
                if val:  # Only append non-empty values
                    record["Specimen Picture URL"].append(val)
                i += 1
                continue

            # ✅ Special handling for Derived From headers
            elif has_derived_from and col.startswith("Derived From"):
                if val:  # Only append non-empty values
                    record["Derived From"].append(val)
                i += 1
                continue

            # ✅ Normal processing for all other columns
            if col in record:
                if not isinstance(record[col], list):
                    record[col] = [record[col]]
                record[col].append(val)
            else:
                record[col] = val
            i += 1

        grouped_data.append(record)

    return grouped_data
