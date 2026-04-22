from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from utils.config import ALLOWED_DOMAINS, ALLOWED_EMAILS, APP_ENV, AUTH_ENABLED


@dataclass(frozen=True)
class AuthContext:
    user_display_name: str
    user_email: str | None
    is_authenticated: bool
    is_authorized: bool
    authentication_enabled: bool
    environment: str


def _get_streamlit_user() -> Any:
    return getattr(st, "user", getattr(st, "experimental_user", None))


def _user_value(user: Any, key: str, default: str = "") -> str:
    if user is None:
        return default

    value = getattr(user, key, None)
    if value is not None:
        return str(value)

    if hasattr(user, "get"):
        fallback = user.get(key, default)
        return str(fallback) if fallback is not None else default

    return default


def _is_logged_in(user: Any) -> bool:
    return bool(getattr(user, "is_logged_in", False))


def _normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def user_is_authorized(user_email: str | None = None) -> bool:
    if not AUTH_ENABLED:
        return True

    normalized_email = _normalize_email(user_email)
    if not normalized_email:
        return False

    if not ALLOWED_EMAILS and not ALLOWED_DOMAINS:
        return True

    allowed_emails = {_normalize_email(email) for email in ALLOWED_EMAILS}
    allowed_domains = {_normalize_email(domain).lstrip("@") for domain in ALLOWED_DOMAINS}

    if normalized_email in allowed_emails:
        return True

    if "@" in normalized_email:
        email_domain = normalized_email.split("@", 1)[1]
        if email_domain in allowed_domains:
            return True

    return False


def get_auth_context() -> AuthContext:
    if not AUTH_ENABLED:
        return AuthContext(
            user_display_name="Local Development User",
            user_email=None,
            is_authenticated=False,
            is_authorized=True,
            authentication_enabled=False,
            environment=APP_ENV,
        )

    user = _get_streamlit_user()
    if user is None or not _is_logged_in(user):
        return AuthContext(
            user_display_name="Guest",
            user_email=None,
            is_authenticated=False,
            is_authorized=False,
            authentication_enabled=True,
            environment=APP_ENV,
        )

    user_email = _normalize_email(
        _user_value(user, "email") or _user_value(user, "mail") or _user_value(user, "upn")
    )
    user_name = (
        _user_value(user, "name")
        or _user_value(user, "given_name")
        or user_email
        or "Authenticated User"
    )

    return AuthContext(
        user_display_name=user_name,
        user_email=user_email or None,
        is_authenticated=True,
        is_authorized=user_is_authorized(user_email or None),
        authentication_enabled=True,
        environment=APP_ENV,
    )


def require_login() -> AuthContext:
    auth_context = get_auth_context()

    if not auth_context.authentication_enabled:
        # Keep the main page clean in local/dev mode; show this only in the sidebar.
        st.sidebar.info(
            "Authentication is disabled. Set `AUTH_ENABLED=true` to require Microsoft Entra ID login."
        )
        return auth_context

    if not auth_context.is_authenticated:
        st.title("Recipient Dashboard")
        st.warning("Please sign in with Microsoft Entra ID to access this dashboard.")
        st.caption(
            "Configure Streamlit OIDC in `.streamlit/secrets.toml` with `[auth]` and `[auth.microsoft]` before enabling production access."
        )
        if st.button("Log in with Microsoft Entra ID", type="primary"):
            st.login("microsoft")
        st.stop()

    if not auth_context.is_authorized:
        st.title("Recipient Dashboard")
        st.error("Access denied. Your account is authenticated but not authorized for this dashboard.")
        if auth_context.user_email:
            st.caption(f"Signed in as `{auth_context.user_email}`")
        if st.button("Log out"):
            st.logout()
        st.stop()

    return auth_context
