from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl

from bess_optimizer.model.battery import BatteryState
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.energy_flows import split_pv_and_load
from bess_optimizer.model.schemas import CONSTRAINT_FIELDS, ConstraintStatus, status_label


@dataclass(frozen=True)
class DispatchThresholds:
    low_price_eur_mwh: float
    high_price_eur_mwh: float
    peak_threshold_kw: float


@dataclass(frozen=True)
class LocalDispatchResult:
    row: dict[str, Any]
    used_local_power_mw: float


def compute_dispatch_thresholds(df: pl.DataFrame, config: PartAModelConfig) -> DispatchThresholds:
    return DispatchThresholds(
        low_price_eur_mwh=float(df["spot_price_eur_mwh"].quantile(config.site.low_price_quantile)),
        high_price_eur_mwh=float(df["spot_price_eur_mwh"].quantile(config.site.high_price_quantile)),
        peak_threshold_kw=float(df["net_load_kw"].quantile(config.site.peak_threshold_quantile)),
    )


def local_reserve_requirement(
    rows: list[dict[str, Any]],
    index: int,
    peak_threshold_kw: float,
    config: PartAModelConfig,
) -> float:
    lookahead_end = min(index + config.site.local_peak_lookahead_hours + 1, len(rows))
    lookahead_net_peak_kw = max(float(row["net_load_kw"]) for row in rows[index:lookahead_end])
    peak_excess_kw = max(lookahead_net_peak_kw - peak_threshold_kw, 0.0)
    return min(config.battery.power_mw, peak_excess_kw / 1000.0)


def zero_constraint_values() -> dict[str, bool]:
    return {field: False for field in CONSTRAINT_FIELDS}


def add_constraint_fields(row: dict[str, Any], status: ConstraintStatus) -> dict[str, Any]:
    row.update(status.model_dump())
    row["constraint_status"] = status_label(status)
    return row


def build_constraint_status(
    *,
    soc_mwh: float,
    battery_charge_mw: float,
    battery_discharge_mw: float,
    local_reserve_mw: float,
    fcr_commit_mw: float,
    mfrr_commit_mw: float,
    grid_to_battery_kw: float,
    grid_import_kw: float,
    peak_threshold_kw: float,
    config: PartAModelConfig,
    fcr_headroom_violation: bool = False,
    mfrr_readiness_violation: bool = False,
    savings_floor_violation: bool = False,
) -> ConstraintStatus:
    epsilon = 1e-9
    return ConstraintStatus(
        soc_min_violation=soc_mwh < config.battery.min_soc_mwh - epsilon,
        soc_max_violation=soc_mwh > config.battery.max_soc_mwh + epsilon,
        power_limit_violation=max(battery_charge_mw, battery_discharge_mw) > config.battery.power_mw + epsilon,
        shared_capacity_violation=local_reserve_mw + fcr_commit_mw + mfrr_commit_mw > config.battery.power_mw + epsilon,
        peak_import_violation=grid_to_battery_kw > 0 and grid_import_kw > peak_threshold_kw + epsilon,
        fcr_headroom_violation=fcr_headroom_violation,
        mfrr_readiness_violation=mfrr_readiness_violation,
        savings_floor_violation=savings_floor_violation,
    )


def fcr_headroom_violation(soc_mwh: float, fcr_commit_mw: float, config: PartAModelConfig) -> bool:
    if fcr_commit_mw <= 1e-9:
        return False

    buffer_mwh = fcr_commit_mw * config.reserve.fcr_response_buffer_hours
    return not (
        config.battery.min_soc_mwh + buffer_mwh <= soc_mwh + 1e-9
        and soc_mwh <= config.battery.max_soc_mwh - buffer_mwh + 1e-9
    )


def base_output_row(
    source_row: dict[str, Any],
    *,
    scenario: str,
    service_selected: str,
    soc_mwh: float,
    flows: dict[str, float],
    peak_threshold_kw: float,
) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "timestamp": source_row["timestamp"],
        "date": source_row["date"],
        "hour": int(source_row["hour"]),
        "dt_hours": float(source_row["dt_hours"]),
        "bidding_zone": source_row["bidding_zone"],
        "site_load_kw": float(source_row["site_load_kw"]),
        "site_pv_kw": float(source_row["site_pv_kw"]),
        "net_load_kw": float(source_row["net_load_kw"]),
        "spot_price_eur_mwh": float(source_row["spot_price_eur_mwh"]),
        "fcrn_price_eur_mw_h": float(source_row["fcrn_price_eur_mw_h"]),
        "mfrr_capacity_price_eur_mw_h": float(source_row["mfrr_capacity_price_eur_mw_h"]),
        "mfrr_capacity_volume_mw": float(source_row["mfrr_capacity_volume_mw"]),
        "mfrr_activation_energy_price_eur_mwh": float(source_row["mfrr_activation_energy_price_eur_mwh"]),
        "mfrr_activation_probability": float(source_row.get("mfrr_activation_probability") or 0.0),
        "mfrr_activation_flag": int(source_row.get("mfrr_activation_flag") or 0),
        "mfrr_activation_volume_mw": float(source_row.get("mfrr_activation_volume_mw") or 0.0),
        "pv_to_load_kw": flows["pv_to_load_kw"],
        "pv_to_battery_kw": 0.0,
        "pv_export_or_curtailed_kw": flows["pv_surplus_kw"],
        "grid_to_load_kw": flows["remaining_load_kw"],
        "grid_to_battery_kw": 0.0,
        "battery_to_load_kw": 0.0,
        "grid_import_kw": flows["remaining_load_kw"],
        "battery_charge_mw": 0.0,
        "battery_discharge_mw": 0.0,
        "soc_mwh": soc_mwh,
        "peak_threshold_kw": peak_threshold_kw,
        "local_reserve_mw": 0.0,
        "fcr_commit_mw": 0.0,
        "mfrr_commit_mw": 0.0,
        "service_selected": service_selected,
        "energy_cost_eur": 0.0,
        "local_savings_eur": 0.0,
        "fcr_revenue_eur": 0.0,
        "mfrr_capacity_revenue_eur": 0.0,
        "expected_mfrr_activation_revenue_eur": 0.0,
        "total_value_eur": 0.0,
        "constraint_status": "ok",
        **zero_constraint_values(),
    }


def apply_local_dispatch(
    source_row: dict[str, Any],
    *,
    scenario: str,
    state: BatteryState,
    thresholds: DispatchThresholds,
    config: PartAModelConfig,
    service_selected: str,
) -> LocalDispatchResult:
    dt_hours = float(source_row["dt_hours"])
    spot_price = float(source_row["spot_price_eur_mwh"])
    flows = split_pv_and_load(float(source_row["site_load_kw"]), float(source_row["site_pv_kw"]))
    row = base_output_row(
        source_row,
        scenario=scenario,
        service_selected=service_selected,
        soc_mwh=state.soc_mwh,
        flows=flows,
        peak_threshold_kw=thresholds.peak_threshold_kw,
    )

    pv_to_battery_kw = 0.0
    pv_export_or_curtailed_kw = flows["pv_surplus_kw"]
    grid_to_battery_kw = 0.0
    battery_to_load_kw = 0.0
    battery_charge_mw = 0.0
    battery_discharge_mw = 0.0

    if flows["pv_surplus_kw"] > 0:
        battery_charge_mw = state.charge(flows["pv_surplus_kw"] / 1000.0, config.battery, dt_hours)
        pv_to_battery_kw = battery_charge_mw * 1000.0
        pv_export_or_curtailed_kw = max(flows["pv_surplus_kw"] - pv_to_battery_kw, 0.0)
    else:
        peak_discharge_kw = max(flows["remaining_load_kw"] - thresholds.peak_threshold_kw, 0.0)
        requested_discharge_kw = peak_discharge_kw
        if spot_price >= thresholds.high_price_eur_mwh:
            requested_discharge_kw = max(requested_discharge_kw, flows["remaining_load_kw"])

        if requested_discharge_kw > 0:
            battery_discharge_mw = state.discharge(requested_discharge_kw / 1000.0, config.battery, dt_hours)
            battery_to_load_kw = min(battery_discharge_mw * 1000.0, flows["remaining_load_kw"])

        grid_to_load_after_discharge_kw = max(flows["remaining_load_kw"] - battery_to_load_kw, 0.0)
        can_grid_charge = (
            battery_discharge_mw == 0
            and spot_price <= thresholds.low_price_eur_mwh
            and grid_to_load_after_discharge_kw < thresholds.peak_threshold_kw
        )
        if can_grid_charge:
            peak_safe_charge_kw = max(thresholds.peak_threshold_kw - grid_to_load_after_discharge_kw, 0.0)
            battery_charge_mw = state.charge(peak_safe_charge_kw / 1000.0, config.battery, dt_hours)
            grid_to_battery_kw = battery_charge_mw * 1000.0

    grid_to_load_kw = max(flows["remaining_load_kw"] - battery_to_load_kw, 0.0)
    grid_import_kw = grid_to_load_kw + grid_to_battery_kw
    energy_cost_eur = grid_import_kw / 1000.0 * dt_hours * spot_price
    no_battery_energy_cost_eur = flows["remaining_load_kw"] / 1000.0 * dt_hours * spot_price
    local_savings_eur = no_battery_energy_cost_eur - energy_cost_eur

    row.update(
        {
            "pv_to_battery_kw": pv_to_battery_kw,
            "pv_export_or_curtailed_kw": pv_export_or_curtailed_kw,
            "grid_to_load_kw": grid_to_load_kw,
            "grid_to_battery_kw": grid_to_battery_kw,
            "battery_to_load_kw": battery_to_load_kw,
            "grid_import_kw": grid_import_kw,
            "battery_charge_mw": battery_charge_mw,
            "battery_discharge_mw": battery_discharge_mw,
            "soc_mwh": state.soc_mwh,
            "energy_cost_eur": energy_cost_eur,
            "local_savings_eur": local_savings_eur,
            "total_value_eur": local_savings_eur,
        }
    )
    used_local_power_mw = max(battery_charge_mw, battery_discharge_mw)
    return LocalDispatchResult(row=row, used_local_power_mw=used_local_power_mw)


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
            service_selected="local_only",
        )
        local_reserve_mw = local_reserve_requirement(input_rows, index, thresholds.peak_threshold_kw, config)
        result.row["local_reserve_mw"] = local_reserve_mw
        status = build_constraint_status(
            soc_mwh=float(result.row["soc_mwh"]),
            battery_charge_mw=float(result.row["battery_charge_mw"]),
            battery_discharge_mw=float(result.row["battery_discharge_mw"]),
            local_reserve_mw=local_reserve_mw,
            fcr_commit_mw=0.0,
            mfrr_commit_mw=0.0,
            grid_to_battery_kw=float(result.row["grid_to_battery_kw"]),
            grid_import_kw=float(result.row["grid_import_kw"]),
            peak_threshold_kw=thresholds.peak_threshold_kw,
            config=config,
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
        result = apply_local_dispatch(
            source_row,
            scenario="fcr_only",
            state=state,
            thresholds=thresholds,
            config=config,
            service_selected="local_plus_fcr",
        )
        dt_hours = float(source_row["dt_hours"])
        local_reserve_mw = local_reserve_requirement(input_rows, index, thresholds.peak_threshold_kw, config)
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
            fcr_headroom_violation=fcr_headroom_violation(state.soc_mwh, best_fcr_mw, config),
        )
        rows.append(add_constraint_fields(result.row, status))

    return pl.DataFrame(rows)
