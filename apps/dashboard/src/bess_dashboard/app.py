from __future__ import annotations

import streamlit as st

from bess_dashboard.data import (
    filter_hour_range,
    load_break_even_output,
    load_constraint_audit,
    load_dispatch_output,
    load_processed_dataset,
    load_scenario_summary,
)
from bess_dashboard.tabs.break_even import render_break_even_tab
from bess_dashboard.tabs.data import render_data_tab
from bess_dashboard.tabs.dispatch import render_dispatch_tab
from bess_dashboard.tabs.methodology import render_methodology_tab


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .main .block-container {
            max-width: 1360px;
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }
        div[data-testid="stSidebarContent"] {
            padding-top: 1.5rem;
        }
        .dashboard-eyebrow {
            color: #93a4b8;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.15rem;
        }
        .dashboard-subtitle {
            color: #a8b3c4;
            font-size: 0.98rem;
            margin-top: -0.5rem;
            margin-bottom: 1.45rem;
        }
        .section-title {
            color: #f8fafc;
            font-size: 1.4rem;
            font-weight: 700;
            margin: 2rem 0 0.65rem;
        }
        .section-header {
            margin: 1.8rem 0 0.75rem;
        }
        .section-header-tight {
            margin: 1.35rem 0 0.55rem;
        }
        .section-heading {
            color: #f8fafc;
            font-size: 1.02rem;
            font-weight: 760;
            line-height: 1.25;
        }
        .section-caption {
            color: #94a3b8;
            font-size: 0.88rem;
            line-height: 1.35;
            margin-top: 0.22rem;
        }
        .metric-card {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 8px;
            background: rgba(15, 23, 42, 0.46);
            padding: 1rem 1rem 0.95rem;
            min-height: 112px;
        }
        .metric-label {
            color: #a8b3c4;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .metric-value {
            color: #f8fafc;
            font-size: 1.8rem;
            font-weight: 760;
            line-height: 1.15;
            margin-top: 0.48rem;
            white-space: nowrap;
        }
        .metric-unit {
            color: #94a3b8;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            margin-top: 0.12rem;
            text-transform: uppercase;
            white-space: nowrap;
        }
        @media (max-width: 900px) {
            .metric-value {
                font-size: 1.45rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="BESS Market Optimizer",
        page_icon=":material/battery_charging_full:",
        layout="wide",
    )

    apply_theme()

    st.markdown('<div class="dashboard-eyebrow">Behind-the-meter</div>', unsafe_allow_html=True)
    st.title("BESS Market Optimizer")
    st.markdown(
        '<div class="dashboard-subtitle">Representative SE3 data view for load, PV, FCR-N, and mFRR signals.</div>',
        unsafe_allow_html=True,
    )

    active_view = st.segmented_control(
        "View",
        options=["Data", "Dispatch", "Break-even", "Methodology"],
        default="Data",
        key="active_dashboard_view",
    )

    if active_view == "Data":
        resolution = st.sidebar.segmented_control(
            "Data resolution",
            options=["Hourly", "15-minute"],
            default="Hourly",
        )
        hour_range = st.sidebar.slider(
            "Hours",
            min_value=0,
            max_value=23,
            value=(0, 23),
        )

        grain = "hourly" if resolution == "Hourly" else "15min"
        df = filter_hour_range(load_processed_dataset(grain), hour_range)
        render_data_tab(df, resolution=resolution)

    if active_view == "Dispatch":
        try:
            render_dispatch_tab(
                load_dispatch_output(),
                load_scenario_summary(),
                load_constraint_audit(),
            )
        except FileNotFoundError as exc:
            st.warning(str(exc))

    if active_view == "Break-even":
        try:
            render_break_even_tab(load_break_even_output())
        except FileNotFoundError as exc:
            st.warning(str(exc))

    if active_view == "Methodology":
        render_methodology_tab()


if __name__ == "__main__":
    main()
