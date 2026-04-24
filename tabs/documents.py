from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import AuthContext
from utils.config import ENTITY_NAME
from utils.loaders import load_documents
from utils.storage import has_document_reference, resolve_document_access_url
from utils.transforms import format_column_name, ui_safe_frame


def _safe_filter_options(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    return frame[column].dropna().astype("string").sort_values().unique().tolist()


def _normalize_signed_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize FCA signed values into consistent Yes/No labels."""
    normalized = frame.copy()
    if "fca_signed" not in normalized.columns:
        normalized["fca_signed"] = pd.NA
        return normalized

    signed_map = {
        "yes": "Yes",
        "y": "Yes",
        "true": "Yes",
        "1": "Yes",
        "no": "No",
        "n": "No",
        "false": "No",
        "0": "No",
    }
    normalized["fca_signed"] = (
        normalized["fca_signed"]
        .astype("string")
        .str.strip()
        .str.lower()
        .map(signed_map)
        .fillna(normalized["fca_signed"])
    )
    return normalized


def _build_document_display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display_frame = frame.copy()

    display_frame["document_reference_available"] = (
        display_frame["file_url"].apply(has_document_reference)
        if "file_url" in display_frame.columns
        else False
    )
    display_frame["photo_reference_available"] = (
        display_frame["photo_url"].apply(has_document_reference)
        if "photo_url" in display_frame.columns
        else False
    )
    display_frame["view_document"] = (
        display_frame["file_url"].apply(resolve_document_access_url)
        if "file_url" in display_frame.columns
        else pd.NA
    )

    preferred_columns = [
        "document_id",
        "recipient_id",
        "plot_id",
        "recipient",
        "document_type",
        "status",
        "fca_signed",
        "document_reference_available",
        "photo_reference_available",
        "last_updated",
        "view_document",
    ]
    visible_columns = [column for column in preferred_columns if column in display_frame.columns]
    return display_frame[visible_columns] if visible_columns else display_frame


def _build_column_config(display_frame: pd.DataFrame) -> dict[str, object]:
    column_config: dict[str, object] = {}
    view_col = format_column_name(
        "view_document",
        overrides={"view_document": "View Document"},
    )
    if view_col in display_frame.columns:
        column_config[view_col] = st.column_config.LinkColumn(
            "View Document",
            display_text="Open",
        )
    doc_on_file_col = format_column_name(
        "document_reference_available",
        overrides={"document_reference_available": "Document On File"},
    )
    if doc_on_file_col in display_frame.columns:
        column_config[doc_on_file_col] = st.column_config.CheckboxColumn(
            "Document On File",
            disabled=True,
        )
    photo_on_file_col = format_column_name(
        "photo_reference_available",
        overrides={"photo_reference_available": "Photo On File"},
    )
    if photo_on_file_col in display_frame.columns:
        column_config[photo_on_file_col] = st.column_config.CheckboxColumn(
            "Photo On File",
            disabled=True,
        )
    return column_config


def _render_document_links(frame: pd.DataFrame) -> None:
    st.subheader("Document Access")

    if frame.empty:
        st.info("No document records are available for the current selection.")
        return

    if "file_url" not in frame.columns:
        st.info("No private document reference column is available yet.")
        return

    linked_documents = frame[frame["file_url"].notna() & frame["file_url"].astype("string").str.strip().ne("")].copy()
    if linked_documents.empty:
        st.info("No secure document references are available for the current selection.")
        return

    links_available = False
    for _, row in linked_documents.iterrows():
        access_url = resolve_document_access_url(row.get("file_url"))
        if not access_url:
            continue
        document_id = row.get("document_id", "Document")
        document_type = row.get("document_type", "File")
        st.markdown(f"- [{document_id} - {document_type}]({access_url})")
        links_available = True

    if not links_available:
        st.info("No document links are available for the current selection.")


def render(auth_context: AuthContext) -> None:
    """Render document status, access references, and the filtered library view."""
    frame = _normalize_signed_values(load_documents())

    st.header("Documents")
    st.caption(f"User context: `{auth_context.user_display_name}`")

    if frame.empty:
        st.info("Document data is not available yet. Add `documents.csv` to populate this tab.")
        return

    filtered_frame = frame.copy()

    filter_columns = st.columns(2)
    if "recipient_id" in frame.columns:
        recipient_options = ["All"] + _safe_filter_options(frame, "recipient_id")
        selected_recipient = filter_columns[0].selectbox(
            f"{ENTITY_NAME} ID",
            recipient_options,
            key="documents_recipient_id",
        )
        if selected_recipient != "All":
            filtered_frame = filtered_frame[
                filtered_frame["recipient_id"].astype("string") == selected_recipient
            ].copy()
    elif "recipient" in frame.columns:
        recipient_options = ["All"] + _safe_filter_options(frame, "recipient")
        selected_recipient_name = filter_columns[0].selectbox(
            ENTITY_NAME,
            recipient_options,
            key="documents_recipient_name",
        )
        if selected_recipient_name != "All":
            filtered_frame = filtered_frame[
                filtered_frame["recipient"].astype("string") == selected_recipient_name
            ].copy()

    if "plot_id" in frame.columns:
        plot_options = ["All"] + _safe_filter_options(frame, "plot_id")
        selected_plot = filter_columns[1].selectbox(
            "Plot ID",
            plot_options,
            key="documents_plot_id",
        )
        if selected_plot != "All":
            filtered_frame = filtered_frame[
                filtered_frame["plot_id"].astype("string") == selected_plot
            ].copy()

    status_series = (
        filtered_frame["status"].astype("string").str.lower()
        if "status" in filtered_frame.columns
        else pd.Series(dtype="string")
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Documents", len(filtered_frame))
    col2.metric("Approved", int(status_series.eq("approved").sum()))
    col3.metric("Pending", int(status_series.eq("pending").sum()))

    if "fca_signed" in filtered_frame.columns:
        signed_count = int(filtered_frame["fca_signed"].astype("string").str.lower().eq("yes").sum())
        st.caption(f"FCA signed documents in view: `{signed_count}`")

    _render_document_links(filtered_frame)

    st.subheader("Document Library")
    if filtered_frame.empty:
        st.info("No document records matched the current filters. Try clearing one or more filters.")
        return

    display_frame = _build_document_display_frame(filtered_frame)
    display_frame = ui_safe_frame(
        display_frame,
        column_overrides={
            "recipient_id": f"{ENTITY_NAME} ID",
            "recipient": ENTITY_NAME,
            "view_document": "View Document",
            "document_reference_available": "Document On File",
            "photo_reference_available": "Photo On File",
        },
        rename_columns=True,
    )
    st.dataframe(
        display_frame,
        use_container_width=True,
        hide_index=True,
        column_config=_build_column_config(display_frame),
    )

    st.caption(
        "If a document URL exists, it is shown as a clickable link for demo viewing."
    )
