from __future__ import annotations

import pandas as pd
import streamlit as st
from pandas.api.types import is_scalar

from utils.auth import AuthContext
from utils.config import ALLOW_SENSITIVE_UNMASK
from utils.loaders import load_grievance_intake, load_grievance_resolution
from utils.transforms import ensure_columns, join_grievance_data, mask_columns, normalize_yes_no_fields

SENSITIVE_COLUMNS = [
    "complainant_name",
    "complainant_phone",
    "complainant_email",
    "complainant_meeting_place",
    "grievance_description",
    "grievance_photo",
    "grievance_photo_url",
    "grievance_photos",
    "signature",
    "signatures",
    "complainant_signature",
    "fca_scan",
    "fca_scan_url",
]


def _filter_options(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return ["All"]
    options = frame[column].dropna().astype("string").sort_values().unique().tolist()
    return ["All"] + options


def _apply_filters(frame: pd.DataFrame) -> pd.DataFrame:
    filtered = frame.copy()
    filter_columns = st.columns(4)
    filter_mapping = [
        ("grievance_type", "Grievance Type"),
        ("complainant_area", "Complainant Area"),
        ("urgency", "Urgency"),
        ("severity", "Severity"),
    ]

    for index, (column, label) in enumerate(filter_mapping):
        if column not in filtered.columns:
            continue
        selected_value = filter_columns[index].selectbox(label, _filter_options(filtered, column))
        if selected_value != "All":
            filtered = filtered[filtered[column].astype("string") == selected_value].copy()

    return filtered


def _mask_sensitive_fields(frame: pd.DataFrame) -> pd.DataFrame:
    return mask_columns(frame, SENSITIVE_COLUMNS)


def _render_kpis(frame: pd.DataFrame) -> None:
    status_series = frame["status"].astype("string").str.lower() if "status" in frame.columns else pd.Series(dtype="string")
    resolution_series = (
        frame["resolution_status"].astype("string").str.lower()
        if "resolution_status" in frame.columns
        else pd.Series(dtype="string")
    )
    anonymous_series = (
        frame["is_anonymous"].astype("string").str.lower()
        if "is_anonymous" in frame.columns
        else pd.Series(dtype="string")
    )
    follow_up_series = (
        frame["follow_up_required"].astype("string").str.lower()
        if "follow_up_required" in frame.columns
        else pd.Series(dtype="string")
    )

    unresolved_mask = status_series.isin(["open", "unresolved", "in_progress"]) | resolution_series.isin(
        ["open", "unresolved", "in_review", "in_progress"]
    )
    unresolved_count = int(unresolved_mask.sum())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Grievances", len(frame))
    col2.metric("Anonymous Grievances", int(anonymous_series.eq("yes").sum()))
    col3.metric("Follow-up Required", int(follow_up_series.eq("yes").sum()))
    col4.metric("Open / Unresolved", unresolved_count)


def _render_details_panel(frame: pd.DataFrame) -> None:
    st.subheader("Grievance Details")
    if frame.empty:
        st.info("No grievance records are available for the current filters.")
        return

    grievance_column = "grievance_id" if "grievance_id" in frame.columns else "case_id"
    if grievance_column not in frame.columns:
        st.info("No grievance identifier column is available for a detailed view.")
        return

    grievance_ids = frame[grievance_column].dropna().astype("string").tolist()
    if not grievance_ids:
        st.info("No grievance identifiers are available for a detailed view.")
        return

    selected_grievance_id = st.selectbox("Select Grievance", grievance_ids)
    selected_record = frame[frame[grievance_column].astype("string") == selected_grievance_id]
    if selected_record.empty:
        st.info("The selected grievance could not be found.")
        return

    detail_frame = selected_record.T.reset_index()
    detail_frame.columns = ["Field", "Value"]
    # Streamlit serializes dataframes through Arrow. Kobo exports can contain mixed
    # object types (strings, timestamps, numbers, lists), so we render values as text.
    def _safe_text(value: object) -> str:
        if value is None:
            return ""
        if is_scalar(value) and pd.isna(value):
            return ""
        return str(value)

    detail_frame["Value"] = detail_frame["Value"].apply(_safe_text)
    st.dataframe(detail_frame, use_container_width=True, hide_index=True)


def _build_display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    preferred_columns = [
        "grievance_id",
        "recipient_id",
        "grievance_type",
        "complainant_area",
        "urgency",
        "severity",
        "is_anonymous",
        "follow_up_required",
        "status",
        "resolution_status",
        "opened_on",
        "resolved_on",
    ]
    visible_columns = [column for column in preferred_columns if column in frame.columns]
    return frame[visible_columns].copy() if visible_columns else frame.copy()


def render(auth_context: AuthContext) -> None:
    """Render the joined grievance intake and resolution view for internal review."""
    intake = load_grievance_intake()
    resolution = load_grievance_resolution()
    joined_frame = join_grievance_data(intake, resolution)
    joined_frame = ensure_columns(
        joined_frame,
        [
            "grievance_id",
            "grievance_type",
            "complainant_area",
            "urgency",
            "severity",
            "is_anonymous",
            "follow_up_required",
            "complainant_name",
            "complainant_phone",
            "complainant_email",
            "complainant_meeting_place",
            "grievance_description",
            "grievance_photo",
            "grievance_photo_url",
            "grievance_photos",
            "signature",
            "signatures",
            "complainant_signature",
            "fca_scan",
            "fca_scan_url",
        ],
    )
    joined_frame = normalize_yes_no_fields(joined_frame, ["is_anonymous", "follow_up_required"])

    st.header("Grievances")
    st.caption(f"Environment: `{auth_context.environment}`")

    if joined_frame.empty:
        st.info(
            "Grievance intake and resolution data have not been provided yet. Add `grievance_intake.csv` and `grievance_resolution.csv` to populate this tab."
        )
        return

    filtered_frame = _apply_filters(joined_frame)
    _render_kpis(filtered_frame)

    st.subheader("Grievance Log")
    if filtered_frame.empty:
        st.info("No grievances matched the current filters. Try clearing one or more filters.")
        return

    allow_unmask = bool(ALLOW_SENSITIVE_UNMASK and auth_context.is_authorized)
    show_sensitive = False
    if allow_unmask:
        show_sensitive = st.checkbox(
            "Show sensitive grievance details",
            value=False,
            help="Off by default. Enables viewing complainant details, descriptions, and media references.",
        )

    masked_frame = filtered_frame if show_sensitive else _mask_sensitive_fields(filtered_frame)
    display_frame = _build_display_frame(masked_frame)
    st.dataframe(display_frame, use_container_width=True, hide_index=True)

    with st.expander("Selected Grievance Details", expanded=False):
        _render_details_panel(masked_frame)

    st.caption(
        "Personal details, grievance descriptions, photos, signatures, and scan references are hidden by default in this internal dashboard view."
    )
