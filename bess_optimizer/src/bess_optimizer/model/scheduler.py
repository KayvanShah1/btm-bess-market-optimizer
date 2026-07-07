from __future__ import annotations

from typing import Any

import polars as pl

from bess_optimizer.model.baselines import (
    add_constraint_fields,
    apply_local_dispatch,
    build_constraint_status,
    compute_dispatch_thresholds,
    fcr_headroom_violation,
    local_reserve_requirement,
)
from bess_optimizer.model.battery import BatteryState
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.schemas import CandidateAllocation


def round_down_to_step(value: float, step: float) -> float:
    if step <= 0:
        return max(value, 0.0)
    return max((value // step) * step, 0.0)


def generate_candidate_allocations(
    local_reserve_mw: float,
    available_market_mw: float,
    step: float,
) -> list[CandidateAllocation]:
    max_market_mw = round_down_to_step(available_market_mw, step)
    candidates = []
    fcr_commit_mw = 0.0
    while fcr_commit_mw <= max_market_mw + 1e-9:
        mfrr_commit_mw = 0.0
        while fcr_commit_mw + mfrr_commit_mw <= max_market_mw + 1e-9:
            candidates.append(
                CandidateAllocation(
                    local_reserve_mw=local_reserve_mw,
                    fcr_commit_mw=round(fcr_commit_mw, 10),
                    mfrr_commit_mw=round(mfrr_commit_mw, 10),
                )
            )
            mfrr_commit_mw += step
        fcr_commit_mw += step
    return candidates


def mfrr_readiness_violation(soc_mwh: float, mfrr_commit_mw: float, config: PartAModelConfig) -> bool:
    if mfrr_commit_mw <= 1e-9:
        return False

    required_mwh = mfrr_commit_mw * config.reserve.mfrr_activation_duration_hours
    return soc_mwh < config.battery.min_soc_mwh + required_mwh - 1e-9


def candidate_revenue(
    source_row: dict[str, Any],
    candidate: CandidateAllocation,
    activation_probability: float,
    config: PartAModelConfig,
) -> dict[str, float]:
    dt_hours = float(source_row["dt_hours"])
    spot_price = float(source_row["spot_price_eur_mwh"])
    activation_price = float(source_row["mfrr_activation_energy_price_eur_mwh"])
    activation_margin_eur_mwh = max(
        0.0,
        activation_price
        - spot_price / config.battery.discharge_efficiency
        - config.battery.degradation_cost_eur_per_mwh,
    )
    fcr_revenue = candidate.fcr_commit_mw * float(source_row["fcrn_price_eur_mw_h"]) * dt_hours
    mfrr_capacity_revenue = candidate.mfrr_commit_mw * float(source_row["mfrr_capacity_price_eur_mw_h"]) * dt_hours
    expected_mfrr_activation_revenue = (
        candidate.mfrr_commit_mw
        * activation_probability
        * config.reserve.mfrr_activation_duration_hours
        * activation_margin_eur_mwh
    )
    return {
        "fcr_revenue_eur": fcr_revenue,
        "mfrr_capacity_revenue_eur": mfrr_capacity_revenue,
        "expected_mfrr_activation_revenue_eur": expected_mfrr_activation_revenue,
        "candidate_value_eur": fcr_revenue + mfrr_capacity_revenue + expected_mfrr_activation_revenue,
    }


def candidate_is_feasible(
    *,
    candidate: CandidateAllocation,
    soc_mwh: float,
    battery_charge_mw: float,
    battery_discharge_mw: float,
    grid_to_battery_kw: float,
    grid_import_kw: float,
    peak_threshold_kw: float,
    config: PartAModelConfig,
) -> bool:
    status = build_constraint_status(
        soc_mwh=soc_mwh,
        battery_charge_mw=battery_charge_mw,
        battery_discharge_mw=battery_discharge_mw,
        local_reserve_mw=candidate.local_reserve_mw,
        fcr_commit_mw=candidate.fcr_commit_mw,
        mfrr_commit_mw=candidate.mfrr_commit_mw,
        grid_to_battery_kw=grid_to_battery_kw,
        grid_import_kw=grid_import_kw,
        peak_threshold_kw=peak_threshold_kw,
        config=config,
        fcr_headroom_violation=fcr_headroom_violation(soc_mwh, candidate.fcr_commit_mw, config),
        mfrr_readiness_violation=mfrr_readiness_violation(soc_mwh, candidate.mfrr_commit_mw, config),
    )
    return status.feasible


def run_stacked_schedule(
    df: pl.DataFrame,
    config: PartAModelConfig,
    activation_probability: float,
    scenario_name: str,
) -> pl.DataFrame:
    thresholds = compute_dispatch_thresholds(df, config)
    input_rows = df.to_dicts()
    state = BatteryState(soc_mwh=config.battery.initial_soc_mwh)
    output_rows = []

    for index, source_row in enumerate(input_rows):
        result = apply_local_dispatch(
            source_row,
            scenario=scenario_name,
            state=state,
            thresholds=thresholds,
            config=config,
            service_selected="stacked",
        )
        local_reserve_mw = local_reserve_requirement(input_rows, index, thresholds.peak_threshold_kw, config)
        available_market_mw = max(
            0.0,
            config.battery.power_mw - result.used_local_power_mw - local_reserve_mw,
        )
        available_market_mw = round_down_to_step(available_market_mw, config.reserve.market_capacity_step_mw)

        candidates = generate_candidate_allocations(
            local_reserve_mw,
            available_market_mw,
            config.reserve.market_capacity_step_mw,
        )
        best_candidate = candidates[0]
        best_revenue = {
            "fcr_revenue_eur": 0.0,
            "mfrr_capacity_revenue_eur": 0.0,
            "expected_mfrr_activation_revenue_eur": 0.0,
            "candidate_value_eur": 0.0,
        }

        for candidate in candidates:
            if not candidate_is_feasible(
                candidate=candidate,
                soc_mwh=state.soc_mwh,
                battery_charge_mw=float(result.row["battery_charge_mw"]),
                battery_discharge_mw=float(result.row["battery_discharge_mw"]),
                grid_to_battery_kw=float(result.row["grid_to_battery_kw"]),
                grid_import_kw=float(result.row["grid_import_kw"]),
                peak_threshold_kw=thresholds.peak_threshold_kw,
                config=config,
            ):
                continue
            revenue = candidate_revenue(source_row, candidate, activation_probability, config)
            if revenue["candidate_value_eur"] >= best_revenue["candidate_value_eur"]:
                best_candidate = candidate
                best_revenue = revenue

        expected_activation_discharge_mwh = (
            best_candidate.mfrr_commit_mw
            * activation_probability
            * config.reserve.mfrr_activation_duration_hours
        )
        if expected_activation_discharge_mwh > 0:
            state.soc_mwh -= expected_activation_discharge_mwh / config.battery.discharge_efficiency

        service_selected = "stacked_hold"
        if best_candidate.fcr_commit_mw > 0 and best_candidate.mfrr_commit_mw > 0:
            service_selected = "local_fcr_mfrr"
        elif best_candidate.fcr_commit_mw > 0:
            service_selected = "local_fcr"
        elif best_candidate.mfrr_commit_mw > 0:
            service_selected = "local_mfrr"
        elif result.used_local_power_mw > 0:
            service_selected = "local_only"

        result.row["soc_mwh"] = state.soc_mwh
        result.row["local_reserve_mw"] = best_candidate.local_reserve_mw
        result.row["fcr_commit_mw"] = best_candidate.fcr_commit_mw
        result.row["mfrr_commit_mw"] = best_candidate.mfrr_commit_mw
        result.row["service_selected"] = service_selected
        result.row["fcr_revenue_eur"] = best_revenue["fcr_revenue_eur"]
        result.row["mfrr_capacity_revenue_eur"] = best_revenue["mfrr_capacity_revenue_eur"]
        result.row["expected_mfrr_activation_revenue_eur"] = best_revenue["expected_mfrr_activation_revenue_eur"]
        result.row["total_value_eur"] = float(result.row["local_savings_eur"]) + best_revenue["candidate_value_eur"]

        status = build_constraint_status(
            soc_mwh=state.soc_mwh,
            battery_charge_mw=float(result.row["battery_charge_mw"]),
            battery_discharge_mw=float(result.row["battery_discharge_mw"]),
            local_reserve_mw=best_candidate.local_reserve_mw,
            fcr_commit_mw=best_candidate.fcr_commit_mw,
            mfrr_commit_mw=best_candidate.mfrr_commit_mw,
            grid_to_battery_kw=float(result.row["grid_to_battery_kw"]),
            grid_import_kw=float(result.row["grid_import_kw"]),
            peak_threshold_kw=thresholds.peak_threshold_kw,
            config=config,
            fcr_headroom_violation=fcr_headroom_violation(state.soc_mwh, best_candidate.fcr_commit_mw, config),
            mfrr_readiness_violation=mfrr_readiness_violation(state.soc_mwh, best_candidate.mfrr_commit_mw, config),
        )
        output_rows.append(add_constraint_fields(result.row, status))

    return pl.DataFrame(output_rows)
