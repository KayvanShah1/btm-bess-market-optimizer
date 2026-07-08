from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
import polars as pl


class FinancialOverlayAssumptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    upfront_enablement_cost_eur: float = Field(default=25_000.0, ge=0.0)
    annual_operating_cost_eur: float = Field(default=5_000.0, ge=0.0)
    risk_buffer_eur: float = Field(default=2_000.0, ge=0.0)
    operating_days: int = Field(default=300, ge=1)
    confidence_factor: float = Field(default=0.80, gt=0.0, le=1.0)
    target_payback_years: float = Field(default=5.0, gt=0.0)


def calculate_effective_operating_days(operating_days: int, confidence_factor: float) -> float:
    return operating_days * confidence_factor


def annualize_daily_delta(
    daily_delta_eur: float,
    *,
    operating_days: int,
    confidence_factor: float,
) -> float:
    return daily_delta_eur * operating_days * confidence_factor


def calculate_annual_net_incremental_value(
    annual_incremental_value_eur: float,
    *,
    annual_operating_cost_eur: float,
    risk_buffer_eur: float,
) -> float:
    return annual_incremental_value_eur - annual_operating_cost_eur - risk_buffer_eur


def calculate_fixed_cost_burden_per_day(
    *,
    annual_operating_cost_eur: float,
    risk_buffer_eur: float,
    effective_operating_days: float,
) -> float:
    return (annual_operating_cost_eur + risk_buffer_eur) / effective_operating_days


def calculate_required_daily_delta_for_payback(
    *,
    upfront_enablement_cost_eur: float,
    annual_operating_cost_eur: float,
    risk_buffer_eur: float,
    effective_operating_days: float,
    target_payback_years: float,
) -> float:
    annual_recovery_required = upfront_enablement_cost_eur / target_payback_years
    annual_fixed_cost = annual_operating_cost_eur + risk_buffer_eur
    return (annual_recovery_required + annual_fixed_cost) / effective_operating_days


def calculate_payback_years(
    upfront_enablement_cost_eur: float,
    annual_net_incremental_value_eur: float,
) -> float | None:
    if annual_net_incremental_value_eur <= 0:
        return None
    if upfront_enablement_cost_eur <= 0:
        return 0.0
    return upfront_enablement_cost_eur / annual_net_incremental_value_eur


def build_financial_overlay(
    break_even_df: pl.DataFrame,
    assumptions: FinancialOverlayAssumptions | None = None,
) -> pl.DataFrame:
    assumptions = assumptions or FinancialOverlayAssumptions()

    effective_operating_days = calculate_effective_operating_days(
        assumptions.operating_days,
        assumptions.confidence_factor,
    )
    fixed_cost_burden_per_day = calculate_fixed_cost_burden_per_day(
        annual_operating_cost_eur=assumptions.annual_operating_cost_eur,
        risk_buffer_eur=assumptions.risk_buffer_eur,
        effective_operating_days=effective_operating_days,
    )
    required_daily_delta = calculate_required_daily_delta_for_payback(
        upfront_enablement_cost_eur=assumptions.upfront_enablement_cost_eur,
        annual_operating_cost_eur=assumptions.annual_operating_cost_eur,
        risk_buffer_eur=assumptions.risk_buffer_eur,
        effective_operating_days=effective_operating_days,
        target_payback_years=assumptions.target_payback_years,
    )

    annualized_delta = pl.col("delta_vs_fcr_only_eur") * effective_operating_days
    with_annual_value = break_even_df.with_columns(
        annualized_delta.alias("annualized_delta_eur"),
        pl.lit(assumptions.upfront_enablement_cost_eur).alias("upfront_enablement_cost_eur"),
        pl.lit(assumptions.annual_operating_cost_eur).alias("annual_operating_cost_eur"),
        pl.lit(assumptions.risk_buffer_eur).alias("risk_buffer_eur"),
        pl.lit(assumptions.operating_days).alias("operating_days"),
        pl.lit(assumptions.confidence_factor).alias("confidence_factor"),
        pl.lit(effective_operating_days).alias("effective_operating_days"),
        pl.lit(fixed_cost_burden_per_day).alias("fixed_cost_burden_eur_per_day"),
        pl.lit(assumptions.target_payback_years).alias("target_payback_years"),
        pl.lit(required_daily_delta).alias("required_daily_delta_for_target_payback_eur"),
    )

    with_net_value = with_annual_value.with_columns(
        (
            pl.col("annualized_delta_eur")
            - pl.col("annual_operating_cost_eur")
            - pl.col("risk_buffer_eur")
        ).alias("annual_net_incremental_value_eur")
    )

    return with_net_value.with_columns(
        pl.when(pl.col("annual_net_incremental_value_eur") > 0)
        .then(pl.col("upfront_enablement_cost_eur") / pl.col("annual_net_incremental_value_eur"))
        .otherwise(None)
        .alias("payback_years")
    ).with_columns(
        (
            pl.col("delta_vs_fcr_only_eur")
            - pl.col("required_daily_delta_for_target_payback_eur")
        ).alias("payback_gap_to_target_eur_per_day")
    )
