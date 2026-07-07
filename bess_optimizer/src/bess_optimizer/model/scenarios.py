from __future__ import annotations

import polars as pl

from bess_optimizer.model.baselines import (
    run_fcr_only_baseline,
    run_local_only_dispatch,
    run_no_battery_baseline,
)
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.metrics import build_constraint_audit, build_scenario_summary
from bess_optimizer.model.scheduler import run_stacked_schedule
from bess_optimizer.model.schemas import ActivationScenario


def build_activation_scenarios(df: pl.DataFrame) -> list[ActivationScenario]:
    if "mfrr_activation_probability" in df.columns:
        base_activation = float(df["mfrr_activation_probability"].mean() or 0.0)
    else:
        base_activation = float(df["mfrr_activation_flag"].mean() or 0.0)

    return [
        ActivationScenario(name="low_activation", activation_probability=0.0),
        ActivationScenario(name="base_activation", activation_probability=base_activation),
        ActivationScenario(name="high_activation", activation_probability=min(0.75, 2 * base_activation)),
    ]


def run_part_a_scenarios(df: pl.DataFrame, config: PartAModelConfig) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    dispatch_frames = [
        run_no_battery_baseline(df, config),
        run_local_only_dispatch(df, config),
        run_fcr_only_baseline(df, config),
    ]
    for scenario in build_activation_scenarios(df):
        dispatch_frames.append(
            run_stacked_schedule(
                df,
                config,
                activation_probability=scenario.activation_probability,
                scenario_name=f"stacked_{scenario.name}",
            )
        )

    dispatch_df = pl.concat(dispatch_frames, how="vertical")
    summary_df = build_scenario_summary(dispatch_df, config)
    audit_df = build_constraint_audit(dispatch_df, summary_df)

    return dispatch_df, summary_df, audit_df

