from __future__ import annotations

from pathlib import Path

import polars as pl

from bess_optimizer.model.config import PartAModelConfig


def load_hourly_inputs(config: PartAModelConfig) -> pl.DataFrame:
    return pl.read_csv(config.input_file, try_parse_dates=True).sort("timestamp")


def output_paths(config: PartAModelConfig) -> dict[str, Path]:
    date_slug = config.run_date.isoformat().replace("-", "")
    zone_slug = config.bidding_zone.lower()
    return {
        "dispatch": config.output_dir / f"part_a_dispatch_hourly_{zone_slug}_{date_slug}.csv",
        "summary": config.output_dir / f"part_a_scenario_summary_{zone_slug}_{date_slug}.csv",
        "audit": config.output_dir / f"part_a_constraint_audit_{zone_slug}_{date_slug}.csv",
    }


def write_part_a_outputs(
    dispatch_df: pl.DataFrame,
    summary_df: pl.DataFrame,
    audit_df: pl.DataFrame,
    config: PartAModelConfig,
) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = output_paths(config)
    dispatch_df.write_csv(paths["dispatch"])
    summary_df.write_csv(paths["summary"])
    audit_df.write_csv(paths["audit"])

