from __future__ import annotations

from pathlib import Path

import polars as pl


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
    candidates = ["Elområde", "bidding_zone", "Bidding zone", "MBA", "Price area"]

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
