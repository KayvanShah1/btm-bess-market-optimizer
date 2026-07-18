from __future__ import annotations

from pathlib import Path

import pytest

from bess_optimizer.cli import parse_battery_counts
from bess_optimizer.data.config import ProcessedDatasetConfig
from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.settings import settings
from bess_optimizer.workflows.pipeline import run_pipeline


def assert_matches_committed_output(actual: Path, expected: Path) -> None:
    assert actual.read_bytes() == expected.read_bytes()


def test_packaged_pipeline_matches_committed_outputs(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"
    output_dir = tmp_path / "output"
    data_config = ProcessedDatasetConfig(processed_dir=processed_dir)
    model_config = PartAModelConfig(output_dir=output_dir)

    result = run_pipeline(
        data_config=data_config,
        model_config=model_config,
        b3_output_path=output_dir / "b3_mfrr_break_even_sensitivity_se3_20260624.csv",
    )

    assert result.processed_data.data_15min.height == 96
    assert result.processed_data.data_hourly.height == 24
    assert result.part_a.summary.height == 6
    assert result.b3.sensitivity.height == 336

    expected_pairs = [
        (
            result.processed_data.output_15min_path,
            settings.processed_data_dir / "representative_day_15min_se3_20260624.csv",
        ),
        (
            result.processed_data.output_hourly_path,
            settings.processed_data_dir / "representative_day_hourly_se3_20260624.csv",
        ),
        (
            result.part_a.output_paths["dispatch"],
            settings.output_dir / "part_a_dispatch_hourly_se3_20260624.csv",
        ),
        (
            result.part_a.output_paths["summary"],
            settings.output_dir / "part_a_scenario_summary_se3_20260624.csv",
        ),
        (
            result.part_a.output_paths["audit"],
            settings.output_dir / "part_a_constraint_audit_se3_20260624.csv",
        ),
        (
            result.b3.output_path,
            settings.output_dir / "b3_mfrr_break_even_sensitivity_se3_20260624.csv",
        ),
    ]

    for actual, expected in expected_pairs:
        assert_matches_committed_output(actual, expected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", (1,)),
        ("1,2,3", (1, 2, 3)),
        (" 1, 3 ", (1, 3)),
    ],
)
def test_parse_battery_counts(value: str, expected: tuple[int, ...]) -> None:
    assert parse_battery_counts(value) == expected
