from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import AuthContext
from utils.loaders import load_nursery_batch_intake
from utils.transforms import ui_safe_frame


def _numeric_sum(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns or frame.empty:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


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
            for column in ["quantity", "seedlings_distributed", "trees_received", "trees_planted"]
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

    st.dataframe(ui_safe_frame(breakdown), use_container_width=True, hide_index=True)


def _render_nursery_totals_chart(frame: pd.DataFrame) -> None:
    st.subheader("Seedlings Received by Nursery")
    if frame.empty or "nursery_name" not in frame.columns:
        st.info("Nursery totals are not available for charting yet.")
        return

    totals = (
        frame.assign(_qty=pd.to_numeric(frame.get("quantity"), errors="coerce").fillna(0))
        .groupby("nursery_name", dropna=False)["_qty"]
        .sum()
        .sort_values(ascending=False)
    )
    if totals.empty:
        st.info("No quantity values are available to chart.")
        return

    chart_frame = totals.reset_index().rename(columns={"_qty": "total"}).set_index("nursery_name")
    st.bar_chart(chart_frame, y="total")


def render(auth_context: AuthContext) -> None:
    """Render trees & seedlings insights from Kobo nursery exports."""
    frame = load_nursery_batch_intake()

    st.header("Trees & Seedlings")
    st.caption(f"Data source: `{auth_context.environment}`")

    if frame.empty:
        st.info(
            "Nursery intake data is not available yet. Add `Nursery Seedling Batch Intake.xlsx` to populate this tab."
        )
        return

    st.caption(
        "Showing seedling batches received into nurseries from Kobo exports."
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
    _render_nursery_totals_chart(frame)

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
    st.dataframe(ui_safe_frame(display_frame), use_container_width=True, hide_index=True)
