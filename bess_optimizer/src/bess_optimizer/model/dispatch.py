from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl

from bess_optimizer.model.battery import BatteryState
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.energy_flows import split_pv_and_load
from bess_optimizer.model.rows import base_output_row, refresh_operating_metrics


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


def local_reserve_energy_mwh(local_reserve_mw: float) -> float:
    return max(local_reserve_mw, 0.0)


def remaining_discharge_capacity_mw(
    state: BatteryState,
    *,
    battery_discharge_mw: float,
    local_reserve_mw: float,
    dt_hours: float,
    config: PartAModelConfig,
) -> float:
    if dt_hours <= 0:
        return 0.0
    remaining_power_mw = max(config.battery.power_mw - battery_discharge_mw, 0.0)
    energy_limited_mw = (
        state.available_discharge_mwh(config.battery, local_reserve_energy_mwh(local_reserve_mw))
        * config.battery.discharge_efficiency
        / dt_hours
    )
    return max(min(remaining_power_mw, energy_limited_mw), 0.0)


def apply_local_dispatch(
    source_row: dict[str, Any],
    *,
    scenario: str,
    state: BatteryState,
    thresholds: DispatchThresholds,
    config: PartAModelConfig,
    local_reserve_mw: float,
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
    reserve_energy_mwh = local_reserve_energy_mwh(local_reserve_mw)
    local_power_limit_mw = max(config.battery.power_mw - local_reserve_mw, 0.0)

    if flows["pv_surplus_kw"] > 0:
        battery_charge_mw = state.charge(
            flows["pv_surplus_kw"] / 1000.0,
            config.battery,
            dt_hours,
            power_limit_mw=local_power_limit_mw,
        )
        pv_to_battery_kw = battery_charge_mw * 1000.0
        pv_export_or_curtailed_kw = max(flows["pv_surplus_kw"] - pv_to_battery_kw, 0.0)
    else:
        peak_discharge_kw = max(flows["remaining_load_kw"] - thresholds.peak_threshold_kw, 0.0)
        requested_discharge_kw = peak_discharge_kw
        if spot_price >= thresholds.high_price_eur_mwh:
            requested_discharge_kw = max(requested_discharge_kw, flows["remaining_load_kw"])

        if requested_discharge_kw > 0:
            battery_discharge_mw = state.discharge(
                requested_discharge_kw / 1000.0,
                config.battery,
                dt_hours,
                power_limit_mw=local_power_limit_mw,
                reserve_energy_mwh=reserve_energy_mwh,
            )
            battery_to_load_kw = min(battery_discharge_mw * 1000.0, flows["remaining_load_kw"])

        grid_to_load_after_discharge_kw = max(flows["remaining_load_kw"] - battery_to_load_kw, 0.0)
        can_grid_charge = (
            battery_discharge_mw == 0
            and spot_price <= thresholds.low_price_eur_mwh
            and grid_to_load_after_discharge_kw < thresholds.peak_threshold_kw
        )
        if can_grid_charge:
            peak_safe_charge_kw = max(thresholds.peak_threshold_kw - grid_to_load_after_discharge_kw, 0.0)
            battery_charge_mw = state.charge(
                peak_safe_charge_kw / 1000.0,
                config.battery,
                dt_hours,
                power_limit_mw=local_power_limit_mw,
            )
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
            "local_reserve_mw": local_reserve_mw,
            "energy_cost_eur": energy_cost_eur,
            "local_savings_eur": local_savings_eur,
            "total_value_eur": local_savings_eur,
        }
    )
    refresh_operating_metrics(row)
    used_local_power_mw = max(battery_charge_mw, battery_discharge_mw)
    return LocalDispatchResult(row=row, used_local_power_mw=used_local_power_mw)
