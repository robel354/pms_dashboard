from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import AuthContext
from utils.loaders import load_plots, load_recipients, load_training
from utils.transforms import parse_lat_long_columns


def _safe_series_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns or frame.empty:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _safe_unique_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns or frame.empty:
        return 0
    return int(frame[column].dropna().nunique())


def _filter_by_recipient(frame: pd.DataFrame, recipient_id: str, recipient_name: str) -> pd.DataFrame:
    """Return records linked to the selected recipient using the best available key."""
    if frame.empty:
        return frame

    if "recipient_id" in frame.columns:
        return frame[frame["recipient_id"].astype("string") == recipient_id].copy()

    if "recipient_name" in frame.columns:
        return frame[frame["recipient_name"].astype("string") == recipient_name].copy()

    if "recipient" in frame.columns:
        return frame[frame["recipient"].astype("string") == recipient_name].copy()

    return frame.iloc[0:0].copy()


def _render_map(plots: pd.DataFrame) -> None:
    st.subheader("Plot Map")
    show_map = st.checkbox(
        "Show GPS-linked plot map",
        value=False,
        help="Plot coordinates are sensitive and are hidden by default.",
    )
    if not show_map:
        st.info("GPS-linked plot records are hidden by default. Enable the map only when needed.")
        return

    plot_locations = parse_lat_long_columns(plots)
    valid_locations = plot_locations.dropna(subset=["latitude", "longitude"])
    if valid_locations.empty:
        st.info("No valid latitude and longitude values are available for this recipient's plots yet.")
        return

    st.map(valid_locations[["latitude", "longitude"]], use_container_width=True)


def _render_plot_table(plots: pd.DataFrame) -> None:
    st.subheader("Plots")
    if plots.empty:
        st.info("No plot records are available for the selected recipient.")
        return

    preferred_columns = [
        "plot_id",
        "plot_name",
        "area_ha",
        "status",
        "trees_received",
        "trees_planted",
        "seedlings_distributed",
    ]
    visible_columns = [column for column in preferred_columns if column in plots.columns]
    display_frame = plots[visible_columns] if visible_columns else plots
    st.dataframe(display_frame, use_container_width=True, hide_index=True)


def render(auth_context: AuthContext) -> None:
    """Render the recipient summary view with plot, training, and map details."""
    recipients = load_recipients()
    plots = load_plots()
    training = load_training()

    st.header("Recipient Overview")
    st.caption(f"Signed in as: `{auth_context.user_display_name}`")

    if recipients.empty or "recipient_id" not in recipients.columns:
        st.info("Recipient data is not available yet. Add `recipients.csv` with a `recipient_id` column to populate this view.")
        return

    recipient_options = recipients["recipient_id"].dropna().astype("string").tolist()
    if not recipient_options:
        st.info("Recipient data loaded, but no usable `recipient_id` values were found.")
        return

    selected_recipient_id = st.selectbox(
        "Recipient ID",
        recipient_options,
        key="recipient_overview_recipient_id",
    )
    selected_recipient = recipients[
        recipients["recipient_id"].astype("string") == selected_recipient_id
    ].copy()

    if selected_recipient.empty:
        st.info("No recipient record matched the selected Recipient ID.")
        return

    recipient_name = str(selected_recipient["recipient_name"].iloc[0]) if "recipient_name" in selected_recipient.columns else selected_recipient_id
    filtered_plots = _filter_by_recipient(plots, selected_recipient_id, recipient_name)
    filtered_training = _filter_by_recipient(training, selected_recipient_id, recipient_name)

    if filtered_training.empty:
        training_sessions = 0
    elif "completed" in filtered_training.columns:
        completed_values = pd.to_numeric(filtered_training["completed"], errors="coerce")
        training_sessions = int(completed_values.fillna(0).gt(0).sum())
    else:
        training_sessions = len(filtered_training.index)

    st.write(f"Showing summary for **{recipient_name}** (`{selected_recipient_id}`).")

    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)
    col1.metric("Number of Plots", _safe_unique_count(filtered_plots, "plot_id"))
    col2.metric("Hectares Cultivated", f"{_safe_series_sum(filtered_plots, 'area_ha'):.2f}")
    col3.metric("Training Sessions", training_sessions)
    col4.metric("Trees Received", f"{_safe_series_sum(filtered_plots, 'trees_received'):.0f}")
    col5.metric("Trees Planted", f"{_safe_series_sum(filtered_plots, 'trees_planted'):.0f}")
    col6.metric("Seedlings Distributed", f"{_safe_series_sum(filtered_plots, 'seedlings_distributed'):.0f}")

    _render_plot_table(filtered_plots)
    _render_map(filtered_plots)

    st.subheader("Training Records")
    if filtered_training.empty:
        st.info("No training records are linked to this recipient yet.")
    else:
        st.dataframe(filtered_training, use_container_width=True, hide_index=True)
