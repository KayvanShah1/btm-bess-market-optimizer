from __future__ import annotations

from typing import Literal

import polars as pl
import streamlit as st
from bess_optimizer.settings import settings

DatasetGrain = Literal["hourly", "15min"]

DATASET_FILES: dict[DatasetGrain, str] = {
    "hourly": "representative_day_hourly_se3_20260624.csv",
    "15min": "representative_day_15min_se3_20260624.csv",
}

MODEL_OUTPUT_FILES = {
    "dispatch": "part_a_dispatch_hourly_se3_20260624.csv",
    "summary": "part_a_scenario_summary_se3_20260624.csv",
    "audit": "part_a_constraint_audit_se3_20260624.csv",
    "break_even": "b3_mfrr_break_even_sensitivity_se3_20260624.csv",
}


@st.cache_data(show_spinner=False)
def load_processed_dataset(grain: DatasetGrain) -> pl.DataFrame:
    path = settings.processed_data_dir / DATASET_FILES[grain]
    if not path.exists():
        raise FileNotFoundError(f"Processed dataset not found: {path}")

    return pl.read_csv(path, try_parse_dates=True).sort("timestamp")


def filter_hour_range(df: pl.DataFrame, hour_range: tuple[int, int]) -> pl.DataFrame:
    start_hour, end_hour = hour_range
    return df.filter(pl.col("hour").is_between(start_hour, end_hour))


def summarize_data_tab(df: pl.DataFrame) -> dict[str, float | int | str]:
    activation_probability = df["mfrr_activation_flag"].mean()

    return {
        "rows": df.height,
        "date": str(df["date"].drop_nulls().first()),
        "zone": str(df["bidding_zone"].drop_nulls().first()),
        "peak_net_load_kw": float(df["net_load_kw"].max()),
        "peak_pv_kw": float(df["site_pv_kw"].max()),
        "avg_fcrn_price": float(df["fcrn_price_eur_mw_h"].mean()),
        "avg_mfrr_capacity_price": float(df["mfrr_capacity_price_eur_mw_h"].mean()),
        "activation_probability": float(activation_probability or 0.0),
    }


@st.cache_data(show_spinner=False)
def load_dispatch_output() -> pl.DataFrame:
    path = settings.output_dir / MODEL_OUTPUT_FILES["dispatch"]
    if not path.exists():
        raise FileNotFoundError(f"Part A dispatch output not found: {path}")

    return pl.read_csv(path, try_parse_dates=True).sort(["scenario", "timestamp"])


@st.cache_data(show_spinner=False)
def load_scenario_summary() -> pl.DataFrame:
    path = settings.output_dir / MODEL_OUTPUT_FILES["summary"]
    if not path.exists():
        raise FileNotFoundError(f"Part A scenario summary not found: {path}")

    return pl.read_csv(path)


@st.cache_data(show_spinner=False)
def load_constraint_audit() -> pl.DataFrame:
    path = settings.output_dir / MODEL_OUTPUT_FILES["audit"]
    if not path.exists():
        raise FileNotFoundError(f"Part A constraint audit not found: {path}")

    return pl.read_csv(path)


@st.cache_data(show_spinner=False)
def load_break_even_output() -> pl.DataFrame:
    path = settings.output_dir / MODEL_OUTPUT_FILES["break_even"]
    if not path.exists():
        raise FileNotFoundError(f"B3 break-even output not found: {path}")

    return pl.read_csv(path)
