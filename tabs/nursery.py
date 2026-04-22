from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import AuthContext
from utils.loaders import load_nursery_batch_intake, load_nursery_qaqc
from utils.transforms import ensure_columns, summarize_nursery_batch_metrics


def _safe_numeric_sum(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns or frame.empty:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _filter_options(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return ["All"]
    options = frame[column].dropna().astype("string").sort_values().unique().tolist()
    return ["All"] + options


def _apply_filters(batch_frame: pd.DataFrame) -> pd.DataFrame:
    filtered = batch_frame.copy()
    filter_columns = st.columns(3)
    filter_mapping = [
        ("batch_id", "Batch ID"),
        ("species", "Species"),
        ("intended_project_activity", "Intended Project Activity"),
    ]

    for index, (column, label) in enumerate(filter_mapping):
        if column not in filtered.columns:
            continue
        selected_value = filter_columns[index].selectbox(
            label,
            _filter_options(filtered, column),
            key=f"nursery_filter_{column}",
        )
        if selected_value != "All":
            filtered = filtered[filtered[column].astype("string") == selected_value].copy()

    return filtered


def _filter_qaqc_by_batches(qaqc_frame: pd.DataFrame, batch_frame: pd.DataFrame) -> pd.DataFrame:
    if qaqc_frame.empty:
        return qaqc_frame.copy()
    if batch_frame.empty or "batch_id" not in batch_frame.columns or "batch_id" not in qaqc_frame.columns:
        return qaqc_frame.iloc[0:0].copy()

    batch_ids = batch_frame["batch_id"].dropna().astype("string").unique().tolist()
    if not batch_ids:
        return qaqc_frame.iloc[0:0].copy()

    return qaqc_frame[qaqc_frame["batch_id"].astype("string").isin(batch_ids)].copy()


def _render_species_breakdown(batch_frame: pd.DataFrame) -> None:
    st.subheader("Species Breakdown")
    if batch_frame.empty:
        st.info("No nursery batch records are available for the current filters.")
        return

    if "species" not in batch_frame.columns:
        st.info("Species data is not available in the nursery batch intake file.")
        return

    quantity_column = "quantity" if "quantity" in batch_frame.columns else None
    if quantity_column is None:
        st.info("Quantity data is not available for species summarization.")
        return

    species_breakdown = (
        batch_frame.assign(_quantity=pd.to_numeric(batch_frame[quantity_column], errors="coerce").fillna(0))
        .groupby("species", dropna=False)
        .agg(batch_count=("batch_id", "nunique"), total_seedlings=("_quantity", "sum"))
        .reset_index()
        .sort_values("total_seedlings", ascending=False)
    )
    st.dataframe(species_breakdown, use_container_width=True, hide_index=True)


def _render_batch_summary(batch_frame: pd.DataFrame, qaqc_frame: pd.DataFrame) -> None:
    st.subheader("Batch Summary")
    if batch_frame.empty:
        st.info("No nursery batch records matched the selected filters.")
        return

    summary_frame = summarize_nursery_batch_metrics(batch_frame, qaqc_frame)
    st.dataframe(summary_frame, use_container_width=True, hide_index=True)


def _render_qaqc_table(qaqc_frame: pd.DataFrame) -> None:
    st.subheader("QA/QC Findings")
    if qaqc_frame.empty:
        st.info("No QA/QC findings are available for the current filters.")
        return

    preferred_columns = [
        "inspection_id",
        "batch_id",
        "nursery_name",
        "species",
        "quality_status",
        "damaged_seedlings",
        "diseased_seedlings",
        "dead_seedlings",
        "inspection_date",
        "notes",
    ]
    visible_columns = [column for column in preferred_columns if column in qaqc_frame.columns]
    display_frame = qaqc_frame[visible_columns].copy() if visible_columns else qaqc_frame.copy()
    st.dataframe(display_frame, use_container_width=True, hide_index=True)


def render(auth_context: AuthContext) -> None:
    """Render nursery intake summaries and QA/QC findings with shared filters."""
    batch_frame = ensure_columns(
        load_nursery_batch_intake(),
        [
            "batch_id",
            "nursery_name",
            "species",
            "quantity",
            "intended_project_activity",
            "intake_date",
        ],
    )
    qaqc_frame = ensure_columns(
        load_nursery_qaqc(),
        [
            "inspection_id",
            "batch_id",
            "nursery_name",
            "species",
            "quality_status",
            "damaged_seedlings",
            "diseased_seedlings",
            "dead_seedlings",
            "inspection_date",
            "notes",
        ],
    )

    st.header("Nursery")
    st.caption(f"Signed in as: `{auth_context.user_display_name}`")

    if batch_frame.empty and qaqc_frame.empty:
        st.info(
            "Nursery batch intake and QA/QC data are not available yet. Add Kobo exports "
            "`Nursery Seedling Batch Intake.xlsx` and `Nursery Seedling QAQC.xlsx` (or the CSV fallbacks) to populate this tab."
        )
        return

    view_mode = st.radio(
        "View",
        options=["Batch-Level View", "QA/QC-Level View"],
        horizontal=True,
        key="nursery_view_mode",
    )

    filtered_batches = _apply_filters(batch_frame)
    filtered_qaqc = _filter_qaqc_by_batches(qaqc_frame, filtered_batches)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Batches", int(filtered_batches["batch_id"].dropna().nunique()) if "batch_id" in filtered_batches.columns else 0)
    col2.metric("Total Seedlings", f"{_safe_numeric_sum(filtered_batches, 'quantity'):,}")
    col3.metric("Damaged Seedlings", f"{_safe_numeric_sum(filtered_qaqc, 'damaged_seedlings'):,}")
    col4.metric("Diseased Seedlings", f"{_safe_numeric_sum(filtered_qaqc, 'diseased_seedlings'):,}")
    col5.metric("Dead Seedlings", f"{_safe_numeric_sum(filtered_qaqc, 'dead_seedlings'):,}")

    if view_mode == "Batch-Level View":
        _render_batch_summary(filtered_batches, filtered_qaqc)
        _render_species_breakdown(filtered_batches)
        _render_qaqc_table(filtered_qaqc)
        return

    _render_batch_summary(filtered_batches, filtered_qaqc)
    _render_species_breakdown(filtered_batches)
    _render_qaqc_table(filtered_qaqc)
