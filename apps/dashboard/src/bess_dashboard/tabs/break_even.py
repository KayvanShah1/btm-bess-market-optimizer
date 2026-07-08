from __future__ import annotations

from html import escape

import plotly.graph_objects as go
import polars as pl
import streamlit as st
from bess_optimizer.sensitivity.b3_break_even import summarize_break_even_result
from bess_optimizer.sensitivity.finance import FinancialOverlayAssumptions, build_financial_overlay

CHART_CONFIG = {"displayModeBar": False, "responsive": True}
GRID_COLOR = "rgba(148, 163, 184, 0.25)"
TEXT_COLOR = "#e5e7eb"


def format_eur(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.0f}"


def format_years(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value > 99:
        return ">99"
    return f"{value:.1f}"


def format_eur_per_day(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.1f} EUR/day"


def render_kpi_cards(summary: dict[str, float | int | None]) -> None:
    one_x_threshold = summary["max_activation_probability_at_1x_capacity"]

    metrics = [
        ("Best case", format_eur(summary["best_case_delta_eur"]), "daily delta EUR"),
        ("Worst case", format_eur(summary["worst_case_delta_eur"]), "daily delta EUR"),
        (
            "1.0x threshold",
            "n/a" if one_x_threshold is None else f"{float(one_x_threshold):.0%}",
            "max activation rate",
        ),
        ("Worthwhile cells", f"{int(summary['worthwhile_cell_count'])}", "grid cells"),
    ]

    columns = st.columns(len(metrics), gap="medium")
    for column, (label, value, unit) in zip(columns, metrics, strict=True):
        column.markdown(
            (
                '<div class="metric-card">'
                f'<div class="metric-label">{escape(label)}</div>'
                f'<div class="metric-value">{escape(value)}</div>'
                f'<div class="metric-unit">{escape(unit)}</div>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def battery_size_options(df: pl.DataFrame) -> list[dict[str, float | int | str]]:
    if "battery_count" not in df.columns:
        return []

    return (
        df.select(["battery_count", "battery_power_mw", "battery_energy_mwh", "usable_soc_headroom_mwh"])
        .unique()
        .sort("battery_count")
        .to_dicts()
    )


def battery_size_label(row: dict[str, float | int | str]) -> str:
    count = int(row["battery_count"])
    label = "battery" if count == 1 else "batteries"
    return (
        f"{count} {label} "
        f"({float(row['battery_power_mw']):.0f} MW / {float(row['battery_energy_mwh']):.0f} MWh)"
    )


def break_even_heatmap_figure(df: pl.DataFrame) -> go.Figure:
    activations = sorted(df["activation_probability"].unique().to_list())
    multipliers = sorted(df["mfrr_capacity_price_multiplier"].unique().to_list())
    values = {
        (float(row["activation_probability"]), float(row["mfrr_capacity_price_multiplier"])): float(
            row["delta_vs_fcr_only_eur"]
        )
        for row in df.to_dicts()
    }

    z_values = [[values[(activation, multiplier)] for multiplier in multipliers] for activation in activations]

    figure = go.Figure(
        go.Heatmap(
            x=[f"{multiplier:.2f}x" for multiplier in multipliers],
            y=[f"{activation:.0%}" for activation in activations],
            z=z_values,
            zmid=0,
            colorscale=[
                [0.0, "#b91c1c"],
                [0.48, "#f97316"],
                [0.50, "#0f172a"],
                [0.52, "#0f766e"],
                [1.0, "#22c55e"],
            ],
            colorbar=dict(title="EUR"),
            hovertemplate=(
                "Activation %{y}<br>"
                "mFRR capacity price %{x}<br>"
                "Delta vs FCR-only EUR %{z:.2f}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        height=470,
        margin=dict(l=64, r=44, t=12, b=64),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color=TEXT_COLOR),
        xaxis=dict(title="mFRR capacity price multiplier", linecolor=GRID_COLOR, tickfont=dict(color=TEXT_COLOR)),
        yaxis=dict(title="mFRR activation probability", linecolor=GRID_COLOR, tickfont=dict(color=TEXT_COLOR)),
    )
    return figure


def threshold_table(df: pl.DataFrame) -> list[dict[str, str]]:
    rows = (
        df.filter(pl.col("is_mfrr_worthwhile"))
        .group_by("activation_probability")
        .agg(pl.col("mfrr_capacity_price_multiplier").min().alias("break_even_capacity_multiplier"))
        .sort("activation_probability")
        .to_dicts()
    )
    if not rows:
        return []
    return [
        {
            "Activation probability": f"{float(row['activation_probability']):.0%}",
            "Minimum capacity multiplier": f"{float(row['break_even_capacity_multiplier']):.2f}x",
        }
        for row in rows
    ]


def detail_rows(df: pl.DataFrame) -> list[dict[str, str]]:
    columns = [
        "battery_count",
        "battery_power_mw",
        "battery_energy_mwh",
        "activation_probability",
        "mfrr_capacity_price_multiplier",
        "delta_vs_fcr_only_eur",
        "is_mfrr_worthwhile",
        "annualized_delta_eur",
        "annual_net_incremental_value_eur",
        "required_daily_delta_for_target_payback_eur",
        "payback_gap_to_target_eur_per_day",
        "payback_years",
    ]
    rows = df.select(columns).sort(["activation_probability", "mfrr_capacity_price_multiplier"]).to_dicts()
    return [
        {
            "Battery count": f"{int(row['battery_count'])}",
            "Battery MW": f"{float(row['battery_power_mw']):.0f}",
            "Battery MWh": f"{float(row['battery_energy_mwh']):.0f}",
            "Activation probability": f"{float(row['activation_probability']):.0%}",
            "Capacity multiplier": f"{float(row['mfrr_capacity_price_multiplier']):.2f}x",
            "Daily delta EUR": f"{float(row['delta_vs_fcr_only_eur']):,.2f}",
            "mFRR worthwhile": "Yes" if row["is_mfrr_worthwhile"] else "No",
            "Annualized delta EUR": f"{float(row['annualized_delta_eur']):,.0f}",
            "Annual net EUR": f"{float(row['annual_net_incremental_value_eur']):,.0f}",
            "Required daily delta EUR": f"{float(row['required_daily_delta_for_target_payback_eur']):,.2f}",
            "Gap to target EUR/day": f"{float(row['payback_gap_to_target_eur_per_day']):,.2f}",
            "Payback years": format_years(row["payback_years"]),
        }
        for row in rows
    ]


def render_financial_controls() -> FinancialOverlayAssumptions:
    st.markdown('<div class="section-title">Commercial payback overlay</div>', unsafe_allow_html=True)
    with st.container(border=True):
        columns = st.columns(3, gap="medium")
        upfront_cost = columns[0].number_input(
            "Enablement cost EUR",
            min_value=0.0,
            value=25_000.0,
            step=1_000.0,
        )
        annual_cost = columns[1].number_input(
            "Annual operating cost EUR",
            min_value=0.0,
            value=5_000.0,
            step=500.0,
        )
        risk_buffer = columns[2].number_input(
            "Risk buffer EUR",
            min_value=0.0,
            value=2_000.0,
            step=500.0,
        )
        columns = st.columns(3, gap="medium")
        operating_days = columns[0].number_input(
            "Operating days",
            min_value=1,
            max_value=366,
            value=300,
            step=1,
        )
        confidence_factor = columns[1].number_input(
            "Confidence factor",
            min_value=0.1,
            max_value=1.0,
            value=0.80,
            step=0.05,
        )
        target_payback_years = columns[2].number_input(
            "Target payback years",
            min_value=0.5,
            max_value=30.0,
            value=5.0,
            step=0.5,
        )

    return FinancialOverlayAssumptions(
        upfront_enablement_cost_eur=float(upfront_cost),
        annual_operating_cost_eur=float(annual_cost),
        risk_buffer_eur=float(risk_buffer),
        operating_days=int(operating_days),
        confidence_factor=float(confidence_factor),
        target_payback_years=float(target_payback_years),
    )


def render_payback_summary(break_even_df: pl.DataFrame) -> None:
    best_row = break_even_df.sort("delta_vs_fcr_only_eur", descending=True).to_dicts()[0]
    with st.container(border=True):
        columns = st.columns(4, gap="medium")
        columns[0].metric("Best payback", format_years(best_row["payback_years"]), "years")
        columns[1].metric(
            "Required daily delta",
            format_eur_per_day(best_row["required_daily_delta_for_target_payback_eur"]),
            f"{float(best_row['target_payback_years']):.1f} year target",
        )
        columns[2].metric(
            "Best daily delta",
            format_eur_per_day(best_row["delta_vs_fcr_only_eur"]),
            f"{float(best_row['payback_gap_to_target_eur_per_day']):+,.1f} EUR/day",
        )
        columns[3].metric(
            "Fixed cost burden",
            format_eur_per_day(best_row["fixed_cost_burden_eur_per_day"]),
            "operating + risk",
        )

    if best_row["payback_years"] is None:
        st.info("No grid cell clears the selected annual operating cost and risk-buffer assumptions.")


def render_break_even_tab(raw_break_even_df: pl.DataFrame) -> None:
    selected_df = raw_break_even_df
    options = battery_size_options(raw_break_even_df)
    if options:
        selected_option = st.selectbox(
            "Battery size",
            options=options,
            format_func=battery_size_label,
        )
        selected_df = raw_break_even_df.filter(pl.col("battery_count") == int(selected_option["battery_count"]))
        st.caption(
            "Battery-count sweep scales the Part A unit as identical aggregate batteries at the same site. "
            "It changes available MW and SOC headroom, not customer load."
        )

    summary = summarize_break_even_result(selected_df)

    st.markdown('<div class="section-title">Operational break-even</div>', unsafe_allow_html=True)
    render_kpi_cards(summary)

    st.plotly_chart(break_even_heatmap_figure(selected_df), width="stretch", config=CHART_CONFIG)
    st.caption("Green cells mean stacked FCR-N + mFRR beats FCR-N-only. Red cells mean FCR-N-only is higher value.")

    threshold_rows = threshold_table(selected_df)
    if threshold_rows:
        st.markdown('<div class="section-title">Break-even threshold by activation rate</div>', unsafe_allow_html=True)
        st.dataframe(threshold_rows, hide_index=True, width="stretch")

    assumptions = render_financial_controls()
    break_even_df = build_financial_overlay(selected_df, assumptions)
    render_payback_summary(break_even_df)

    with st.expander(f"Sensitivity grid rows ({break_even_df.height:,} rows)"):
        st.dataframe(detail_rows(break_even_df), hide_index=True, width="stretch")
