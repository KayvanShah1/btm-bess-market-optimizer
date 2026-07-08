from __future__ import annotations

import argparse
from pathlib import Path

from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.io import load_hourly_inputs
from bess_optimizer.sensitivity.b3_break_even import (
    DEFAULT_ACTIVATION_PROBABILITIES,
    DEFAULT_MFRR_CAPACITY_PRICE_MULTIPLIERS,
    run_b3_break_even_grid,
    summarize_break_even_result,
)
from bess_optimizer.sensitivity.finance import FinancialOverlayAssumptions, build_financial_overlay


def default_output_path(config: PartAModelConfig) -> Path:
    date_slug = config.run_date.isoformat().replace("-", "")
    zone_slug = config.bidding_zone.lower()
    return config.output_dir / f"b3_mfrr_break_even_sensitivity_{zone_slug}_{date_slug}.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run B3 operational mFRR break-even sensitivity and optional payback overlay."
    )
    parser.add_argument("--input-file", type=Path, default=None)
    parser.add_argument("--output-file", type=Path, default=None)
    parser.add_argument("--upfront-enable-cost-eur", type=float, default=25_000.0)
    parser.add_argument("--annual-operating-cost-eur", type=float, default=5_000.0)
    parser.add_argument("--risk-buffer-eur", type=float, default=2_000.0)
    parser.add_argument("--operating-days", type=int, default=300)
    parser.add_argument("--confidence-factor", type=float, default=0.80)
    parser.add_argument("--target-payback-years", type=float, default=5.0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = PartAModelConfig()
    if args.input_file:
        config = config.model_copy(update={"input_file": args.input_file})

    df = load_hourly_inputs(config)
    operational_df = run_b3_break_even_grid(
        df,
        config,
        activation_probabilities=DEFAULT_ACTIVATION_PROBABILITIES,
        mfrr_capacity_price_multipliers=DEFAULT_MFRR_CAPACITY_PRICE_MULTIPLIERS,
    )
    output_df = build_financial_overlay(
        operational_df,
        FinancialOverlayAssumptions(
            upfront_enablement_cost_eur=args.upfront_enable_cost_eur,
            annual_operating_cost_eur=args.annual_operating_cost_eur,
            risk_buffer_eur=args.risk_buffer_eur,
            operating_days=args.operating_days,
            confidence_factor=args.confidence_factor,
            target_payback_years=args.target_payback_years,
        ),
    )

    output_path = args.output_file or default_output_path(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.write_csv(output_path)

    summary = summarize_break_even_result(output_df)
    print(f"Wrote {output_path}")
    print(f"Grid cells: {summary['cell_count']}")
    print(f"mFRR worthwhile cells: {summary['worthwhile_cell_count']}")
    print(f"Best daily delta EUR: {summary['best_case_delta_eur']:.2f}")
    print(f"Worst daily delta EUR: {summary['worst_case_delta_eur']:.2f}")
    print(
        "Max activation probability at 1.0x mFRR capacity price: "
        f"{summary['max_activation_probability_at_1x_capacity']}"
    )
    required_daily_delta = float(output_df["required_daily_delta_for_target_payback_eur"].first())
    fixed_cost_burden = float(output_df["fixed_cost_burden_eur_per_day"].first())
    print(f"Fixed operating/risk burden EUR/day: {fixed_cost_burden:.2f}")
    print(f"Required daily delta for {args.target_payback_years:.1f} year payback EUR: {required_daily_delta:.2f}")


if __name__ == "__main__":
    main()
