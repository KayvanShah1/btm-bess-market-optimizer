from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.io import load_hourly_inputs, output_paths, write_part_a_outputs
from bess_optimizer.model.scenarios import run_part_a_scenarios


@dataclass(frozen=True)
class PartAResult:
    config: PartAModelConfig
    dispatch: pl.DataFrame
    summary: pl.DataFrame
    audit: pl.DataFrame
    output_paths: dict[str, Path]


def run_part_a(config: PartAModelConfig | None = None, *, write_outputs: bool = True) -> PartAResult:
    config = config or PartAModelConfig()
    hourly_inputs = load_hourly_inputs(config)
    dispatch, summary, audit = run_part_a_scenarios(hourly_inputs, config)

    if write_outputs:
        write_part_a_outputs(dispatch, summary, audit, config)

    return PartAResult(
        config=config,
        dispatch=dispatch,
        summary=summary,
        audit=audit,
        output_paths=output_paths(config),
    )
