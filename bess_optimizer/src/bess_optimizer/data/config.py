from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from bess_optimizer.settings import settings


class ProcessedDatasetConfig(BaseModel):
    """Configuration for the representative-day processed dataset build."""

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
