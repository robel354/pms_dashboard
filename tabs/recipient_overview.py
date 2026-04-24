from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from utils.auth import AuthContext
from utils.config import ENTITY_NAME
from utils.loaders import load_farmer_registration

ENTITY_LABEL = ENTITY_NAME
NOT_AVAILABLE = "Not Available"

_SMALL_KV_STYLE = "font-size:0.9rem; line-height:1.3;"


def _render_small_kv_row(items: list[tuple[str, str]]) -> None:
    """Render a compact, responsive row of key/value cards.

    Using a single flex container avoids Streamlit column spacing quirks that can
    misalign items on wide layouts.
    """
    cards = "".join(
        f"<div style='flex:1 1 320px; min-width:320px; padding:12px 14px; border:1px solid rgba(49, 51, 63, 0.12); border-radius:12px; { _SMALL_KV_STYLE }'>"
        f"<div style='font-weight:600; margin-bottom:4px;'>{label}</div>"
        f"<div style='white-space:normal; overflow-wrap:anywhere;'>{value}</div>"
        f"</div>"
        for label, value in items
    )
    st.markdown(
        "<div style='display:flex; flex-wrap:wrap; gap:24px; align-items:stretch; width:100%; margin:8px 0 18px 0;'>"
        f"{cards}"
        "</div>",
        unsafe_allow_html=True,
    )


def _na(value: object) -> str:
    raw = str(value).strip() if value is not None else ""
    return raw if raw else NOT_AVAILABLE


def _titleize(column_name: str) -> str:
    cleaned = re.sub(r"[_/]+", " ", str(column_name)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.title()


def _get_first_present(record: pd.Series, candidates: list[str]) -> str:
    for column in candidates:
        if column in record.index:
            value = _na(record.get(column))
            if value != NOT_AVAILABLE:
                return value
    return NOT_AVAILABLE


def _parse_float(value: object) -> float | None:
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _extract_lat_lon(record: pd.Series) -> tuple[float | None, float | None]:
    lat = _parse_float(record.get("homestead_gps_coordinates_latitude"))
    lon = _parse_float(record.get("homestead_gps_coordinates_longitude"))
    if lat is not None and lon is not None:
        return lat, lon

    # Fallback to parsing the geopoint string: "-11.78 19.91 0 0"
    raw_point = str(record.get("homestead_gps_coordinates") or "").strip()
    parts = raw_point.split()
    if len(parts) >= 2:
        lat2 = _parse_float(parts[0])
        lon2 = _parse_float(parts[1])
        return lat2, lon2

    return None, None


def _render_registration_details(record: pd.Series) -> None:
    st.subheader(f"{ENTITY_LABEL} Summary")

    first_name = _na(record.get("first_name_of_household_head_or_primary_participant"))
    last_name = _na(record.get("last_name_of_household_head_or_primary_participant"))
    full_name = " ".join(part for part in [first_name, last_name] if part != NOT_AVAILABLE).strip() or NOT_AVAILABLE

    registration_id = _get_first_present(
        record,
        [
            "participant_registration_id",
            "manual_registration_id",
            "national_id_number",
        ],
    )

    _render_small_kv_row(
        [
            ("Registration ID", registration_id),
            ("Name", full_name),
            ("Village", _na(record.get("village"))),
        ]
    )

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Identity",
            [
                ("Gender", _na(record.get("gender_of_primary_participant"))),
                ("Date Of Birth", _na(record.get("date_of_birth"))),
                ("National Id", _na(record.get("national_id"))),
                ("National Id Number", _na(record.get("national_id_number"))),
            ],
        ),
        (
            "Contact",
            [
                ("Phone Access", _na(record.get("phone_access"))),
                ("Primary Phone / WhatsApp", _na(record.get("primary_phone_or_whatsapp_number"))),
                ("Email Address", _na(record.get("email_address"))),
                ("Preferred Communication Channel", _na(record.get("preferred_communication_channel"))),
                ("Preferred Language", _na(record.get("preferred_language"))),
            ],
        ),
        (
            "Co-Owner (If Applicable)",
            [
                ("Co-Owner First Name", _na(record.get("farm_co_owner_first_name_if_applicable"))),
                ("Co-Owner Second Name", _na(record.get("farm_co_owner_second_name_if_applicable"))),
            ],
        ),
    ]

    for title, items in sections:
        with st.expander(title, expanded=False):
            detail_frame = pd.DataFrame(items, columns=["Field", "Value"])
            st.dataframe(detail_frame, use_container_width=True, hide_index=True)


def _render_parcel_mapping(record: pd.Series) -> None:
    st.subheader("Parcel Mapping")

    lat, lon = _extract_lat_lon(record)
    has_coords = lat is not None and lon is not None

    _render_small_kv_row(
        [
            ("Homestead Latitude", f"{lat:.6f}" if lat is not None else NOT_AVAILABLE),
            ("Homestead Longitude", f"{lon:.6f}" if lon is not None else NOT_AVAILABLE),
            ("Parcel Boundary Mapping", _na(record.get("parcel_boundary_mapping"))),
        ]
    )

    if has_coords:
        show_map = st.checkbox(
            "Show homestead location on map",
            value=False,
            help="Coordinates are sensitive. Keep hidden unless needed.",
            key="recipient_overview_show_map",
        )
        if show_map:
            st.map(
                pd.DataFrame([{"latitude": lat, "longitude": lon}]),
                use_container_width=True,
            )
    else:
        st.info("No usable GPS coordinates were found for this registration.")

    with st.expander("Land Tenure & Disputes", expanded=False):
        tenure_items = [
            ("Land Tenure Type", _na(record.get("land_tenure_type"))),
            ("Tenure Evidence", _na(record.get("tenure_evidence"))),
            ("Known Disputes Or Overlapping Claims", _na(record.get("known_disputes_or_overlapping_claims"))),
            ("Description Of Dispute Or Overlap", _na(record.get("description_of_dispute_or_overlap"))),
        ]
        st.dataframe(pd.DataFrame(tenure_items, columns=["Field", "Value"]), use_container_width=True, hide_index=True)

    with st.expander("FCA Status", expanded=False):
        fca_items = [
            ("Fca Signed", _na(record.get("has_the_participant_signed_a_farmer_and_community_agreement_fca_form"))),
            ("Submission Time", _na(record.get("submission_time"))),
            ("Submitted By", _na(record.get("submitted_by"))),
            ("Status", _na(record.get("status"))),
        ]
        st.dataframe(pd.DataFrame(fca_items, columns=["Field", "Value"]), use_container_width=True, hide_index=True)


def render(auth_context: AuthContext) -> None:
    """Render the farmer/recipient registration + parcel mapping workflow (Kobo export)."""
    frame = load_farmer_registration()

    st.header(f"{ENTITY_LABEL} Overview")
    st.caption(f"Signed in as: `{auth_context.user_display_name}`")

    if frame.empty:
        st.info(
            "Registration data is not available yet. Add the Kobo CSV export for the Farmer Registration and Parcel Mapping Form to populate this view."
        )
        return

    # Interpretation note:
    # The provided Kobo export appears to be one row per registered farmer/household,
    # with homestead GPS fields embedded in the same row (no flattened repeat-group parcels observed).
    id_column = (
        "participant_registration_id"
        if "participant_registration_id" in frame.columns
        else ("manual_registration_id" if "manual_registration_id" in frame.columns else None)
    )
    if id_column is None:
        st.info("No usable registration identifier column was found in the export.")
        return

    options = frame[id_column].dropna().astype("string").tolist()
    options = [value for value in options if str(value).strip()]
    if not options:
        st.info("Registration data loaded, but no usable registration IDs were found.")
        return

    selected_id = st.selectbox(
        f"{ENTITY_LABEL} Registration Id",
        options,
        key="recipient_overview_registration_id",
    )

    selected = frame[frame[id_column].astype("string") == selected_id]
    if selected.empty:
        st.info("No registration record matched the selected registration ID.")
        return

    record = selected.iloc[0]
    _render_registration_details(record)
    _render_parcel_mapping(record)
