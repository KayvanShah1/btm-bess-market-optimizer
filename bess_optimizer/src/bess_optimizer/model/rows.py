from __future__ import annotations

from typing import Any

from bess_optimizer.model.schemas import CONSTRAINT_FIELDS, ConstraintStatus, status_label


def zero_constraint_values() -> dict[str, bool]:
    return {field: False for field in CONSTRAINT_FIELDS}


def add_constraint_fields(row: dict[str, Any], status: ConstraintStatus) -> dict[str, Any]:
    row.update(status.model_dump())
    row["constraint_status"] = status_label(status)
    return row


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
        "residual_peak_exposure_kw": max(flows["remaining_load_kw"] - peak_threshold_kw, 0.0),
        "local_reserve_mw": 0.0,
        "local_physical_power_mw": 0.0,
        "total_reserved_or_used_mw": 0.0,
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


def refresh_operating_metrics(row: dict[str, Any]) -> None:
    local_physical_power_mw = max(float(row["battery_charge_mw"]), float(row["battery_discharge_mw"]))
    row["local_physical_power_mw"] = local_physical_power_mw
    row["total_reserved_or_used_mw"] = (
        local_physical_power_mw
        + float(row["local_reserve_mw"])
        + float(row["fcr_commit_mw"])
        + float(row["mfrr_commit_mw"])
    )
    row["residual_peak_exposure_kw"] = max(float(row["grid_import_kw"]) - float(row["peak_threshold_kw"]), 0.0)
