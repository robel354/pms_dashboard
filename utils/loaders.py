from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Final

import pandas as pd
import streamlit as st

from utils.config import DATA_DIR, USE_AZURE_STORAGE
from utils.storage import read_csv_content
from utils.transforms import (
    normalize_columns,
    normalize_kobo_grievance_intake,
    normalize_kobo_grievance_resolution,
    normalize_kobo_nursery_batch_intake,
    normalize_kobo_nursery_qaqc,
)

DATASET_REQUIRED_COLUMNS: Final[dict[str, list[str]]] = {
    "recipients.csv": ["recipient_id", "recipient_name", "country", "status", "start_date"],
    "plots.csv": ["plot_id", "recipient_id", "plot_name", "area_ha", "status"],
    "training.csv": ["session_id", "topic", "participants", "completed", "training_date"],
    "documents.csv": ["document_id", "recipient", "document_type", "status", "last_updated"],
    "grievance_intake.csv": ["case_id", "recipient", "category", "status", "opened_on"],
    "grievance_resolution.csv": ["case_id", "resolution_status", "resolved_on", "resolution_notes"],
    "nursery_batch_intake.csv": ["batch_id", "nursery_name", "species", "quantity", "intake_date"],
    "nursery_qaqc.csv": ["inspection_id", "nursery_name", "batch_id", "quality_status", "inspection_date"],
}


@st.cache_data(show_spinner=False)
def _parse_csv_bytes_cached(csv_bytes: bytes) -> pd.DataFrame:
    """Parse raw CSV bytes once and cache the resulting DataFrame."""
    return pd.read_csv(BytesIO(csv_bytes))


@st.cache_data(show_spinner=False)
def _read_excel_cached(path: str, *, sheet_name: str | int | None = 0) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name)

@st.cache_data(show_spinner=False)
def _read_kobo_labels_csv_cached(path: str) -> pd.DataFrame:
    # Kobo "labels" exports commonly use semicolons with quoted fields.
    return pd.read_csv(path, sep=";", quotechar='"', dtype="string", keep_default_na=False)


def _empty_frame(required_columns: list[str] | None = None) -> pd.DataFrame:
    return pd.DataFrame(columns=required_columns or [])


def load_csv_safe(
    file_name: str,
    *,
    required_columns: list[str] | None = None,
    dataset_name: str | None = None,
) -> pd.DataFrame:
    """Load a CSV from the configured storage backend and validate basic shape."""
    label = dataset_name or file_name
    normalized_required = [column.strip().lower() for column in (required_columns or [])]

    try:
        csv_bytes = read_csv_content(file_name)
    except FileNotFoundError:
        st.warning(f"{label} was not found in the configured storage backend. Returning an empty dataset.")
        return _empty_frame(normalized_required)
    except Exception as exc:
        st.warning(f"{label} could not be loaded: {exc}. Returning an empty dataset.")
        return _empty_frame(normalized_required)

    try:
        frame = _parse_csv_bytes_cached(csv_bytes)
    except Exception as exc:
        st.warning(f"{label} could not be parsed as CSV: {exc}. Returning an empty dataset.")
        return _empty_frame(normalized_required)

    normalized_frame = normalize_columns(frame)

    missing_columns = [
        column for column in normalized_required if column not in normalized_frame.columns
    ]
    if missing_columns:
        missing_columns_text = ", ".join(missing_columns)
        st.warning(
            f"{label} is missing required columns: {missing_columns_text}. Returning an empty dataset."
        )
        return _empty_frame(normalized_required)

    return normalized_frame


def _load_dataset(file_name: str) -> pd.DataFrame:
    return load_csv_safe(
        file_name,
        required_columns=DATASET_REQUIRED_COLUMNS[file_name],
        dataset_name=file_name,
    )


def load_recipients() -> pd.DataFrame:
    return _load_dataset("recipients.csv")


def load_plots() -> pd.DataFrame:
    return _load_dataset("plots.csv")


def load_training() -> pd.DataFrame:
    return _load_dataset("training.csv")


def load_documents() -> pd.DataFrame:
    return _load_dataset("documents.csv")


def load_grievance_intake() -> pd.DataFrame:
    # Prefer Kobo-style Excel export when running locally.
    if not USE_AZURE_STORAGE:
        excel_path = (Path(DATA_DIR) / "Grievance Intake Form.xlsx").resolve()
        if excel_path.exists():
            frame = _read_excel_cached(str(excel_path), sheet_name=0)
            return normalize_kobo_grievance_intake(frame)

    return _load_dataset("grievance_intake.csv")


def load_grievance_resolution() -> pd.DataFrame:
    if not USE_AZURE_STORAGE:
        excel_path = (Path(DATA_DIR) / "Grievance Resolution Communication.xlsx").resolve()
        if excel_path.exists():
            frame = _read_excel_cached(str(excel_path), sheet_name=0)
            return normalize_kobo_grievance_resolution(frame)

    return _load_dataset("grievance_resolution.csv")


def load_nursery_batch_intake() -> pd.DataFrame:
    if not USE_AZURE_STORAGE:
        excel_path = (Path(DATA_DIR) / "Nursery Seedling Batch Intake.xlsx").resolve()
        if excel_path.exists():
            parent = _read_excel_cached(str(excel_path), sheet_name="Nursery Seedling Batch Intake")
            agro = _read_excel_cached(str(excel_path), sheet_name="agroforestry_seedlings")
            er = _read_excel_cached(str(excel_path), sheet_name="er_seedlings")
            return normalize_kobo_nursery_batch_intake(parent, agroforestry_frame=agro, er_frame=er)

    return _load_dataset("nursery_batch_intake.csv")


def load_nursery_qaqc() -> pd.DataFrame:
    if not USE_AZURE_STORAGE:
        excel_path = (Path(DATA_DIR) / "Nursery Seedling QAQC.xlsx").resolve()
        if excel_path.exists():
            parent = _read_excel_cached(str(excel_path), sheet_name="Nursery Seedling QA_QC")
            agro = _read_excel_cached(str(excel_path), sheet_name="agroforestry_seedlings")
            er = _read_excel_cached(str(excel_path), sheet_name="ER_seedlings")
            qaqc = normalize_kobo_nursery_qaqc(parent, agroforestry_frame=agro, er_frame=er)

            # Enrich QAQC rows with nursery name where possible (from intake workbook).
            intake_path = (Path(DATA_DIR) / "Nursery Seedling Batch Intake.xlsx").resolve()
            if intake_path.exists() and "batch_id" in qaqc.columns:
                intake_parent = _read_excel_cached(
                    str(intake_path), sheet_name="Nursery Seedling Batch Intake"
                )
                intake_parent = normalize_columns(intake_parent)
                intake_parent = intake_parent.rename(
                    columns={"seedling_supplier": "nursery_name", "batch_id": "batch_id"}
                )
                if "nursery_name" in intake_parent.columns and "batch_id" in intake_parent.columns:
                    lookup = (
                        intake_parent[["batch_id", "nursery_name"]]
                        .dropna(subset=["batch_id"])
                        .drop_duplicates(subset=["batch_id"])
                    )
                    qaqc = qaqc.merge(lookup, on="batch_id", how="left")

            return qaqc

    return _load_dataset("nursery_qaqc.csv")


def load_trees_seedlings() -> pd.DataFrame:
    return load_plots()


def load_farmer_registration() -> pd.DataFrame:
    """Load the Kobo farmer registration + parcel mapping export (labels CSV).

    This dataset is intentionally loaded from the local `data/` directory for MVP use.
    """
    if USE_AZURE_STORAGE:
        st.warning(
            "Farmer registration data is not configured for Azure storage yet. Returning an empty dataset."
        )
        return pd.DataFrame()

    data_dir = Path(DATA_DIR)
    candidates = sorted(
        data_dir.glob("Farmer_Registration_and_Parcel_Mapping_Form*_labels_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        st.warning(
            "Farmer registration export was not found in the data directory. Returning an empty dataset."
        )
        return pd.DataFrame()

    try:
        raw = _read_kobo_labels_csv_cached(str(candidates[0]))
    except Exception as exc:
        st.warning(f"Farmer registration export could not be loaded: {exc}. Returning an empty dataset.")
        return pd.DataFrame()

    return normalize_columns(raw)
