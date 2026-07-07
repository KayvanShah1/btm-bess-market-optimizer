from __future__ import annotations

import polars as pl
import streamlit as st

from bess_dashboard.components.dispatch_charts import (
    capacity_allocation_figure,
    grid_import_figure,
    soc_figure,
    value_component_figure,
)

CHART_CONFIG = {"displayModeBar": False, "responsive": True}

SCENARIO_ORDER = [
    "no_battery",
    "local_only",
    "fcr_only",
    "stacked_low_activation",
    "stacked_base_activation",
    "stacked_high_activation",
]

SCENARIO_LABELS = {
    "no_battery": "No Battery Baseline",
    "local_only": "Local-Only Battery",
    "fcr_only": "FCR-N Only",
    "stacked_low_activation": "Stacked: Low mFRR Activation",
    "stacked_base_activation": "Stacked: Base mFRR Activation",
    "stacked_high_activation": "Stacked: High mFRR Activation",
}

SCENARIO_DESCRIPTIONS = {
    "no_battery": "PV serves load first; remaining load is imported from the grid. The battery and reserve markets are disabled, so this is the cost reference case.",
    "local_only": "The battery only serves local site value: PV charging, peak shaving, high-price discharge, and safe low-price grid charging. No FCR-N or mFRR is sold.",
    "fcr_only": "The local battery logic is preserved first, then any feasible remaining capacity is offered to FCR-N. mFRR is disabled.",
    "stacked_low_activation": "The stacked scheduler can split capacity across local reserve, FCR-N, and mFRR, but assumes no mFRR activation energy is called.",
    "stacked_base_activation": "The stacked scheduler uses the dataset's average mFRR activation probability to score expected activation value.",
    "stacked_high_activation": "The stacked scheduler doubles the base activation probability, capped at 75%, to test higher mFRR activation exposure.",
}

SERVICE_LABELS = {
    "no_battery": "No battery",
    "local_only": "Local only",
    "local_plus_fcr": "Local + FCR-N",
    "stacked_hold": "Hold capacity",
    "local_fcr": "Local + FCR-N",
    "local_mfrr": "Local + mFRR",
    "local_fcr_mfrr": "Local + FCR-N + mFRR",
}

DETAIL_COLUMNS = [
    "timestamp",
    "hour",
    "service",
    "pv_to_load_kw",
    "pv_to_battery_kw",
    "grid_to_load_kw",
    "grid_to_battery_kw",
    "battery_to_load_kw",
    "grid_import_kw",
    "soc_mwh",
    "local_reserve_mw",
    "fcr_commit_mw",
    "mfrr_commit_mw",
    "total_value_eur",
    "constraint_status",
]


def format_eur(value: float) -> str:
    return f"{value:,.0f} EUR"


def format_pct(value: float) -> str:
    return f"{value:.1%}"


def format_kw(value: float) -> str:
    return f"{value:,.0f} kW"


def format_mwh(value: float) -> str:
    return f"{value:.2f} MWh"


def scenario_options(dispatch_df: pl.DataFrame) -> list[str]:
    available = set(dispatch_df["scenario"].unique().to_list())
    ordered = [scenario for scenario in SCENARIO_ORDER if scenario in available]
    return ordered or sorted(available)


def scenario_label(scenario: str) -> str:
    return SCENARIO_LABELS.get(scenario, scenario.replace("_", " ").title())


def service_label(service: str) -> str:
    return SERVICE_LABELS.get(service, service.replace("_", " ").title())


def scenario_definition_rows(selected_scenario: str) -> list[dict[str, str]]:
    return [
        {"Scenario": scenario_label(scenario), "Meaning": SCENARIO_DESCRIPTIONS[scenario]}
        for scenario in SCENARIO_ORDER
        if scenario != selected_scenario
    ]


def render_scenario_context(scenario: str) -> None:
    st.markdown('<div class="section-title">Scenario setup</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.caption("SELECTED SCENARIO")
        st.write(f"**{scenario_label(scenario)}**")
        st.write(SCENARIO_DESCRIPTIONS[scenario])
        st.caption("OTHER SCENARIOS")
        st.dataframe(scenario_definition_rows(scenario), hide_index=True, width="stretch")


def render_dispatch_kpis(summary_row: dict[str, float | int | str]) -> None:
    metrics = [
        ("Total value", format_eur(float(summary_row["total_value_eur"]))),
        ("Local savings", format_pct(float(summary_row["local_savings_pct"]))),
        ("Delta vs FCR-only", format_eur(float(summary_row["delta_vs_fcr_only_eur"]))),
        ("Peak import reduction", format_kw(float(summary_row["peak_import_reduction_kw"]))),
        ("Minimum SOC", format_mwh(float(summary_row["min_soc_mwh"]))),
        ("Violations", f"{int(summary_row['constraint_violation_count'])}"),
    ]
    for column, (label, value) in zip(st.columns(len(metrics), gap="medium"), metrics, strict=True):
        column.metric(label, value)


def render_dispatch_tab(dispatch_df: pl.DataFrame, summary_df: pl.DataFrame, audit_df: pl.DataFrame) -> None:
    options = scenario_options(dispatch_df)
    default_index = options.index("stacked_base_activation") if "stacked_base_activation" in options else 0
    scenario = st.selectbox("Scenario", options=options, index=default_index, format_func=scenario_label)

    scenario_df = dispatch_df.filter(pl.col("scenario") == scenario).sort("timestamp")
    summary_row = summary_df.filter(pl.col("scenario") == scenario).to_dicts()[0]

    st.caption(f"{scenario_label(scenario)} | {scenario_df.height:,} hourly rows")
    render_scenario_context(scenario)
    render_dispatch_kpis(summary_row)

    st.markdown('<div class="section-title">State of charge</div>', unsafe_allow_html=True)
    st.plotly_chart(soc_figure(scenario_df), width="stretch", config=CHART_CONFIG)

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown('<div class="section-title">Capacity allocation</div>', unsafe_allow_html=True)
        st.plotly_chart(capacity_allocation_figure(scenario_df), width="stretch", config=CHART_CONFIG)
    with right:
        st.markdown('<div class="section-title">Grid import</div>', unsafe_allow_html=True)
        st.plotly_chart(grid_import_figure(scenario_df), width="stretch", config=CHART_CONFIG)

    st.markdown('<div class="section-title">Value components</div>', unsafe_allow_html=True)
    st.plotly_chart(value_component_figure(summary_row), width="stretch", config=CHART_CONFIG)

    st.markdown('<div class="section-title">Dispatch detail</div>', unsafe_allow_html=True)
    detail_df = scenario_df.with_columns(
        pl.col("service_selected").replace_strict(SERVICE_LABELS, default=pl.col("service_selected")).alias("service")
    )
    st.dataframe(
        detail_df.select([column for column in DETAIL_COLUMNS if column in detail_df.columns]).to_dicts(),
        hide_index=True,
        width="stretch",
    )

    st.markdown('<div class="section-title">Constraint audit</div>', unsafe_allow_html=True)
    display_audit_df = audit_df.with_columns(
        pl.col("scenario").replace_strict(SCENARIO_LABELS, default=pl.col("scenario")).alias("scenario")
    )
    st.dataframe(display_audit_df.to_dicts(), hide_index=True, width="stretch")
