from datetime import date, datetime, time, timedelta
from pathlib import Path

import polars as pl
from bess_optimizer.settings import settings
from pydantic import BaseModel, ConfigDict
from rich.console import Console
from rich.table import Table

##################################################
# Settings and run constants
##################################################


class ProcessedDatasetConfig(BaseModel):
    """Constants for this one representative-day processed data build."""

    model_config = ConfigDict(frozen=True)

    project_root: Path = settings.project_root
    raw_dir: Path = settings.raw_data_dir
    processed_dir: Path = settings.processed_data_dir

    run_date: date = date(2026, 6, 24)
    bidding_zone: str = "SE3"
    mimer_zone: str = "SN3"

    site_pv_capacity_kw: float = 800.0
    load_scenario_col: str = "light_factory_one_shift_kw"

    load_file: str = "synthetic_representative_swedish_ci_load_profiles_hourly.csv"
    pv_file: str = "esett_production_profile_20260624.csv"
    spot_nordpool_file: str = "nordpool_day_ahead_prices_pasted_20260624.csv"
    spot_svk_file: str = "svk_day_ahead_area_prices_20260624.csv"
    fcr_file: str = "mimer_fcr_capacity_market_20260624.csv"
    mfrr_capacity_file: str = "mimer_mfrr_capacity_market_d1_20260624.csv"
    mfrr_activation_file: str = "mimer_mfrr_energy_activation_market_20260624.csv"

    @property
    def date_label(self) -> str:
        return self.run_date.isoformat()

    @property
    def date_slug(self) -> str:
        return self.run_date.strftime("%Y%m%d")

    @property
    def day_start(self) -> datetime:
        return datetime.combine(self.run_date, time.min)

    @property
    def next_day_start(self) -> datetime:
        return self.day_start + timedelta(days=1)

    @property
    def day_end_15min(self) -> datetime:
        return self.next_day_start - timedelta(minutes=15)

    @property
    def output_15min_file(self) -> str:
        zone = self.bidding_zone.lower()
        return f"representative_day_15min_{zone}_{self.date_slug}.csv"

    @property
    def output_hourly_file(self) -> str:
        zone = self.bidding_zone.lower()
        return f"representative_day_hourly_{zone}_{self.date_slug}.csv"

    @property
    def source_files(self) -> dict[str, str]:
        return {
            "source_load": self.load_file,
            "source_pv": self.pv_file,
            "source_spot": self.spot_nordpool_file,
            "source_fcr": self.fcr_file,
            "source_mfrr_cm": self.mfrr_capacity_file,
            "source_mfrr_eam": self.mfrr_activation_file,
        }


CONFIG = ProcessedDatasetConfig()
console = Console()


##################################################
# CSV and timestamp processes
##################################################


def read_csv_auto(path: Path) -> pl.DataFrame:
    """Read comma or semicolon CSV with basic decimal-comma support."""
    sample = path.read_text(encoding="utf-8-sig", errors="ignore")[:1000]
    header = sample.splitlines()[0] if sample else ""
    separator = ";" if header.count(";") > header.count(",") else ","

    df = pl.read_csv(
        path,
        separator=separator,
        encoding="utf8-lossy",
        infer_schema_length=5000,
        ignore_errors=True,
    )

    empty_columns = [col for col in df.columns if not col]
    if empty_columns:
        df = df.drop(empty_columns)

    for col, dtype in df.schema.items():
        if dtype != pl.String:
            continue

        converted = df[col].str.replace_all(",", ".").cast(pl.Float64, strict=False)
        non_null_ratio = (df.height - converted.null_count()) / max(df.height, 1)

        if non_null_ratio > 0.5:
            df = df.with_columns(converted.alias(col))

    return df


def parse_esett_time(df: pl.DataFrame) -> pl.DataFrame:
    time_col = "Date/Time CET/CEST"
    if time_col not in df.columns:
        raise ValueError(f"Missing expected eSett time column: {time_col}")

    return df.with_columns(
        pl.col(time_col).str.strptime(pl.Datetime, "%d.%m.%Y/%H:%M", strict=False).alias("timestamp")
    )


def parse_iso_time(df: pl.DataFrame, col: str, alias: str = "timestamp") -> pl.DataFrame:
    if col not in df.columns:
        raise ValueError(f"Missing expected time column: {col}")

    return df.with_columns(pl.col(col).str.strptime(pl.Datetime, strict=False).alias(alias))


def parse_flexible_time(df: pl.DataFrame, time_col: str) -> pl.DataFrame:
    if df.schema[time_col] != pl.String:
        return df.with_columns(pl.col(time_col).cast(pl.Datetime).alias("timestamp"))

    parsed = pl.coalesce(
        pl.col(time_col).str.strptime(pl.Datetime, "%d.%m.%Y/%H:%M", strict=False),
        pl.col(time_col).str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S", strict=False),
        pl.col(time_col).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S", strict=False),
        pl.col(time_col).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M", strict=False),
        pl.col(time_col).str.strptime(pl.Datetime, strict=False),
    )

    return df.with_columns(parsed.alias("timestamp"))


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


##################################################
# File family processes
##################################################


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


##################################################
# Column detection processes
##################################################


def find_time_col(df: pl.DataFrame) -> str:
    candidates = [
        "Date/Time CET/CEST",
        "start_time_sweden",
        "Start time Sweden",
        "Period",
        "Datum",
        "Tid",
        "Time",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    for col in df.columns:
        lowered = col.lower()
        if "time" in lowered or "date" in lowered or "datum" in lowered:
            return col

    raise ValueError(f"Could not detect time column from columns: {df.columns}")


def find_zone_col(df: pl.DataFrame) -> str | None:
    candidates = ["Elomr\u00e5de", "bidding_zone", "Bidding zone", "MBA", "Price area"]

    for col in candidates:
        if col in df.columns:
            return col

    for col in df.columns:
        lowered = col.lower()
        if "zone" in lowered or "area" in lowered or lowered.startswith("elomr"):
            return col

    return None


def find_col(
    df: pl.DataFrame,
    contains_all: list[str],
    required: bool = True,
) -> str | None:
    for col in df.columns:
        if all(token.lower() in col.lower() for token in contains_all):
            return col

    if required:
        raise ValueError(f"Could not find column containing {contains_all}. Columns: {df.columns}")

    return None


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


##################################################
# Processed dataset build
##################################################


def build_source_columns(config: ProcessedDatasetConfig) -> list[pl.Expr]:
    return [pl.lit(filename).alias(column) for column, filename in config.source_files.items()]


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
        df.with_columns(
            [
                (pl.col("site_load_kw") - pl.col("site_pv_kw")).alias("net_load_kw"),
                *build_source_columns(config),
            ]
        )
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
                "source_load",
                "source_pv",
                "source_spot",
                "source_fcr",
                "source_mfrr_cm",
                "source_mfrr_eam",
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


##################################################
# CLI output processes
##################################################


def render_outputs_table(config: ProcessedDatasetConfig, outputs: list[tuple[Path, int]]) -> None:
    table = Table(title="Processed dataset outputs")
    table.add_column("File")
    table.add_column("Rows", justify="right")

    for path, rows in outputs:
        table.add_row(str(path.relative_to(config.project_root)), f"{rows:,}")

    console.print(table)


def main(config: ProcessedDatasetConfig = CONFIG) -> None:
    config.processed_dir.mkdir(parents=True, exist_ok=True)

    with console.status("Building processed BESS datasets...", spinner="dots"):
        index = build_15min_index(config)
        df_15m = build_15min_processed(config, index)
        df_hourly = build_hourly_processed(df_15m)

        out_15m = config.processed_dir / config.output_15min_file
        out_hourly = config.processed_dir / config.output_hourly_file

        df_15m.write_csv(out_15m)
        df_hourly.write_csv(out_hourly)

    render_outputs_table(config, [(out_15m, df_15m.height), (out_hourly, df_hourly.height)])
    console.print("[green]Done.[/green]")


if __name__ == "__main__":
    main()
