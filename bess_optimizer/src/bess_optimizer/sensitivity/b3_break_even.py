from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import polars as pl

from bess_optimizer.model.baselines import run_fcr_only_baseline, run_no_battery_baseline
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.metrics import build_scenario_summary
from bess_optimizer.model.scheduler import run_stacked_schedule

DEFAULT_ACTIVATION_PROBABILITIES = tuple(round(value * 0.05, 2) for value in range(16))
DEFAULT_MFRR_CAPACITY_PRICE_MULTIPLIERS = (0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00)
DEFAULT_BATTERY_COUNTS = (1, 2, 3)


def apply_mfrr_capacity_price_multiplier(df: pl.DataFrame, multiplier: float) -> pl.DataFrame:
    if "mfrr_capacity_price_eur_mw_h" not in df.columns:
        raise ValueError("Input data must include mfrr_capacity_price_eur_mw_h")

    return df.with_columns(
        (pl.col("mfrr_capacity_price_eur_mw_h") * multiplier).alias("mfrr_capacity_price_eur_mw_h")
    )


def _summary_row(summary_df: pl.DataFrame, scenario: str) -> dict[str, Any]:
    rows = summary_df.filter(pl.col("scenario") == scenario).to_dicts()
    if not rows:
        raise ValueError(f"Scenario not found in summary: {scenario}")
    return rows[0]


def compare_against_fcr_only(summary_df: pl.DataFrame, stacked_scenario: str) -> dict[str, float | bool]:
    fcr_row = _summary_row(summary_df, "fcr_only")
    stacked_row = _summary_row(summary_df, stacked_scenario)

    fcr_only_total_value_eur = float(fcr_row["total_value_eur"])
    stacked_total_value_eur = float(stacked_row["total_value_eur"])
    delta_vs_fcr_only_eur = stacked_total_value_eur - fcr_only_total_value_eur

    return {
        "stacked_total_value_eur": stacked_total_value_eur,
        "fcr_only_total_value_eur": fcr_only_total_value_eur,
        "delta_vs_fcr_only_eur": delta_vs_fcr_only_eur,
        "is_mfrr_worthwhile": delta_vs_fcr_only_eur > 0,
        "stacked_local_savings_eur": float(stacked_row["local_savings_eur"]),
        "stacked_local_savings_pct": float(stacked_row["local_savings_pct"]),
        "stacked_fcr_revenue_eur": float(stacked_row["fcr_revenue_eur"]),
        "stacked_mfrr_capacity_revenue_eur": float(stacked_row["mfrr_capacity_revenue_eur"]),
        "stacked_expected_mfrr_activation_revenue_eur": float(
            stacked_row["expected_mfrr_activation_revenue_eur"]
        ),
        "stacked_min_soc_mwh": float(stacked_row["min_soc_mwh"]),
        "stacked_max_soc_mwh": float(stacked_row["max_soc_mwh"]),
        "stacked_constraint_violation_count": int(stacked_row["constraint_violation_count"]),
        "stacked_savings_floor_pass": bool(stacked_row["savings_floor_pass"]),
    }


def _coerce_float_grid(values: Iterable[float]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _coerce_int_grid(values: Iterable[int]) -> tuple[int, ...]:
    return tuple(int(value) for value in values)


def scale_config_for_battery_count(config: PartAModelConfig, battery_count: int) -> PartAModelConfig:
    if battery_count < 1:
        raise ValueError("battery_count must be at least 1")

    scaled_battery = config.battery.model_copy(
        update={
            "power_mw": config.battery.power_mw * battery_count,
            "energy_mwh": config.battery.energy_mwh * battery_count,
            "initial_soc_mwh": config.battery.initial_soc_mwh * battery_count,
            "min_soc_mwh": config.battery.min_soc_mwh * battery_count,
            "max_soc_mwh": config.battery.max_soc_mwh * battery_count,
        }
    )
    return config.model_copy(update={"battery": scaled_battery})


def run_b3_break_even_grid(
    df: pl.DataFrame,
    config: PartAModelConfig,
    *,
    activation_probabilities: Iterable[float] = DEFAULT_ACTIVATION_PROBABILITIES,
    mfrr_capacity_price_multipliers: Iterable[float] = DEFAULT_MFRR_CAPACITY_PRICE_MULTIPLIERS,
    battery_counts: Iterable[int] = DEFAULT_BATTERY_COUNTS,
) -> pl.DataFrame:
    activation_grid = _coerce_float_grid(activation_probabilities)
    multiplier_grid = _coerce_float_grid(mfrr_capacity_price_multipliers)
    battery_count_grid = _coerce_int_grid(battery_counts)

    rows = []
    for battery_count in battery_count_grid:
        scenario_config = scale_config_for_battery_count(config, battery_count)
        no_battery_dispatch = run_no_battery_baseline(df, scenario_config)
        fcr_only_dispatch = run_fcr_only_baseline(df, scenario_config)

        for activation_probability in activation_grid:
            for multiplier in multiplier_grid:
                scenario_name = "stacked_b3_break_even"
                adjusted_df = apply_mfrr_capacity_price_multiplier(df, multiplier)
                stacked_dispatch = run_stacked_schedule(
                    adjusted_df,
                    scenario_config,
                    activation_probability=activation_probability,
                    scenario_name=scenario_name,
                )
                summary_df = build_scenario_summary(
                    pl.concat([no_battery_dispatch, fcr_only_dispatch, stacked_dispatch], how="vertical"),
                    scenario_config,
                )
                comparison = compare_against_fcr_only(summary_df, scenario_name)
                rows.append(
                    {
                        "battery_count": battery_count,
                        "battery_power_mw": scenario_config.battery.power_mw,
                        "battery_energy_mwh": scenario_config.battery.energy_mwh,
                        "usable_soc_headroom_mwh": (
                            scenario_config.battery.max_soc_mwh - scenario_config.battery.min_soc_mwh
                        ),
                        "activation_probability": activation_probability,
                        "mfrr_capacity_price_multiplier": multiplier,
                        **comparison,
                    }
                )

    return pl.DataFrame(rows).sort(
        ["battery_count", "activation_probability", "mfrr_capacity_price_multiplier"]
    )


def summarize_break_even_result(break_even_df: pl.DataFrame) -> dict[str, float | int | None]:
    if break_even_df.is_empty():
        return {
            "cell_count": 0,
            "worthwhile_cell_count": 0,
            "best_case_delta_eur": None,
            "worst_case_delta_eur": None,
            "max_activation_probability_at_1x_capacity": None,
            "lowest_worthwhile_capacity_multiplier": None,
        }

    worthwhile = break_even_df.filter(pl.col("is_mfrr_worthwhile"))
    one_x = break_even_df.filter(pl.col("mfrr_capacity_price_multiplier") == 1.0)
    one_x_worthwhile = one_x.filter(pl.col("is_mfrr_worthwhile"))

    return {
        "cell_count": break_even_df.height,
        "worthwhile_cell_count": worthwhile.height,
        "best_case_delta_eur": float(break_even_df["delta_vs_fcr_only_eur"].max()),
        "worst_case_delta_eur": float(break_even_df["delta_vs_fcr_only_eur"].min()),
        "max_activation_probability_at_1x_capacity": (
            None if one_x_worthwhile.is_empty() else float(one_x_worthwhile["activation_probability"].max())
        ),
        "lowest_worthwhile_capacity_multiplier": (
            None if worthwhile.is_empty() else float(worthwhile["mfrr_capacity_price_multiplier"].min())
        ),
    }
