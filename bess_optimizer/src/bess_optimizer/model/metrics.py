from __future__ import annotations

import polars as pl

from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.schemas import CONSTRAINT_FIELDS


def build_scenario_summary(dispatch_df: pl.DataFrame, config: PartAModelConfig) -> pl.DataFrame:
    no_battery = dispatch_df.filter(pl.col("scenario") == "no_battery")
    no_battery_energy_cost = float(no_battery["energy_cost_eur"].sum())
    no_battery_peak_kw = float(no_battery["grid_import_kw"].max())
    no_battery_customer_cost = no_battery_energy_cost + (
        no_battery_peak_kw * config.site.peak_tariff_eur_per_kw_day
    )

    rows = []
    for scenario in dispatch_df["scenario"].unique(maintain_order=True).to_list():
        scenario_df = dispatch_df.filter(pl.col("scenario") == scenario)
        total_energy_cost = float(scenario_df["energy_cost_eur"].sum())
        peak_import_kw = float(scenario_df["grid_import_kw"].max())
        peak_cost_eur = peak_import_kw * config.site.peak_tariff_eur_per_kw_day
        customer_cost_eur = total_energy_cost + peak_cost_eur
        local_savings_eur = 0.0 if scenario == "no_battery" else no_battery_customer_cost - customer_cost_eur
        local_savings_pct = 0.0 if no_battery_customer_cost == 0 else local_savings_eur / no_battery_customer_cost
        fcr_revenue = float(scenario_df["fcr_revenue_eur"].sum())
        mfrr_capacity_revenue = float(scenario_df["mfrr_capacity_revenue_eur"].sum())
        expected_mfrr_activation_revenue = float(scenario_df["expected_mfrr_activation_revenue_eur"].sum())
        total_market_revenue = fcr_revenue + mfrr_capacity_revenue + expected_mfrr_activation_revenue
        total_value = local_savings_eur + total_market_revenue
        row_violation_count = int((scenario_df["constraint_status"] != "ok").sum())
        savings_floor_pass = scenario == "no_battery" or local_savings_pct >= config.site.minimum_savings_pct
        constraint_violation_count = row_violation_count + (0 if savings_floor_pass else 1)

        rows.append(
            {
                "scenario": scenario,
                "total_energy_cost_eur": total_energy_cost,
                "peak_import_kw": peak_import_kw,
                "peak_cost_eur": peak_cost_eur,
                "customer_cost_eur": customer_cost_eur,
                "local_savings_eur": local_savings_eur,
                "local_savings_pct": local_savings_pct,
                "fcr_revenue_eur": fcr_revenue,
                "mfrr_capacity_revenue_eur": mfrr_capacity_revenue,
                "expected_mfrr_activation_revenue_eur": expected_mfrr_activation_revenue,
                "total_market_revenue_eur": total_market_revenue,
                "total_value_eur": total_value,
                "delta_vs_fcr_only_eur": 0.0,
                "min_soc_mwh": float(scenario_df["soc_mwh"].min()),
                "max_soc_mwh": float(scenario_df["soc_mwh"].max()),
                "peak_import_reduction_kw": no_battery_peak_kw - peak_import_kw,
                "constraint_violation_count": constraint_violation_count,
                "savings_floor_pass": savings_floor_pass,
            }
        )

    fcr_total_value = next((row["total_value_eur"] for row in rows if row["scenario"] == "fcr_only"), 0.0)
    for row in rows:
        row["delta_vs_fcr_only_eur"] = row["total_value_eur"] - fcr_total_value

    return pl.DataFrame(rows)


def build_constraint_audit(dispatch_df: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for scenario in dispatch_df["scenario"].unique(maintain_order=True).to_list():
        scenario_df = dispatch_df.filter(pl.col("scenario") == scenario)
        audit_row = {
            "scenario": scenario,
            "row_count": scenario_df.height,
            "feasible_row_count": int((scenario_df["constraint_status"] == "ok").sum()),
            "violation_row_count": int((scenario_df["constraint_status"] != "ok").sum()),
        }
        for field in CONSTRAINT_FIELDS:
            audit_row[field] = int(scenario_df[field].sum())
        rows.append(audit_row)

    return pl.DataFrame(rows)

