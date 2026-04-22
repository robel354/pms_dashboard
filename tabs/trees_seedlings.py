from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import AuthContext
from utils.loaders import load_nursery_batch_intake, load_recipients, load_trees_seedlings


def _numeric_sum(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns or frame.empty:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _filter_records_for_view(
    frame: pd.DataFrame, view_mode: str, recipient_id: str | None = None
) -> pd.DataFrame:
    if frame.empty or view_mode == "All Recipients":
        return frame.copy()

    if recipient_id and "recipient_id" in frame.columns:
        return frame[frame["recipient_id"].astype("string") == recipient_id].copy()

    return frame.iloc[0:0].copy()


def _render_species_breakdown(frame: pd.DataFrame) -> None:
    st.subheader("Species Breakdown")

    if frame.empty:
        st.info("No tree or seedling records are available for this view.")
        return

    species_column = next(
        (column for column in ["species", "tree_species", "seedling_species"] if column in frame.columns),
        None,
    )
    if not species_column:
        st.info("Species data is not available in the current dataset.")
        return

    quantity_column = next(
        (
            column
            for column in ["seedlings_distributed", "trees_received", "trees_planted", "quantity"]
            if column in frame.columns
        ),
        None,
    )
    if not quantity_column:
        st.info("No quantity column is available to summarize species.")
        return

    breakdown = (
        frame.assign(
            _quantity=pd.to_numeric(frame[quantity_column], errors="coerce").fillna(0)
        )
        .groupby(species_column, dropna=False)["_quantity"]
        .sum()
        .reset_index()
        .rename(columns={species_column: "species", "_quantity": "total"})
        .sort_values("total", ascending=False)
    )

    st.dataframe(breakdown, use_container_width=True, hide_index=True)


def _render_charts(frame: pd.DataFrame) -> None:
    st.subheader("Charts")

    metric_columns = [
        column
        for column in ["trees_received", "trees_planted", "seedlings_distributed", "er_planting_count"]
        if column in frame.columns
    ]
    if frame.empty or not metric_columns:
        st.info("Not enough data is available to plot trees and seedlings charts.")
        return

    totals = {
        column.replace("_", " ").title(): pd.to_numeric(frame[column], errors="coerce").fillna(0).sum()
        for column in metric_columns
    }
    totals = {label: value for label, value in totals.items() if value > 0}
    if not totals:
        st.info("Chart data is available structurally, but all totals are currently zero.")
        return

    chart_frame = (
        pd.DataFrame({"metric": list(totals.keys()), "total": list(totals.values())})
        .sort_values("total", ascending=False)
        .set_index("metric")
    )
    st.bar_chart(chart_frame, y="total")


def render(auth_context: AuthContext) -> None:
    """Render high-level trees and seedlings totals with optional recipient filtering."""
    recipients = load_recipients()
    field_frame = load_trees_seedlings()
    nursery_frame = load_nursery_batch_intake()

    st.header("Trees & Seedlings")
    st.caption(f"Data source: `{auth_context.environment}`")

    source = st.radio(
        "Data source",
        options=["Field plots", "Nursery intake (Kobo)"],
        horizontal=True,
        key="trees_seedlings_data_source",
    )

    if source == "Nursery intake (Kobo)":
        frame = nursery_frame
        if frame.empty:
            st.info(
                "Nursery intake data is not available yet. Add `Nursery Seedling Batch Intake.xlsx` to populate this tab."
            )
            return

        st.caption(
            "Showing seedling batches received into nurseries. Recipient-level filtering is not available for this dataset."
        )

        total_seedlings = _numeric_sum(frame, "quantity")
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Total Batches",
            int(frame["batch_id"].dropna().nunique()) if "batch_id" in frame.columns else 0,
        )
        col2.metric("Total Seedlings Received", f"{total_seedlings:,}")
        col3.metric(
            "Species Count",
            int(frame["species"].dropna().nunique()) if "species" in frame.columns else 0,
        )

        _render_species_breakdown(frame)

        st.subheader("Seedling Intake Records")
        preferred_columns = [
            "batch_id",
            "nursery_name",
            "species",
            "quantity",
            "intended_project_activity",
            "intake_date",
            "place_of_origin",
        ]
        visible_columns = [column for column in preferred_columns if column in frame.columns]
        display_frame = frame[visible_columns] if visible_columns else frame
        st.dataframe(display_frame, use_container_width=True, hide_index=True)
        return

    frame = field_frame
    if frame.empty:
        st.info("Trees and seedlings data is not available yet. Add `plots.csv` to populate this tab.")
        return

    view_mode = st.radio(
        "View",
        options=["All Recipients", "Single Recipient"],
        horizontal=True,
        key="trees_seedlings_view_mode",
    )

    selected_recipient_id: str | None = None
    if view_mode == "Single Recipient":
        if recipients.empty or "recipient_id" not in recipients.columns:
            st.info("Recipient-level filtering is not available because the recipients dataset has no usable `recipient_id` values.")
            return

        recipient_options = recipients["recipient_id"].dropna().astype("string").tolist()
        if not recipient_options:
            st.info("No recipient IDs were found in the recipients dataset.")
            return

        selected_recipient_id = st.selectbox(
            "Recipient ID",
            recipient_options,
            key="trees_seedlings_recipient_id",
        )

    filtered_frame = _filter_records_for_view(frame, view_mode, selected_recipient_id)
    if view_mode == "Single Recipient" and filtered_frame.empty:
        st.info("No trees and seedlings records were found for the selected recipient. Try another recipient or switch to all recipients.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trees Received", f"{_numeric_sum(filtered_frame, 'trees_received'):,}")
    col2.metric("Trees Planted", f"{_numeric_sum(filtered_frame, 'trees_planted'):,}")
    col3.metric("Seedlings Distributed", f"{_numeric_sum(filtered_frame, 'seedlings_distributed'):,}")
    col4.metric("ER Planting Counts", f"{_numeric_sum(filtered_frame, 'er_planting_count'):,}")

    _render_species_breakdown(filtered_frame)
    _render_charts(filtered_frame)

    st.subheader("Trees and Seedlings Records")
    if filtered_frame.empty:
        st.info("No trees and seedlings records are available for the current selection.")
        return

    preferred_columns = [
        "recipient_id",
        "plot_id",
        "plot_name",
        "species",
        "trees_received",
        "trees_planted",
        "seedlings_distributed",
        "er_planting_count",
        "status",
    ]
    visible_columns = [column for column in preferred_columns if column in filtered_frame.columns]
    display_frame = filtered_frame[visible_columns] if visible_columns else filtered_frame
    st.dataframe(display_frame, use_container_width=True, hide_index=True)
