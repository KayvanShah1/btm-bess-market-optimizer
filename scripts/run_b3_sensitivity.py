from __future__ import annotations

import argparse
from pathlib import Path

from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.io import load_hourly_inputs
from bess_optimizer.sensitivity.b3_break_even import (
    DEFAULT_ACTIVATION_PROBABILITIES,
    DEFAULT_BATTERY_COUNTS,
    DEFAULT_MFRR_CAPACITY_PRICE_MULTIPLIERS,
    run_b3_break_even_grid,
    summarize_break_even_result,
)


def default_output_path(config: PartAModelConfig) -> Path:
    date_slug = config.run_date.isoformat().replace("-", "")
    zone_slug = config.bidding_zone.lower()
    return config.output_dir / f"b3_mfrr_break_even_sensitivity_{zone_slug}_{date_slug}.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run B3 operational mFRR break-even sensitivity."
    )
    parser.add_argument("--input-file", type=Path, default=None)
    parser.add_argument("--output-file", type=Path, default=None)
    parser.add_argument(
        "--battery-counts",
        default=",".join(str(count) for count in DEFAULT_BATTERY_COUNTS),
        help="Comma-separated identical battery counts to test; each unit is the Part A 1 MW / 2 MWh battery.",
    )
    return parser


def parse_battery_counts(value: str) -> tuple[int, ...]:
    counts = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not counts:
        raise ValueError("At least one battery count is required")
    if any(count < 1 for count in counts):
        raise ValueError("Battery counts must be at least 1")
    return counts


def main() -> None:
    args = build_parser().parse_args()
    config = PartAModelConfig()
    if args.input_file:
        config = config.model_copy(update={"input_file": args.input_file})

    df = load_hourly_inputs(config)
    battery_counts = parse_battery_counts(args.battery_counts)
    operational_df = run_b3_break_even_grid(
        df,
        config,
        activation_probabilities=DEFAULT_ACTIVATION_PROBABILITIES,
        mfrr_capacity_price_multipliers=DEFAULT_MFRR_CAPACITY_PRICE_MULTIPLIERS,
        battery_counts=battery_counts,
    )
    output_path = args.output_file or default_output_path(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    operational_df.write_csv(output_path)

    summary = summarize_break_even_result(operational_df)
    print(f"Wrote {output_path}")
    print(f"Grid cells: {summary['cell_count']}")
    print(f"Battery counts: {', '.join(str(count) for count in battery_counts)}")
    print(f"mFRR worthwhile cells: {summary['worthwhile_cell_count']}")
    print(f"Best daily delta EUR: {summary['best_case_delta_eur']:.2f}")
    print(f"Worst daily delta EUR: {summary['worst_case_delta_eur']:.2f}")
    print(
        "Max activation probability at 1.0x mFRR capacity price: "
        f"{summary['max_activation_probability_at_1x_capacity']}"
    )


if __name__ == "__main__":
    main()
