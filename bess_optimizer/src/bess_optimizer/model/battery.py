from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from bess_optimizer.model.config import BatteryConfig


class BatteryState(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    soc_mwh: float

    def available_charge_mwh(self, config: BatteryConfig) -> float:
        return max(config.max_soc_mwh - self.soc_mwh, 0.0)

    def available_discharge_mwh(self, config: BatteryConfig) -> float:
        return max(self.soc_mwh - config.min_soc_mwh, 0.0)

    def max_charge_mw(self, config: BatteryConfig, dt_hours: float, power_limit_mw: float | None = None) -> float:
        if dt_hours <= 0:
            return 0.0
        power_cap = config.power_mw if power_limit_mw is None else max(min(power_limit_mw, config.power_mw), 0.0)
        soc_cap_mw = self.available_charge_mwh(config) / (dt_hours * config.charge_efficiency)
        return max(min(power_cap, soc_cap_mw), 0.0)

    def max_discharge_mw(self, config: BatteryConfig, dt_hours: float, power_limit_mw: float | None = None) -> float:
        if dt_hours <= 0:
            return 0.0
        power_cap = config.power_mw if power_limit_mw is None else max(min(power_limit_mw, config.power_mw), 0.0)
        soc_cap_mw = self.available_discharge_mwh(config) * config.discharge_efficiency / dt_hours
        return max(min(power_cap, soc_cap_mw), 0.0)

    def charge(self, charge_mw: float, config: BatteryConfig, dt_hours: float) -> float:
        actual_mw = min(max(charge_mw, 0.0), self.max_charge_mw(config, dt_hours))
        self.soc_mwh += actual_mw * dt_hours * config.charge_efficiency
        return actual_mw

    def discharge(self, discharge_mw: float, config: BatteryConfig, dt_hours: float) -> float:
        actual_mw = min(max(discharge_mw, 0.0), self.max_discharge_mw(config, dt_hours))
        self.soc_mwh -= actual_mw * dt_hours / config.discharge_efficiency
        return actual_mw
