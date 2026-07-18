from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bess_optimizer.data.config import ProcessedDatasetConfig
from bess_optimizer.data.pipeline import (
    ProcessedDatasetResult,
    build_processed_datasets,
    write_processed_datasets,
)
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.sensitivity.b3_break_even import DEFAULT_BATTERY_COUNTS
from bess_optimizer.workflows.b3 import B3SensitivityResult, run_b3_sensitivity
from bess_optimizer.workflows.part_a import PartAResult, run_part_a


@dataclass(frozen=True)
class PipelineResult:
    processed_data: ProcessedDatasetResult
    part_a: PartAResult
    b3: B3SensitivityResult


def run_pipeline(
    *,
    data_config: ProcessedDatasetConfig | None = None,
    model_config: PartAModelConfig | None = None,
    b3_output_path: Path | None = None,
    battery_counts: tuple[int, ...] = DEFAULT_BATTERY_COUNTS,
) -> PipelineResult:
    processed_data = build_processed_datasets(data_config)
    write_processed_datasets(processed_data)

    resolved_model_config = (model_config or PartAModelConfig()).model_copy(
        update={"input_file": processed_data.output_hourly_path}
    )
    part_a = run_part_a(resolved_model_config)
    b3 = run_b3_sensitivity(
        resolved_model_config,
        output_path=b3_output_path,
        battery_counts=battery_counts,
    )

    return PipelineResult(
        processed_data=processed_data,
        part_a=part_a,
        b3=b3,
    )
