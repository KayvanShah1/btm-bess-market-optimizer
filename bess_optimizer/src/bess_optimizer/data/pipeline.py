from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from bess_optimizer.data.config import ProcessedDatasetConfig
from bess_optimizer.data.loaders import (
    load_fcr_15min,
    load_mfrr_cm_15min,
    load_mfrr_eam_15min,
    load_site_load_15min,
    load_site_pv_15min,
    load_spot_15min,
)


@dataclass(frozen=True)
class ProcessedDatasetResult:
    config: ProcessedDatasetConfig
    data_15min: pl.DataFrame
    data_hourly: pl.DataFrame
    output_15min_path: Path
    output_hourly_path: Path


def build_15min_index(config: ProcessedDatasetConfig) -> pl.DataFrame:
    timestamps = pl.datetime_range(
        start=config.day_start,
        end=config.day_end_15min,
        interval="15m",
        eager=True,
    )

    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "date": [config.date_label] * len(timestamps),
            "hour": [ts.hour for ts in timestamps],
            "interval_index": list(range(len(timestamps))),
            "dt_hours": [0.25] * len(timestamps),
            "bidding_zone": [config.bidding_zone] * len(timestamps),
        }
    )


def build_15min_processed(config: ProcessedDatasetConfig, index: pl.DataFrame) -> pl.DataFrame:
    parts = [
        load_site_load_15min(config, index),
        load_site_pv_15min(config),
        load_spot_15min(config),
        load_fcr_15min(config, index),
        load_mfrr_cm_15min(config, index),
        load_mfrr_eam_15min(config, index),
    ]

    df = index
    for part in parts:
        df = df.join(part, on="timestamp", how="left")

    return (
        df.with_columns((pl.col("site_load_kw") - pl.col("site_pv_kw")).alias("net_load_kw"))
        .select(
            [
                "timestamp",
                "date",
                "hour",
                "interval_index",
                "dt_hours",
                "bidding_zone",
                "site_load_kw",
                "site_pv_kw",
                "net_load_kw",
                "spot_price_eur_mwh",
                "fcrn_price_eur_mw_h",
                "mfrr_capacity_price_eur_mw_h",
                "mfrr_capacity_volume_mw",
                "mfrr_activation_energy_price_eur_mwh",
                "mfrr_activation_volume_mw",
                "mfrr_activation_flag",
            ]
        )
        .sort("timestamp")
    )


def build_hourly_processed(df_15m: pl.DataFrame) -> pl.DataFrame:
    return (
        df_15m.group_by_dynamic(
            index_column="timestamp",
            every="1h",
            period="1h",
            closed="left",
        )
        .agg(
            [
                pl.first("date").alias("date"),
                pl.first("hour").alias("hour"),
                pl.lit(1.0).alias("dt_hours"),
                pl.first("bidding_zone").alias("bidding_zone"),
                pl.mean("site_load_kw").alias("site_load_kw"),
                pl.mean("site_pv_kw").alias("site_pv_kw"),
                pl.mean("net_load_kw").alias("net_load_kw"),
                pl.mean("spot_price_eur_mwh").alias("spot_price_eur_mwh"),
                pl.mean("fcrn_price_eur_mw_h").alias("fcrn_price_eur_mw_h"),
                pl.mean("mfrr_capacity_price_eur_mw_h").alias("mfrr_capacity_price_eur_mw_h"),
                pl.mean("mfrr_capacity_volume_mw").alias("mfrr_capacity_volume_mw"),
                pl.mean("mfrr_activation_energy_price_eur_mwh").alias("mfrr_activation_energy_price_eur_mwh"),
                pl.mean("mfrr_activation_flag").alias("mfrr_activation_probability"),
                pl.max("mfrr_activation_flag").alias("mfrr_activation_flag"),
                pl.mean("mfrr_activation_volume_mw").alias("mfrr_activation_volume_mw"),
            ]
        )
        .sort("timestamp")
    )


def build_processed_datasets(config: ProcessedDatasetConfig | None = None) -> ProcessedDatasetResult:
    config = config or ProcessedDatasetConfig()
    index = build_15min_index(config)
    data_15min = build_15min_processed(config, index)
    data_hourly = build_hourly_processed(data_15min)

    return ProcessedDatasetResult(
        config=config,
        data_15min=data_15min,
        data_hourly=data_hourly,
        output_15min_path=config.processed_dir / config.output_15min_file,
        output_hourly_path=config.processed_dir / config.output_hourly_file,
    )


def write_processed_datasets(result: ProcessedDatasetResult) -> None:
    result.config.processed_dir.mkdir(parents=True, exist_ok=True)
    result.data_15min.write_csv(result.output_15min_path)
    result.data_hourly.write_csv(result.output_hourly_path)
