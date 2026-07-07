from __future__ import annotations

import plotly.graph_objects as go
import polars as pl

GRID_COLOR = "rgba(148, 163, 184, 0.25)"
TEXT_COLOR = "#e5e7eb"
SOC_COLOR = "#38bdf8"
LOCAL_COLOR = "#22c55e"
FCR_COLOR = "#0f766e"
MFRR_COLOR = "#d97706"
GRID_IMPORT_COLOR = "#fca5a5"
PEAK_COLOR = "#f8fafc"
VALUE_COLORS = ["#22c55e", "#0f766e", "#d97706", "#7c3aed"]


def _series(df: pl.DataFrame, column: str) -> list[float]:
    return df[column].fill_null(0.0).to_list()


def _apply_layout(figure: go.Figure, *, height: int, yaxis_title: str) -> go.Figure:
    figure.update_layout(
        height=height,
        hovermode="x unified",
        margin=dict(l=58, r=34, t=10, b=78),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color=TEXT_COLOR),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color=TEXT_COLOR),
        ),
        xaxis=dict(showgrid=False, linecolor=GRID_COLOR, tickfont=dict(size=12, color=TEXT_COLOR)),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(color=TEXT_COLOR)),
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            tickfont=dict(color=TEXT_COLOR),
        ),
    )
    return figure


def soc_figure(df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=df["timestamp"].to_list(),
            y=_series(df, "soc_mwh"),
            mode="lines+markers",
            name="SOC",
            line=dict(color=SOC_COLOR, width=3),
            marker=dict(size=6),
        )
    )
    return _apply_layout(figure, height=330, yaxis_title="MWh")


def capacity_allocation_figure(df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()
    x_values = df["timestamp"].to_list()
    figure.add_trace(
        go.Bar(x=x_values, y=_series(df, "local_reserve_mw"), name="Local reserve", marker_color=LOCAL_COLOR)
    )
    figure.add_trace(go.Bar(x=x_values, y=_series(df, "fcr_commit_mw"), name="FCR-N", marker_color=FCR_COLOR))
    figure.add_trace(go.Bar(x=x_values, y=_series(df, "mfrr_commit_mw"), name="mFRR", marker_color=MFRR_COLOR))
    figure.update_layout(barmode="stack")
    return _apply_layout(figure, height=360, yaxis_title="MW")


def grid_import_figure(df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()
    x_values = df["timestamp"].to_list()
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series(df, "grid_import_kw"),
            mode="lines",
            name="Grid import",
            line=dict(color=GRID_IMPORT_COLOR, width=3),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series(df, "peak_threshold_kw"),
            mode="lines",
            name="Peak threshold",
            line=dict(color=PEAK_COLOR, width=2, dash="dash"),
        )
    )
    return _apply_layout(figure, height=360, yaxis_title="kW")


def value_component_figure(summary_row: dict[str, float | int | str]) -> go.Figure:
    labels = ["Local savings", "FCR-N", "mFRR CM", "mFRR EAM"]
    values = [
        float(summary_row["local_savings_eur"]),
        float(summary_row["fcr_revenue_eur"]),
        float(summary_row["mfrr_capacity_revenue_eur"]),
        float(summary_row["expected_mfrr_activation_revenue_eur"]),
    ]
    figure = go.Figure(go.Bar(x=labels, y=values, marker_color=VALUE_COLORS, name="Value"))
    return _apply_layout(figure, height=330, yaxis_title="EUR")


def scenario_value_comparison_figure(summary_df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=summary_df["scenario"].to_list(),
            y=_series(summary_df, "total_value_eur"),
            name="Total value",
        )
    )
    return _apply_layout(figure, height=340, yaxis_title="EUR")


def soc_overlay_figure(dispatch_df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()

    for scenario in dispatch_df["scenario"].unique(maintain_order=True).to_list():
        if scenario == "no_battery":
            continue

        scenario_df = dispatch_df.filter(pl.col("scenario") == scenario).sort("timestamp")
        figure.add_trace(
            go.Scatter(
                x=scenario_df["timestamp"].to_list(),
                y=_series(scenario_df, "soc_mwh"),
                mode="lines",
                name=scenario.replace("_", " ").title(),
            )
        )
    return _apply_layout(figure, height=360, yaxis_title="MWh")


def market_revenue_comparison_figure(summary_df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()
    x_values = summary_df["scenario"].to_list()

    figure.add_trace(go.Bar(x=x_values, y=_series(summary_df, "fcr_revenue_eur"), name="FCR-N"))
    figure.add_trace(go.Bar(x=x_values, y=_series(summary_df, "mfrr_capacity_revenue_eur"), name="mFRR CM"))
    figure.add_trace(
        go.Bar(
            x=x_values,
            y=_series(summary_df, "expected_mfrr_activation_revenue_eur"),
            name="mFRR EAM",
        )
    )

    figure.update_layout(barmode="stack")
    return _apply_layout(figure, height=340, yaxis_title="EUR")
