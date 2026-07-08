"""Sensitivity-analysis helpers for the BESS optimizer."""

from bess_optimizer.sensitivity.b3_break_even import (
    apply_mfrr_capacity_price_multiplier,
    run_b3_break_even_grid,
    summarize_break_even_result,
)
from bess_optimizer.sensitivity.finance import (
    FinancialOverlayAssumptions,
    annualize_daily_delta,
    build_financial_overlay,
    calculate_annual_net_incremental_value,
    calculate_effective_operating_days,
    calculate_fixed_cost_burden_per_day,
    calculate_payback_years,
    calculate_required_daily_delta_for_payback,
)

__all__ = [
    "FinancialOverlayAssumptions",
    "annualize_daily_delta",
    "apply_mfrr_capacity_price_multiplier",
    "build_financial_overlay",
    "calculate_annual_net_incremental_value",
    "calculate_effective_operating_days",
    "calculate_fixed_cost_burden_per_day",
    "calculate_payback_years",
    "calculate_required_daily_delta_for_payback",
    "run_b3_break_even_grid",
    "summarize_break_even_result",
]
