from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

MASKED_VALUE = "[Hidden]"


def clean_column_name(column_name: object) -> str:
    """Convert a raw header into a normalized snake_case column name."""
    cleaned = str(column_name).strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    return cleaned.strip("_")


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the frame with normalized column names."""
    normalized = frame.copy()
    normalized.columns = [clean_column_name(column) for column in normalized.columns]
    return normalized


def ensure_columns(frame: pd.DataFrame, columns: Iterable[str], default: object = pd.NA) -> pd.DataFrame:
    """Ensure expected columns exist so downstream code can fail gracefully."""
    normalized = normalize_columns(frame)
    for column in columns:
        if column not in normalized.columns:
            normalized[column] = default
    return normalized


def normalize_yes_no_fields(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Normalize common boolean-like text values into Yes/No labels."""
    normalized = frame.copy()
    value_map = {
        "y": "Yes",
        "yes": "Yes",
        "true": "Yes",
        "1": "Yes",
        "n": "No",
        "no": "No",
        "false": "No",
        "0": "No",
    }

    for column in columns:
        if column not in normalized.columns:
            normalized[column] = pd.NA
            continue

        normalized[column] = (
            normalized[column]
            .astype("string")
            .str.strip()
            .str.lower()
            .map(value_map)
            .fillna(normalized[column])
        )

    return normalized


def parse_lat_long_columns(
    frame: pd.DataFrame,
    latitude_column: str = "latitude",
    longitude_column: str = "longitude",
) -> pd.DataFrame:
    """Safely coerce latitude and longitude fields into usable numeric columns."""
    normalized = frame.copy()

    if latitude_column not in normalized.columns:
        normalized[latitude_column] = pd.Series(dtype="float64")
    if longitude_column not in normalized.columns:
        normalized[longitude_column] = pd.Series(dtype="float64")

    normalized[latitude_column] = pd.to_numeric(normalized[latitude_column], errors="coerce")
    normalized[longitude_column] = pd.to_numeric(normalized[longitude_column], errors="coerce")

    normalized.loc[
        ~normalized[latitude_column].between(-90, 90, inclusive="both"), latitude_column
    ] = pd.NA
    normalized.loc[
        ~normalized[longitude_column].between(-180, 180, inclusive="both"), longitude_column
    ] = pd.NA

    return normalized


def mask_columns(
    frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    mask_value: str = MASKED_VALUE,
    mask_tokens: Iterable[str] = ("photo", "signature", "scan"),
    token_exceptions: Iterable[str] = ("is_anonymous",),
) -> pd.DataFrame:
    """Return a copy with sensitive columns masked.

    - Masks explicit columns in `columns` when present
    - Also masks any columns containing `mask_tokens` (case-insensitive), except `token_exceptions`
    """
    masked = frame.copy()

    explicit = {str(column).strip().lower() for column in columns if str(column).strip()}
    for column in list(masked.columns):
        lowered = str(column).strip().lower()
        if lowered in explicit:
            masked[column] = mask_value
            continue

        if lowered in {str(exc).strip().lower() for exc in token_exceptions}:
            continue

        if any(token in lowered for token in mask_tokens):
            masked[column] = mask_value

    return masked


def _to_id_token(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = re.split(r"[^a-zA-Z0-9]+", raw)
    parts = [part for part in parts if part]
    if not parts:
        return ""
    first, *rest = parts
    return first[:1].upper() + first[1:] + "".join(part[:1].upper() + part[1:] for part in rest)


def _grievance_type_token(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = clean_column_name(raw)
    # Match the common Kobo dummy export style seen in the provided file.
    if normalized == "land_issue":
        return "Land"
    return normalized


def build_grievance_id(
    frame: pd.DataFrame,
    *,
    area_column: str = "complainant_area",
    date_column: str = "date_time",
    type_column: str = "grievance_type",
) -> pd.Series:
    """Derive a stable grievance identifier when Kobo exports don't provide one.

    Format: <AreaToken>-<YYYYMMDD>-<TypeToken>
    """
    area_token = frame.get(area_column, pd.Series(dtype="string")).apply(_to_id_token)
    dates = pd.to_datetime(frame.get(date_column, pd.Series(dtype="string")), errors="coerce")
    date_token = dates.dt.strftime("%Y%m%d").fillna("")
    type_token = frame.get(type_column, pd.Series(dtype="string")).apply(_grievance_type_token)

    composed = area_token.astype("string") + "-" + date_token.astype("string") + "-" + type_token.astype("string")
    composed = composed.str.strip("-")
    composed = composed.where(composed.str.len().gt(0), pd.NA)
    return composed


def normalize_kobo_grievance_intake(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize Kobo grievance intake exports into dashboard-friendly columns."""
    normalized = normalize_columns(frame)

    # Map Kobo field names → dashboard field names
    rename_map = {
        "anonymous": "is_anonymous",
        "grievance_urgency": "urgency",
        "grievance_severity": "severity",
        # Prefer the actual form datetime when present; fall back to submission time later.
        "date_time": "opened_on",
        "grievance_photo_url": "grievance_photo_url",
        "issue_photograph_url": "grievance_photo_url",
        "issue_photograph": "grievance_photo",
        "_id": "case_id",
    }
    normalized = normalized.rename(columns={k: v for k, v in rename_map.items() if k in normalized.columns})

    if "opened_on" not in normalized.columns and "_submission_time" in normalized.columns:
        normalized = normalized.rename(columns={"_submission_time": "opened_on"})

    if "grievance_id" not in normalized.columns or normalized["grievance_id"].isna().all():
        normalized["grievance_id"] = build_grievance_id(normalized, date_column="opened_on")

    # Kobo exports include `_status` like `submitted_via_web` which is not a grievance lifecycle
    # status. Default to `open` for intake records; resolution data can mark it resolved later.
    normalized["status"] = "open"

    return normalized


def normalize_kobo_grievance_resolution(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize Kobo grievance resolution exports into dashboard-friendly columns."""
    normalized = normalize_columns(frame)

    rename_map = {
        "resolution_response_date": "resolved_on",
        "resolution_outcome": "resolution_status",
        "feedback_description": "resolution_notes",
        "follow_up_required": "follow_up_required",
        "grievance_resolution_signature": "signature",
        "grievance_resolution_signature_url": "signature_url",
    }
    normalized = normalized.rename(columns={k: v for k, v in rename_map.items() if k in normalized.columns})

    # Keep existing `grievance_id` from Kobo; fall back to case_id if needed.
    if "case_id" not in normalized.columns and "_id" in normalized.columns:
        normalized = normalized.rename(columns={"_id": "case_id"})

    return normalized


def _first_present_column(frame: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None


def normalize_kobo_nursery_batch_intake(
    parent_frame: pd.DataFrame,
    *,
    agroforestry_frame: pd.DataFrame | None = None,
    er_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Flatten Kobo nursery batch intake export into one row per batch/species."""
    parent = normalize_columns(parent_frame)
    parent = parent.rename(
        columns={
            "id": "submission_id",
            "batch_id": "batch_id",
            "seedling_supplier": "nursery_name",
            "receipt_date": "intake_date",
            "intended_project_activity": "intended_project_activity",
            "place_of_origin": "place_of_origin",
        }
    )

    # Ensure join keys exist
    if "submission_id" not in parent.columns and "id" in parent.columns:
        parent["submission_id"] = parent["id"]

    rows: list[pd.DataFrame] = []

    def _from_repeat(
        repeat_raw: pd.DataFrame,
        *,
        species_candidates: Iterable[str],
        quantity_candidates: Iterable[str],
        activity_label: str,
    ) -> None:
        repeat = normalize_columns(repeat_raw)
        repeat = repeat.rename(columns={"_submission__id": "submission_id"})
        if "submission_id" not in repeat.columns:
            return

        species_col = _first_present_column(repeat, species_candidates)
        qty_col = _first_present_column(repeat, quantity_candidates)
        if not species_col or not qty_col:
            return

        flat = repeat[["submission_id", species_col, qty_col]].copy()
        flat = flat.rename(columns={species_col: "species", qty_col: "quantity"})
        flat["intended_project_activity"] = activity_label
        rows.append(flat)

    if agroforestry_frame is not None and not agroforestry_frame.empty:
        _from_repeat(
            agroforestry_frame,
            species_candidates=("agroforestry_species", "what_agroforestry_species_are_being_sampled"),
            quantity_candidates=("af_total_number_per_species", "how_many_living_seedlings_are_there"),
            activity_label="Agroforestry",
        )

    if er_frame is not None and not er_frame.empty:
        _from_repeat(
            er_frame,
            species_candidates=("er_species", "what_ecosystem_restoration_species_are_being_sampled"),
            quantity_candidates=("er_species_number", "how_many_living_seedlings_are_there"),
            activity_label="Ecosystem Restoration",
        )

    if not rows:
        # Fall back to one row per parent submission (no species breakdown).
        fallback = parent.copy()
        fallback["species"] = pd.NA
        fallback["quantity"] = pd.NA
        return fallback[
            [c for c in ["batch_id", "nursery_name", "species", "quantity", "intended_project_activity", "intake_date"] if c in fallback.columns]
        ].copy()

    combined = pd.concat(rows, ignore_index=True)
    merged = combined.merge(
        parent[["submission_id", "batch_id", "nursery_name", "intake_date", "place_of_origin"]].copy(),
        on="submission_id",
        how="left",
    )

    # If parent already contains intended activity (e.g. SALM_ER), keep it as additional context.
    if "intended_project_activity" in parent.columns:
        merged = merged.merge(
            parent[["submission_id", "intended_project_activity"]].rename(
                columns={"intended_project_activity": "intended_project_activity_source"}
            ),
            on="submission_id",
            how="left",
        )

    return merged


def normalize_kobo_nursery_qaqc(
    parent_frame: pd.DataFrame,
    *,
    agroforestry_frame: pd.DataFrame | None = None,
    er_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Flatten Kobo nursery QA/QC export into one row per inspection/species sample."""
    parent = normalize_columns(parent_frame)
    parent = parent.rename(
        columns={
            "id": "inspection_id",
            "batch_id": "batch_id",
            "inspection_date_and_time": "inspection_date",
            "inspector_id": "inspector_id",
            "intended_project_activity": "intended_project_activity",
        }
    )

    # Normalized forms sometimes preserve original casing in the parent sheet; cover both.
    if "batch_id" not in parent.columns:
        parent = parent.rename(columns={"batch_id": "batch_id"})

    rows: list[pd.DataFrame] = []

    def _safe_numeric(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce").fillna(0)

    def _from_repeat(
        repeat_raw: pd.DataFrame,
        *,
        species_candidates: Iterable[str],
        dead_candidates: Iterable[str],
        diseased_candidates: Iterable[str],
        damaged_candidates: Iterable[str],
        activity_label: str,
    ) -> None:
        repeat = normalize_columns(repeat_raw)
        # Kobo repeat exports are often flattened with `submission_id` columns.
        if "submission_id" in repeat.columns:
            repeat["inspection_id"] = repeat["submission_id"]
        else:
            repeat = repeat.rename(columns={"_submission__id": "inspection_id"})
        if "inspection_id" not in repeat.columns:
            return

        species_col = _first_present_column(repeat, species_candidates)
        dead_col = _first_present_column(repeat, dead_candidates)
        diseased_col = _first_present_column(repeat, diseased_candidates)
        damaged_col = _first_present_column(repeat, damaged_candidates)
        if not species_col:
            return

        flat = repeat[["inspection_id", species_col]].copy()
        flat = flat.rename(columns={species_col: "species"})
        flat["dead_seedlings"] = _safe_numeric(repeat[dead_col]) if dead_col else 0
        flat["diseased_seedlings"] = _safe_numeric(repeat[diseased_col]) if diseased_col else 0
        flat["damaged_seedlings"] = _safe_numeric(repeat[damaged_col]) if damaged_col else 0
        flat["intended_project_activity"] = activity_label

        issue_total = flat[["dead_seedlings", "diseased_seedlings", "damaged_seedlings"]].sum(axis=1)
        flat["quality_status"] = issue_total.gt(0).map({True: "fail", False: "pass"})
        flat["notes"] = pd.NA
        rows.append(flat)

    if agroforestry_frame is not None and not agroforestry_frame.empty:
        _from_repeat(
            agroforestry_frame,
            species_candidates=("what_agroforestry_species_are_being_sampled", "agroforestry_species"),
            dead_candidates=("how_many_dead_seedlings_are_there", "af_visibly_dead_number"),
            diseased_candidates=("how_many_are_showing_signs_of_disease", "af_disease_number"),
            damaged_candidates=("how_many_seedlings_look_visibly_damaged", "af_visibly_damaged_number"),
            activity_label="Agroforestry",
        )

    if er_frame is not None and not er_frame.empty:
        _from_repeat(
            er_frame,
            species_candidates=("what_ecosystem_restoration_species_are_being_sampled", "er_species"),
            dead_candidates=("how_many_dead_seedlings_are_there", "er_visibly_dead_number", "visibly_dead_number_2"),
            diseased_candidates=("how_many_are_showing_signs_of_disease", "er_disease_number", "disease_number_2"),
            damaged_candidates=("how_many_seedlings_look_visibly_damaged", "er_visibly_damaged_number", "visibly_damaged_number_2"),
            activity_label="Ecosystem Restoration",
        )

    if not rows:
        fallback = parent.copy()
        fallback["species"] = pd.NA
        fallback["dead_seedlings"] = 0
        fallback["diseased_seedlings"] = 0
        fallback["damaged_seedlings"] = 0
        fallback["quality_status"] = pd.NA
        fallback["notes"] = pd.NA
        return fallback[
            [
                c
                for c in [
                    "inspection_id",
                    "batch_id",
                    "species",
                    "quality_status",
                    "damaged_seedlings",
                    "diseased_seedlings",
                    "dead_seedlings",
                    "inspection_date",
                    "notes",
                ]
                if c in fallback.columns
            ]
        ].copy()

    combined = pd.concat(rows, ignore_index=True)
    merged = combined.merge(
        parent[["inspection_id", "batch_id", "inspection_date", "inspector_id"]].copy(),
        on="inspection_id",
        how="left",
    )

    return merged


def join_grievance_data(
    grievance_intake: pd.DataFrame, grievance_resolution: pd.DataFrame
) -> pd.DataFrame:
    """Join grievance intake and resolution data using the best available ID."""
    intake = ensure_columns(
        normalize_columns(grievance_intake),
        ["grievance_id", "case_id", "recipient", "category", "status", "opened_on"],
    )
    resolution = ensure_columns(
        normalize_columns(grievance_resolution),
        ["grievance_id", "case_id", "resolution_status", "resolved_on", "resolution_notes"],
    )

    intake["grievance_id"] = intake["grievance_id"].fillna(intake["case_id"])
    resolution["grievance_id"] = resolution["grievance_id"].fillna(resolution["case_id"])

    if intake.empty and resolution.empty:
        return pd.DataFrame(
            columns=[
                "grievance_id",
                "recipient",
                "category",
                "status",
                "opened_on",
                "resolution_status",
                "resolved_on",
                "resolution_notes",
            ]
        )

    merged = intake.merge(
        resolution[
            ["grievance_id", "resolution_status", "resolved_on", "resolution_notes"]
        ],
        on="grievance_id",
        how="left",
    )
    return merged


def summarize_nursery_batch_metrics(
    nursery_batch_intake: pd.DataFrame, nursery_qaqc: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Summarize nursery intake and inspection results by nursery."""
    batch_frame = ensure_columns(
        normalize_columns(nursery_batch_intake),
        ["batch_id", "nursery_name", "species", "quantity", "intake_date"],
    )

    if batch_frame.empty:
        return pd.DataFrame(
            columns=[
                "nursery_name",
                "batch_count",
                "total_quantity",
                "species_count",
                "passing_inspections",
                "failing_inspections",
            ]
        )

    batch_frame["quantity"] = pd.to_numeric(batch_frame["quantity"], errors="coerce").fillna(0)
    summary = (
        batch_frame.groupby("nursery_name", dropna=False)
        .agg(
            batch_count=("batch_id", "nunique"),
            total_quantity=("quantity", "sum"),
            species_count=("species", "nunique"),
        )
        .reset_index()
    )

    if nursery_qaqc is not None:
        qaqc_frame = ensure_columns(
            normalize_columns(nursery_qaqc),
            ["inspection_id", "nursery_name", "batch_id", "quality_status"],
        )
        quality = qaqc_frame["quality_status"].astype("string").str.strip().str.lower()
        qaqc_frame["passing_inspections"] = quality.isin(["pass", "passed", "ok", "approved"]).astype(int)
        qaqc_frame["failing_inspections"] = quality.isin(["fail", "failed", "rejected"]).astype(int)

        qaqc_summary = (
            qaqc_frame.groupby("nursery_name", dropna=False)
            .agg(
                passing_inspections=("passing_inspections", "sum"),
                failing_inspections=("failing_inspections", "sum"),
            )
            .reset_index()
        )
        summary = summary.merge(qaqc_summary, on="nursery_name", how="left")

    for column in ["passing_inspections", "failing_inspections"]:
        if column not in summary.columns:
            summary[column] = 0
        summary[column] = summary[column].fillna(0).astype(int)

    summary["batch_count"] = summary["batch_count"].fillna(0).astype(int)
    summary["species_count"] = summary["species_count"].fillna(0).astype(int)
    summary["total_quantity"] = summary["total_quantity"].fillna(0)
    return summary
