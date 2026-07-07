from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from bess_optimizer.settings import settings


class BatteryConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    power_mw: float = 1.0
    energy_mwh: float = 2.0
    initial_soc_mwh: float = 1.0
    min_soc_mwh: float = 0.2
    max_soc_mwh: float = 1.8
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    degradation_cost_eur_per_mwh: float = 3.0


class SiteConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    peak_threshold_quantile: float = 0.85
    peak_tariff_eur_per_kw_day: float = 0.50
    minimum_savings_pct: float = 0.05
    low_price_quantile: float = 0.30
    high_price_quantile: float = 0.70
    local_peak_lookahead_hours: int = 2


class ReserveConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    fcr_response_buffer_hours: float = 0.25
    mfrr_activation_duration_hours: float = 1.0
    mfrr_readiness_lookback_hours: int = 1
    market_capacity_step_mw: float = 0.25


class PartAModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_date: date = date(2026, 6, 24)
    bidding_zone: str = "SE3"

    input_file: Path = settings.processed_data_dir / "representative_day_hourly_se3_20260624.csv"
    output_dir: Path = settings.output_dir

    battery: BatteryConfig = Field(default_factory=BatteryConfig)
    site: SiteConfig = Field(default_factory=SiteConfig)
    reserve: ReserveConfig = Field(default_factory=ReserveConfig)

