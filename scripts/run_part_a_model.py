from __future__ import annotations

from rich.console import Console
from rich.table import Table

from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.io import load_hourly_inputs, write_part_a_outputs
from bess_optimizer.model.scenarios import run_part_a_scenarios

console = Console()


def main() -> None:
    config = PartAModelConfig()
    df = load_hourly_inputs(config)

    dispatch_df, summary_df, audit_df = run_part_a_scenarios(df, config)
    write_part_a_outputs(dispatch_df, summary_df, audit_df, config)

    table = Table(title="Part A scenario summary")
    table.add_column("Scenario")
    table.add_column("Total value EUR", justify="right")
    table.add_column("Savings %", justify="right")
    table.add_column("Delta vs FCR-only", justify="right")
    table.add_column("Violations", justify="right")

    for row in summary_df.to_dicts():
        table.add_row(
            str(row["scenario"]),
            f"{float(row['total_value_eur']):,.2f}",
            f"{float(row['local_savings_pct']):.1%}",
            f"{float(row.get('delta_vs_fcr_only_eur', 0.0)):,.2f}",
            f"{int(row['constraint_violation_count'])}",
        )

    console.print(table)


if __name__ == "__main__":
    main()
