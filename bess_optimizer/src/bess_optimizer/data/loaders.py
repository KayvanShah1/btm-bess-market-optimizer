from __future__ import annotations

import polars as pl

from bess_optimizer.data.config import ProcessedDatasetConfig
from bess_optimizer.data.parsing import (
    find_col,
    find_time_col,
    find_zone_col,
    parse_esett_time,
    parse_flexible_time,
    parse_iso_time,
    read_csv_auto,
)


def load_site_load_15min(config: ProcessedDatasetConfig, index: pl.DataFrame) -> pl.DataFrame:
    path = config.raw_dir / config.load_file
    df = parse_iso_time(read_csv_auto(path), "time")

    if config.load_scenario_col not in df.columns:
        raise ValueError(f"Missing load scenario column: {config.load_scenario_col}")

    next_midnight = df.head(1).with_columns(pl.lit(config.next_day_start).alias("timestamp"))

    hourly = (
        pl.concat([df, next_midnight], how="diagonal").select(["timestamp", config.load_scenario_col]).sort("timestamp")
    )

    combined = pl.concat([hourly, index.select("timestamp")], how="diagonal").sort("timestamp")

    return (
        combined.unique(subset=["timestamp"], keep="first")
        .with_columns(pl.col(config.load_scenario_col).interpolate())
        .filter(pl.col("timestamp") < config.next_day_start)
        .rename({config.load_scenario_col: "site_load_kw"})
        .select(["timestamp", "site_load_kw"])
    )


def load_site_pv_15min(config: ProcessedDatasetConfig) -> pl.DataFrame:
    path = config.raw_dir / config.pv_file
    df = parse_esett_time(read_csv_auto(path))

    solar_candidates = [col for col in df.columns if "Solar" in col and "MWh" in col]
    if not solar_candidates:
        raise ValueError("Could not find solar production column in eSett production file.")

    solar_col = solar_candidates[0]
    pv = (
        df.select(["timestamp", solar_col])
        .rename({solar_col: "solar_mwh"})
        .with_columns(pl.col("solar_mwh").fill_null(0.0))
    )

    max_solar = pv["solar_mwh"].max()
    if max_solar is None or max_solar <= 0:
        return pv.with_columns(pl.lit(0.0).alias("site_pv_kw")).select(["timestamp", "site_pv_kw"])

    return pv.with_columns((pl.col("solar_mwh") / max_solar * config.site_pv_capacity_kw).alias("site_pv_kw")).select(
        ["timestamp", "site_pv_kw"]
    )


def load_spot_15min(config: ProcessedDatasetConfig) -> pl.DataFrame:
    nordpool_path = config.raw_dir / config.spot_nordpool_file
    svk_path = config.raw_dir / config.spot_svk_file

    if nordpool_path.exists():
        df = parse_iso_time(read_csv_auto(nordpool_path), "time_sweden")

        if config.bidding_zone not in df.columns:
            raise ValueError(f"Nord Pool file missing {config.bidding_zone} column.")

        return (
            df.select(["timestamp", config.bidding_zone])
            .rename({config.bidding_zone: "spot_price_eur_mwh"})
            .sort("timestamp")
        )

    df = parse_iso_time(read_csv_auto(svk_path), "start_time_sweden")

    return (
        df.filter(pl.col("bidding_zone") == config.bidding_zone)
        .select(["timestamp", "price"])
        .rename({"price": "spot_price_eur_mwh"})
        .sort("timestamp")
    )


def load_fcr_15min(config: ProcessedDatasetConfig, index: pl.DataFrame) -> pl.DataFrame:
    df = load_mimer_source(config, config.fcr_file, filter_zone=False)
    price_col = find_col(df, contains_all=["FCR-N", "Pris"])

    hourly = df.select(["timestamp", price_col]).rename({price_col: "fcrn_price_eur_mw_h"}).sort("timestamp")

    return repeat_hourly_to_15min(hourly, ["fcrn_price_eur_mw_h"], index)


def load_mfrr_cm_15min(config: ProcessedDatasetConfig, index: pl.DataFrame) -> pl.DataFrame:
    df = load_mimer_source(config, config.mfrr_capacity_file, filter_zone=True)
    price_col = find_col(df, contains_all=["mFRR", "Upp", "Pris"])
    volume_col = find_col(df, contains_all=["mFRR", "Upp", "Volym"], required=False)

    cols = ["timestamp", price_col]
    rename_map = {price_col: "mfrr_capacity_price_eur_mw_h"}

    if volume_col:
        cols.append(volume_col)
        rename_map[volume_col] = "mfrr_capacity_volume_mw"

    hourly = df.select(cols).rename(rename_map).sort("timestamp")

    if "mfrr_capacity_volume_mw" not in hourly.columns:
        hourly = hourly.with_columns(pl.lit(None).cast(pl.Float64).alias("mfrr_capacity_volume_mw"))

    return repeat_hourly_to_15min(
        hourly,
        ["mfrr_capacity_price_eur_mw_h", "mfrr_capacity_volume_mw"],
        index,
    )


def load_mfrr_eam_15min(config: ProcessedDatasetConfig, index: pl.DataFrame) -> pl.DataFrame:
    df = load_mimer_source(config, config.mfrr_activation_file, filter_zone=True)
    price_col = find_col(df, contains_all=["mFRR", "Upp", "Pris"])
    volume_cols = [col for col in df.columns if "mFRR" in col and "Upp" in col and "Volym" in col]

    if volume_cols:
        df = df.with_columns(
            pl.sum_horizontal([pl.col(col).fill_null(0.0) for col in volume_cols]).alias("mfrr_activation_volume_mw")
        )
    else:
        df = df.with_columns(pl.lit(0.0).alias("mfrr_activation_volume_mw"))

    hourly = df.select(["timestamp", price_col, "mfrr_activation_volume_mw"]).rename(
        {price_col: "mfrr_activation_energy_price_eur_mwh"}
    )

    hourly = hourly.with_columns(
        (pl.col("mfrr_activation_volume_mw") > 0).cast(pl.Int8).alias("mfrr_activation_flag")
    ).sort("timestamp")

    return repeat_hourly_to_15min(
        hourly,
        [
            "mfrr_activation_energy_price_eur_mwh",
            "mfrr_activation_volume_mw",
            "mfrr_activation_flag",
        ],
        index,
    )


def load_mimer_source(
    config: ProcessedDatasetConfig,
    filename: str,
    *,
    filter_zone: bool,
) -> pl.DataFrame:
    df = read_csv_auto(config.raw_dir / filename)
    df = parse_flexible_time(df, find_time_col(df))

    if filter_zone:
        zone_col = find_zone_col(df)
        if zone_col:
            df = df.filter(pl.col(zone_col).cast(pl.String) == config.mimer_zone)

    return df


def repeat_hourly_to_15min(
    hourly: pl.DataFrame,
    value_cols: list[str],
    index: pl.DataFrame,
) -> pl.DataFrame:
    return (
        index.select("timestamp")
        .join_asof(hourly.sort("timestamp"), on="timestamp", strategy="backward")
        .select(["timestamp", *value_cols])
    )
