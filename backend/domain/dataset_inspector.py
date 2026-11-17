"""Dataset content inspection, validation, and schema inference."""
import csv
import io
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from backend.config import settings


class ColumnDetail(BaseModel):
    name: str
    dtype: str  # "numeric" | "string" | "boolean"
    unique_count: int
    sample_values: List[Any]


class DatasetInspectionResult(BaseModel):
    is_valid: bool
    format: str
    row_count: int = 0
    columns: List[str] = []
    column_details: List[ColumnDetail] = []
    error: Optional[str] = None


def inspect_dataset_bytes(raw_bytes: bytes, filename: str) -> DatasetInspectionResult:
    """Inspects dataset file bytes, validates format and structure, and extracts schema."""
    # 1. Size check
    if len(raw_bytes) == 0:
        return DatasetInspectionResult(
            is_valid=False,
            format="unknown",
            error="Dataset file is empty",
        )

    if len(raw_bytes) > settings.max_dataset_size_bytes:
        return DatasetInspectionResult(
            is_valid=False,
            format="unknown",
            error=f"Dataset file size ({len(raw_bytes)} bytes) exceeds maximum allowed size ({settings.max_dataset_size_bytes} bytes)",
        )

    # 2. Format detection by filename extension
    lower_filename = filename.lower()
    detected_format = None
    if lower_filename.endswith(".csv"):
        detected_format = "csv"
    elif lower_filename.endswith(".json"):
        detected_format = "json"
    else:
        return DatasetInspectionResult(
            is_valid=False,
            format="unsupported",
            error=f"Unsupported file format for '{filename}'. Allowed formats: {', '.join(settings.allowed_dataset_formats)}",
        )

    # 3. Content parsing
    try:
        if detected_format == "csv":
            return _inspect_csv(raw_bytes)
        elif detected_format == "json":
            return _inspect_json(raw_bytes)
        else:
            return DatasetInspectionResult(
                is_valid=False,
                format=detected_format,
                error=f"Format '{detected_format}' is not supported",
            )
    except Exception as exc:
        return DatasetInspectionResult(
            is_valid=False,
            format=detected_format or "unknown",
            error=f"Failed to parse dataset content: {str(exc)}",
        )


def _inspect_csv(raw_bytes: bytes) -> DatasetInspectionResult:
    # Decode text, handle UTF-8 with BOM
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw_bytes.decode("latin-1")
        except Exception:
            return DatasetInspectionResult(
                is_valid=False,
                format="csv",
                error="CSV file could not be decoded as UTF-8 or Latin-1 text",
            )

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader, None)
    except Exception as e:
        return DatasetInspectionResult(is_valid=False, format="csv", error=f"Corrupt CSV header: {e}")

    if not header or len(header) < 2:
        return DatasetInspectionResult(
            is_valid=False,
            format="csv",
            error="CSV must contain a header row with at least 2 columns (features and target)",
        )

    # Clean header column names
    clean_columns = [col.strip() for col in header]
    if any(not c for c in clean_columns):
        return DatasetInspectionResult(
            is_valid=False,
            format="csv",
            error="CSV contains empty column names in header",
        )

    if len(set(clean_columns)) != len(clean_columns):
        return DatasetInspectionResult(
            is_valid=False,
            format="csv",
            error="CSV contains duplicate column names",
        )

    # Parse rows
    rows: List[List[str]] = []
    expected_cols = len(clean_columns)
    for row_idx, row in enumerate(reader, start=2):
        if not row:
            continue  # skip blank lines
        if len(row) != expected_cols:
            return DatasetInspectionResult(
                is_valid=False,
                format="csv",
                error=f"Row {row_idx} has {len(row)} columns, expected {expected_cols}",
            )
        rows.append(row)

    if len(rows) < 2:
        return DatasetInspectionResult(
            is_valid=False,
            format="csv",
            error=f"CSV must contain at least 2 data rows, found {len(rows)}",
        )

    column_details = _analyze_column_data(clean_columns, rows)

    return DatasetInspectionResult(
        is_valid=True,
        format="csv",
        row_count=len(rows),
        columns=clean_columns,
        column_details=column_details,
    )


def _inspect_json(raw_bytes: bytes) -> DatasetInspectionResult:
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        return DatasetInspectionResult(is_valid=False, format="json", error=f"Invalid JSON: {e}")

    if not isinstance(data, list):
        return DatasetInspectionResult(
            is_valid=False,
            format="json",
            error="JSON dataset must be a list of record objects (rows)",
        )

    if len(data) < 2:
        return DatasetInspectionResult(
            is_valid=False,
            format="json",
            error=f"JSON dataset must contain at least 2 records, found {len(data)}",
        )

    if not isinstance(data[0], dict):
        return DatasetInspectionResult(
            is_valid=False,
            format="json",
            error="JSON records must be dictionaries mapping column names to values",
        )

    columns = list(data[0].keys())
    if len(columns) < 2:
        return DatasetInspectionResult(
            is_valid=False,
            format="json",
            error="JSON records must contain at least 2 fields (features and target)",
        )

    rows: List[List[Any]] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            return DatasetInspectionResult(
                is_valid=False,
                format="json",
                error=f"Record {idx} is not a valid JSON object",
            )
        row = [item.get(col) for col in columns]
        rows.append(row)

    column_details = _analyze_column_data(columns, rows)

    return DatasetInspectionResult(
        is_valid=True,
        format="json",
        row_count=len(rows),
        columns=columns,
        column_details=column_details,
    )


def _analyze_column_data(columns: List[str], rows: List[List[Any]]) -> List[ColumnDetail]:
    details: List[ColumnDetail] = []
    num_rows = len(rows)

    for col_idx, col_name in enumerate(columns):
        values = [row[col_idx] for row in rows]
        # Detect dtype
        is_numeric = True
        unique_vals = set()
        sample_vals = []

        for v in values:
            if v is None or v == "":
                continue
            unique_vals.add(str(v))
            if len(sample_vals) < 5:
                sample_vals.append(v)

            if is_numeric:
                try:
                    float(v)
                except (ValueError, TypeError):
                    is_numeric = False

        dtype = "numeric" if is_numeric else "string"
        details.append(
            ColumnDetail(
                name=col_name,
                dtype=dtype,
                unique_count=len(unique_vals),
                sample_values=sample_vals[:5],
            )
        )

    return details
