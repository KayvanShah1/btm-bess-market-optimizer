from __future__ import annotations

import plotly.graph_objects as go
import polars as pl

LOAD_COLOR = "#2563eb"
PV_COLOR = "#16a34a"
NET_LOAD_COLOR = "#fca5a5"
FCR_COLOR = "#0f766e"
MFRR_COLOR = "#d97706"
ACTIVATION_COLOR = "#7c3aed"
GRID_COLOR = "rgba(148, 163, 184, 0.25)"
TEXT_COLOR = "#e5e7eb"


def _series(df: pl.DataFrame, column: str) -> list[float]:
    return df[column].fill_null(0.0).to_list()


def _apply_chart_layout(
    figure: go.Figure,
    *,
    height: int,
    yaxis_title: str,
    yaxis2_title: str | None = None,
    bottom_margin: int = 96,
    legend_y: float = -0.18,
) -> go.Figure:
    layout = {
        "height": height,
        "hovermode": "x unified",
        "margin": dict(l=60, r=44, t=12, b=bottom_margin),
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": dict(family="Inter, Segoe UI, sans-serif", size=13, color=TEXT_COLOR),
        "legend": dict(
            orientation="h",
            yanchor="top",
            y=legend_y,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color=TEXT_COLOR),
            tracegroupgap=12,
        ),
        "xaxis": dict(
            showgrid=False,
            linecolor=GRID_COLOR,
            tickfont=dict(size=12, color=TEXT_COLOR),
            zerolinecolor=GRID_COLOR,
        ),
        "yaxis": dict(
            title=dict(text=yaxis_title, font=dict(color=TEXT_COLOR)),
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            tickfont=dict(color=TEXT_COLOR),
        ),
    }

    if yaxis2_title:
        layout["yaxis2"] = dict(
            title=dict(text=yaxis2_title, font=dict(color=TEXT_COLOR)),
            overlaying="y",
            side="right",
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            tickfont=dict(color=TEXT_COLOR),
        )

    figure.update_layout(**layout)
    return figure


def load_profile_figure(df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()
    x_values = df["timestamp"].to_list()

    figure.add_trace(
        go.Scatter(x=x_values, y=_series(df, "site_load_kw"), mode="lines", name="Load", line=dict(color=LOAD_COLOR))
    )
    figure.add_trace(
        go.Scatter(x=x_values, y=_series(df, "site_pv_kw"), mode="lines", name="PV", line=dict(color=PV_COLOR))
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series(df, "net_load_kw"),
            mode="lines",
            name="Net load",
            line=dict(color=NET_LOAD_COLOR, width=3),
        )
    )

    return _apply_chart_layout(figure, height=440, yaxis_title="kW")


def market_price_figure(df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()
    x_values = df["timestamp"].to_list()

    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series(df, "fcrn_price_eur_mw_h"),
            mode="lines",
            name="FCR-N",
            line=dict(color=FCR_COLOR, width=3),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series(df, "mfrr_capacity_price_eur_mw_h"),
            mode="lines",
            name="mFRR CM",
            line=dict(color=MFRR_COLOR, width=3),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series(df, "mfrr_activation_energy_price_eur_mwh"),
            mode="lines",
            name="mFRR EAM",
            yaxis="y2",
            line=dict(color=ACTIVATION_COLOR, width=2),
        )
    )

    return _apply_chart_layout(
        figure,
        height=400,
        yaxis_title="EUR/MW/h",
        yaxis2_title="EUR/MWh",
        bottom_margin=110,
        legend_y=-0.22,
    )


def activation_figure(df: pl.DataFrame) -> go.Figure:
    figure = go.Figure()
    x_values = df["timestamp"].to_list()

    figure.add_trace(
        go.Bar(
            x=x_values,
            y=_series(df, "mfrr_activation_volume_mw"),
            name="Activation volume",
            marker_color="#60a5fa",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series(df, "mfrr_activation_flag"),
            mode="lines+markers",
            name="Activation flag",
            yaxis="y2",
            line=dict(color=ACTIVATION_COLOR, width=2),
            marker=dict(size=7),
        )
    )

    _apply_chart_layout(figure, height=380, yaxis_title="MW", yaxis2_title="Flag")
    figure.update_layout(
        yaxis2=dict(
            title=dict(text="Flag", font=dict(color=TEXT_COLOR)),
            overlaying="y",
            side="right",
            range=[0, 1.1],
            tickfont=dict(color=TEXT_COLOR),
        )
    )
    return figure
