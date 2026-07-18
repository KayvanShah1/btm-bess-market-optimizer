from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.io import load_hourly_inputs
from bess_optimizer.sensitivity.b3_break_even import (
    DEFAULT_ACTIVATION_PROBABILITIES,
    DEFAULT_BATTERY_COUNTS,
    DEFAULT_MFRR_CAPACITY_PRICE_MULTIPLIERS,
    run_b3_break_even_grid,
    summarize_break_even_result,
)

BreakEvenSummary = dict[str, float | int | None]


@dataclass(frozen=True)
class B3SensitivityResult:
    config: PartAModelConfig
    sensitivity: pl.DataFrame
    summary: BreakEvenSummary
    battery_counts: tuple[int, ...]
    output_path: Path


def default_b3_output_path(config: PartAModelConfig) -> Path:
    date_slug = config.run_date.isoformat().replace("-", "")
    zone_slug = config.bidding_zone.lower()
    return config.output_dir / f"b3_mfrr_break_even_sensitivity_{zone_slug}_{date_slug}.csv"


def validate_battery_counts(battery_counts: tuple[int, ...]) -> tuple[int, ...]:
    if not battery_counts:
        raise ValueError("At least one battery count is required")
    if any(count < 1 for count in battery_counts):
        raise ValueError("Battery counts must be at least 1")
    return battery_counts


def run_b3_sensitivity(
    config: PartAModelConfig | None = None,
    *,
    output_path: Path | None = None,
    battery_counts: tuple[int, ...] = DEFAULT_BATTERY_COUNTS,
    write_output: bool = True,
) -> B3SensitivityResult:
    config = config or PartAModelConfig()
    battery_counts = validate_battery_counts(battery_counts)
    hourly_inputs = load_hourly_inputs(config)

    sensitivity = run_b3_break_even_grid(
        hourly_inputs,
        config,
        activation_probabilities=DEFAULT_ACTIVATION_PROBABILITIES,
        mfrr_capacity_price_multipliers=DEFAULT_MFRR_CAPACITY_PRICE_MULTIPLIERS,
        battery_counts=battery_counts,
    )
    resolved_output_path = output_path or default_b3_output_path(config)

    if write_output:
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        sensitivity.write_csv(resolved_output_path)

    return B3SensitivityResult(
        config=config,
        sensitivity=sensitivity,
        summary=summarize_break_even_result(sensitivity),
        battery_counts=battery_counts,
        output_path=resolved_output_path,
    )
