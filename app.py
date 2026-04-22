from __future__ import annotations

from typing import Callable

import streamlit as st

from tabs import (
    documents,
    grievances,
    nursery,
    recipient_overview,
    training,
    trees_seedlings,
)
from utils.auth import AuthContext, require_login
from utils.config import APP_TITLE, PAGE_ICON

TabRenderer = Callable[[AuthContext], None]


def configure_page() -> None:
    """Apply the shared Streamlit page configuration."""
    st.set_page_config(page_title=APP_TITLE, page_icon=PAGE_ICON, layout="wide")


TABS: dict[str, TabRenderer] = {
    "Recipient Overview": recipient_overview.render,
    "Trees & Seedlings": trees_seedlings.render,
    "Training": training.render,
    "Documents": documents.render,
    "Grievances": grievances.render,
    "Nursery": nursery.render,
}


def _render_tab_safely(tab_name: str, render_tab: TabRenderer, auth_context: AuthContext) -> None:
    """Keep one tab failure from breaking the rest of the dashboard."""
    try:
        render_tab(auth_context)
    except BaseException as exc:
        # Streamlit uses internal exceptions to control flow (stop/rerun). These should
        # not be surfaced as user-facing tab errors.
        if exc.__class__.__name__ in {"StopException", "RerunException"}:
            raise

        st.error(f"{tab_name} could not be rendered.")
        st.exception(exc)


def main() -> None:
    configure_page()
    auth_context = require_login()

    st.title(APP_TITLE)
    st.caption(
        "Internal starter dashboard for recipients, trees, trainings, documents, grievances, and nursery operations."
    )
    st.caption(f"Environment: `{auth_context.environment}`")
    if auth_context.user_email:
        st.caption(f"Signed in as `{auth_context.user_email}`")

    tab_names = list(TABS.keys())
    selected_tab = st.sidebar.radio(
        "Navigation",
        options=tab_names,
        index=0,
        key="sidebar_navigation",
    )
    st.sidebar.caption("Select a module to view.")

    render_tab = TABS.get(selected_tab)
    if render_tab is None:
        st.error("Selected tab is not available.")
        return

    _render_tab_safely(selected_tab, render_tab, auth_context)


if __name__ == "__main__":
    main()
