from __future__ import annotations

from html import escape

import streamlit as st


def format_kw(value: float) -> str:
    return f"{value:,.0f}"


def format_price(value: float) -> str:
    return f"{value:,.2f}"


def format_pct(value: float) -> str:
    return f"{value:.0%}"


def render_data_kpis(summary: dict[str, float | int | str]) -> None:
    metrics = [
        ("Peak net load", format_kw(float(summary["peak_net_load_kw"])), "kW"),
        ("Peak PV", format_kw(float(summary["peak_pv_kw"])), "kW"),
        ("Avg FCR-N", format_price(float(summary["avg_fcrn_price"])), "EUR/MW/h"),
        ("Avg mFRR CM", format_price(float(summary["avg_mfrr_capacity_price"])), "EUR/MW/h"),
        ("Activation rate", format_pct(float(summary["activation_probability"])), "intervals active"),
    ]

    cols = st.columns(len(metrics), gap="medium")

    for col, (label, value, unit) in zip(cols, metrics, strict=True):
        card_html = (
            '<div class="metric-card">'
            f'<div class="metric-label">{escape(label)}</div>'
            f'<div class="metric-value">{escape(value)}</div>'
            f'<div class="metric-unit">{escape(unit)}</div>'
            "</div>"
        )
        col.markdown(
            card_html,
            unsafe_allow_html=True,
        )
