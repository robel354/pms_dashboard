from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import AuthContext
from utils.config import ENTITY_NAME
from utils.loaders import load_training
from utils.transforms import ui_safe_frame


def render(auth_context: AuthContext) -> None:
    """Render training filters, topic coverage, and the session table."""
    frame = load_training()

    st.header("Training")
    st.caption(f"Environment: `{auth_context.environment}`")

    if frame.empty:
        st.info("Training data is not available yet. Add `training.csv` to start populating this tab.")
        return

    filtered_frame = frame.copy()

    filter_col1, filter_col2 = st.columns(2)

    if "recipient_id" in frame.columns:
        recipient_options = ["All"] + frame["recipient_id"].dropna().astype("string").sort_values().unique().tolist()
        selected_recipient = filter_col1.selectbox(
            f"{ENTITY_NAME} ID",
            recipient_options,
            key="training_recipient_id",
        )
        if selected_recipient != "All":
            filtered_frame = filtered_frame[
                filtered_frame["recipient_id"].astype("string") == selected_recipient
            ].copy()

    if "topic" in frame.columns:
        topic_options = ["All"] + frame["topic"].dropna().astype("string").sort_values().unique().tolist()
        selected_topic = filter_col2.selectbox(
            "Topic",
            topic_options,
            key="training_topic",
        )
        if selected_topic != "All":
            filtered_frame = filtered_frame[
                filtered_frame["topic"].astype("string") == selected_topic
            ].copy()

    total_sessions = len(filtered_frame.index)
    session_list = (
        filtered_frame["session_id"].dropna().astype("string").tolist()
        if "session_id" in filtered_frame.columns
        else []
    )
    topics_covered = (
        filtered_frame["topic"].dropna().astype("string").sort_values().unique().tolist()
        if "topic" in filtered_frame.columns
        else []
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Sessions", total_sessions)
    col2.metric("Listed Sessions", len(session_list))
    col3.metric("Topics Covered", len(topics_covered))

    st.subheader("Sessions")
    if session_list:
        st.write(", ".join(session_list))
    else:
        st.info("No session identifiers are available in the current training data.")

    st.subheader("Topics Covered")
    if topics_covered:
        st.write(", ".join(topics_covered))
    else:
        st.info("No topic values are available in the current training data.")

    st.subheader("Training Records")
    if filtered_frame.empty:
        st.info("No training records matched the current filters. Try clearing one or more filters.")
        return

    preferred_columns = [
        "session_id",
        "recipient_id",
        "topic",
        "participants",
        "completed",
        "training_date",
    ]
    visible_columns = [column for column in preferred_columns if column in filtered_frame.columns]
    display_frame = (
        filtered_frame[visible_columns].copy() if visible_columns else filtered_frame.copy()
    )

    numeric_columns = [column for column in ["participants", "completed"] if column in display_frame.columns]
    for column in numeric_columns:
        display_frame[column] = pd.to_numeric(display_frame[column], errors="coerce")

    st.dataframe(ui_safe_frame(display_frame), use_container_width=True, hide_index=True)
