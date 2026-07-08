from __future__ import annotations

from html import escape

import polars as pl
import streamlit as st

from bess_dashboard.components.charts import activation_figure, load_profile_figure, market_price_figure
from bess_dashboard.components.kpis import render_data_kpis
from bess_dashboard.data import summarize_data_tab

DETAIL_COLUMNS = [
    "timestamp",
    "hour",
    "site_load_kw",
    "site_pv_kw",
    "net_load_kw",
    "spot_price_eur_mwh",
    "fcrn_price_eur_mw_h",
    "mfrr_capacity_price_eur_mw_h",
    "mfrr_activation_energy_price_eur_mwh",
    "mfrr_activation_volume_mw",
    "mfrr_activation_flag",
]

CHART_CONFIG = {"displayModeBar": False, "responsive": True}


def render_section_header(title: str, caption: str, *, tight: bool = False) -> None:
    class_name = "section-header-tight" if tight else "section-header"
    st.markdown(
        (
            f'<div class="{class_name}">'
            f'<div class="section-heading">{escape(title)}</div>'
            f'<div class="section-caption">{escape(caption)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_context(summary: dict[str, float | int | str], resolution: str) -> None:
    items = [
        ("Data strategy", "Synthetic representative site profile with public market signals."),
        ("Bidding area", f"{summary['zone']} / SN3 keeps spot, FCR-N, and mFRR inputs aligned."),
        ("Market sources", "Nord Pool spot plus Svenska Kraftnat Mimer FCR-N, mFRR CM, and mFRR EAM."),
        ("Dashboard grain", f"{resolution}; 15-minute data is retained as the clean canonical dataset."),
    ]

    scopes = [
        ("Date", f"{summary['date']}"),
        ("Zone", f"{summary['zone']}"),
        ("Resolution", f"{resolution}"),
        ("Rows", f"{summary['rows']:,}"),
    ]

    with st.container(border=True):
        st.caption("DATASET SCOPE")

        columns = st.columns([1, 1, 1, 1], gap="medium")
        for index, (label, value) in enumerate(scopes):
            with columns[index]:
                st.caption(label.upper())
                st.write(value)

        columns = st.columns([1, 1, 1, 1], gap="medium")
        for index, (label, value) in enumerate(items):
            with columns[index]:
                st.caption(label.upper())
                st.write(value)


def render_data_tab(df: pl.DataFrame, *, resolution: str) -> None:
    summary = summarize_data_tab(df)
    render_section_header(
        "Operating snapshot",
        "Headline load, PV, and reserve-market indicators for the selected representative window.",
    )
    render_data_kpis(summary)

    render_section_header(
        "Data context",
        "Source, zone, and grain assumptions used by the charts below.",
        tight=True,
    )
    render_context(summary, resolution)

    st.markdown('<div class="section-title">Load and PV profile</div>', unsafe_allow_html=True)
    st.plotly_chart(load_profile_figure(df), width="stretch", config=CHART_CONFIG)

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown('<div class="section-title">Market prices</div>', unsafe_allow_html=True)
        st.plotly_chart(market_price_figure(df), width="stretch", config=CHART_CONFIG)
    with right:
        st.markdown('<div class="section-title">mFRR activation</div>', unsafe_allow_html=True)
        st.plotly_chart(activation_figure(df), width="stretch", config=CHART_CONFIG)

    with st.expander(f"Detail rows ({df.height:,})"):
        st.dataframe(
            df.select([col for col in DETAIL_COLUMNS if col in df.columns]).to_dicts(),
            hide_index=True,
            width="stretch",
        )
