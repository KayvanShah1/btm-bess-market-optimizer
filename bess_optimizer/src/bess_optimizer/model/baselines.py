from __future__ import annotations

import polars as pl

from bess_optimizer.model.battery import BatteryState
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.constraints import build_constraint_status, fcr_headroom_violation
from bess_optimizer.model.dispatch import (
    apply_local_dispatch,
    compute_dispatch_thresholds,
    local_reserve_requirement,
    remaining_discharge_capacity_mw,
)
from bess_optimizer.model.energy_flows import split_pv_and_load
from bess_optimizer.model.rows import add_constraint_fields, base_output_row, refresh_operating_metrics


def run_no_battery_baseline(df: pl.DataFrame, config: PartAModelConfig) -> pl.DataFrame:
    thresholds = compute_dispatch_thresholds(df, config)
    rows = []
    for source_row in df.to_dicts():
        dt_hours = float(source_row["dt_hours"])
        spot_price = float(source_row["spot_price_eur_mwh"])
        flows = split_pv_and_load(float(source_row["site_load_kw"]), float(source_row["site_pv_kw"]))
        row = base_output_row(
            source_row,
            scenario="no_battery",
            service_selected="no_battery",
            soc_mwh=config.battery.initial_soc_mwh,
            flows=flows,
            peak_threshold_kw=thresholds.peak_threshold_kw,
        )
        row["energy_cost_eur"] = row["grid_import_kw"] / 1000.0 * dt_hours * spot_price
        rows.append(row)
    return pl.DataFrame(rows)


def run_local_only_dispatch(df: pl.DataFrame, config: PartAModelConfig) -> pl.DataFrame:
    thresholds = compute_dispatch_thresholds(df, config)
    input_rows = df.to_dicts()
    state = BatteryState(soc_mwh=config.battery.initial_soc_mwh)
    rows = []

    for index, source_row in enumerate(input_rows):
        result = apply_local_dispatch(
            source_row,
            scenario="local_only",
            state=state,
            thresholds=thresholds,
            config=config,
            local_reserve_mw=local_reserve_requirement(input_rows, index, thresholds.peak_threshold_kw, config),
            service_selected="local_only",
        )
        status = build_constraint_status(
            soc_mwh=float(result.row["soc_mwh"]),
            battery_charge_mw=float(result.row["battery_charge_mw"]),
            battery_discharge_mw=float(result.row["battery_discharge_mw"]),
            local_reserve_mw=float(result.row["local_reserve_mw"]),
            fcr_commit_mw=0.0,
            mfrr_commit_mw=0.0,
            grid_to_battery_kw=float(result.row["grid_to_battery_kw"]),
            grid_import_kw=float(result.row["grid_import_kw"]),
            peak_threshold_kw=thresholds.peak_threshold_kw,
            config=config,
            battery_available_discharge_mw=remaining_discharge_capacity_mw(
                state,
                battery_discharge_mw=float(result.row["battery_discharge_mw"]),
                local_reserve_mw=float(result.row["local_reserve_mw"]),
                dt_hours=float(source_row["dt_hours"]),
                config=config,
            ),
        )
        rows.append(add_constraint_fields(result.row, status))

    return pl.DataFrame(rows)


def run_fcr_only_baseline(df: pl.DataFrame, config: PartAModelConfig) -> pl.DataFrame:
    thresholds = compute_dispatch_thresholds(df, config)
    input_rows = df.to_dicts()
    state = BatteryState(soc_mwh=config.battery.initial_soc_mwh)
    rows = []
    step = config.reserve.market_capacity_step_mw

    for index, source_row in enumerate(input_rows):
        local_reserve_mw = local_reserve_requirement(input_rows, index, thresholds.peak_threshold_kw, config)
        result = apply_local_dispatch(
            source_row,
            scenario="fcr_only",
            state=state,
            thresholds=thresholds,
            config=config,
            local_reserve_mw=local_reserve_mw,
            service_selected="local_plus_fcr",
        )
        dt_hours = float(source_row["dt_hours"])
        available_mw = max(config.battery.power_mw - result.used_local_power_mw - local_reserve_mw, 0.0)
        available_mw = (available_mw // step) * step

        best_fcr_mw = 0.0
        best_revenue = 0.0
        candidate_mw = 0.0
        while candidate_mw <= available_mw + 1e-9:
            if not fcr_headroom_violation(state.soc_mwh, candidate_mw, config):
                revenue = candidate_mw * float(source_row["fcrn_price_eur_mw_h"]) * dt_hours
                if revenue >= best_revenue:
                    best_fcr_mw = candidate_mw
                    best_revenue = revenue
            candidate_mw += step

        result.row["local_reserve_mw"] = local_reserve_mw
        result.row["fcr_commit_mw"] = best_fcr_mw
        result.row["fcr_revenue_eur"] = best_revenue
        result.row["total_value_eur"] = float(result.row["local_savings_eur"]) + best_revenue
        result.row["service_selected"] = "local_plus_fcr" if best_fcr_mw > 0 else "local_only"
        refresh_operating_metrics(result.row)

        status = build_constraint_status(
            soc_mwh=float(result.row["soc_mwh"]),
            battery_charge_mw=float(result.row["battery_charge_mw"]),
            battery_discharge_mw=float(result.row["battery_discharge_mw"]),
            local_reserve_mw=local_reserve_mw,
            fcr_commit_mw=best_fcr_mw,
            mfrr_commit_mw=0.0,
            grid_to_battery_kw=float(result.row["grid_to_battery_kw"]),
            grid_import_kw=float(result.row["grid_import_kw"]),
            peak_threshold_kw=thresholds.peak_threshold_kw,
            config=config,
            battery_available_discharge_mw=remaining_discharge_capacity_mw(
                state,
                battery_discharge_mw=float(result.row["battery_discharge_mw"]),
                local_reserve_mw=local_reserve_mw,
                dt_hours=dt_hours,
                config=config,
            ),
            fcr_headroom_violation=fcr_headroom_violation(state.soc_mwh, best_fcr_mw, config),
        )
        rows.append(add_constraint_fields(result.row, status))

    return pl.DataFrame(rows)
