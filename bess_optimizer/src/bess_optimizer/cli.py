from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from bess_optimizer.data.pipeline import (
    ProcessedDatasetResult,
    build_processed_datasets,
    write_processed_datasets,
)
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.settings import settings
from bess_optimizer.sensitivity.b3_break_even import DEFAULT_BATTERY_COUNTS
from bess_optimizer.workflows.b3 import B3SensitivityResult, run_b3_sensitivity
from bess_optimizer.workflows.part_a import PartAResult, run_part_a
from bess_optimizer.workflows.pipeline import PipelineResult, run_pipeline

console = Console()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(settings.project_root))
    except ValueError:
        return str(resolved)


def render_processed_data(result: ProcessedDatasetResult) -> None:
    table = Table(title="Processed dataset outputs")
    table.add_column("File")
    table.add_column("Rows", justify="right")
    table.add_row(display_path(result.output_15min_path), f"{result.data_15min.height:,}")
    table.add_row(display_path(result.output_hourly_path), f"{result.data_hourly.height:,}")
    console.print(table)


def render_part_a(result: PartAResult) -> None:
    table = Table(title="Part A scenario summary")
    table.add_column("Scenario")
    table.add_column("Total value EUR", justify="right")
    table.add_column("Savings %", justify="right")
    table.add_column("Delta vs FCR-only", justify="right")
    table.add_column("Violations", justify="right")

    for row in result.summary.to_dicts():
        table.add_row(
            str(row["scenario"]),
            f"{float(row['total_value_eur']):,.2f}",
            f"{float(row['local_savings_pct']):.1%}",
            f"{float(row.get('delta_vs_fcr_only_eur', 0.0)):,.2f}",
            f"{int(row['constraint_violation_count'])}",
        )

    console.print(table)


def render_b3(result: B3SensitivityResult) -> None:
    summary = result.summary
    console.print(f"[green]Wrote[/green] {display_path(result.output_path)}")

    table = Table(title="B3 mFRR break-even sensitivity")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Grid cells", f"{int(summary['cell_count']):,}")
    table.add_row("Battery counts", ", ".join(str(count) for count in result.battery_counts))
    table.add_row("mFRR worthwhile cells", f"{int(summary['worthwhile_cell_count']):,}")
    table.add_row("Best daily delta EUR", f"{float(summary['best_case_delta_eur']):,.2f}")
    table.add_row("Worst daily delta EUR", f"{float(summary['worst_case_delta_eur']):,.2f}")

    one_x_threshold = summary["max_activation_probability_at_1x_capacity"]
    table.add_row(
        "Max activation at 1.0x mFRR capacity price",
        "n/a" if one_x_threshold is None else f"{float(one_x_threshold):.1%}",
    )
    console.print(table)


def parse_battery_counts(value: str) -> tuple[int, ...]:
    try:
        counts = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError("Battery counts must be comma-separated integers") from error

    if not counts:
        raise argparse.ArgumentTypeError("At least one battery count is required")
    if any(count < 1 for count in counts):
        raise argparse.ArgumentTypeError("Battery counts must be at least 1")
    return counts


def build_data() -> None:
    with console.status("Building processed BESS datasets...", spinner="dots"):
        result = build_processed_datasets()
        write_processed_datasets(result)
    render_processed_data(result)
    console.print("[green]Done.[/green]")


def run_model() -> None:
    result = run_part_a()
    render_part_a(result)


def sensitivity_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run B3 operational mFRR break-even sensitivity.")
    parser.add_argument("--input-file", type=Path, default=None)
    parser.add_argument("--output-file", type=Path, default=None)
    parser.add_argument(
        "--battery-counts",
        type=parse_battery_counts,
        default=DEFAULT_BATTERY_COUNTS,
        help="Comma-separated identical battery counts to test; each unit is the Part A 1 MW / 2 MWh battery.",
    )
    return parser


def run_sensitivity() -> None:
    args = sensitivity_parser().parse_args()
    config = PartAModelConfig()
    if args.input_file:
        config = config.model_copy(update={"input_file": args.input_file})

    result = run_b3_sensitivity(
        config,
        output_path=args.output_file,
        battery_counts=args.battery_counts,
    )
    render_b3(result)


def render_pipeline(result: PipelineResult) -> None:
    render_processed_data(result.processed_data)
    render_part_a(result.part_a)
    render_b3(result.b3)
    console.rule("[bold green]Pipeline complete")
    console.print("All processed datasets, Part A model outputs, and B3 sensitivity outputs were rebuilt successfully.")


def run_full_pipeline() -> None:
    console.print("[bold]Running the complete BESS data and modelling pipeline...[/bold]")
    with console.status("Executing pipeline stages...", spinner="dots"):
        result = run_pipeline()
    render_pipeline(result)
