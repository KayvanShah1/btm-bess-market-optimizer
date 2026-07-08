from __future__ import annotations

from bess_optimizer.model.config import PartAModelConfig
from bess_optimizer.model.schemas import ConstraintStatus


def build_constraint_status(
    *,
    soc_mwh: float,
    battery_charge_mw: float,
    battery_discharge_mw: float,
    local_reserve_mw: float,
    fcr_commit_mw: float,
    mfrr_commit_mw: float,
    grid_to_battery_kw: float,
    grid_import_kw: float,
    peak_threshold_kw: float,
    config: PartAModelConfig,
    battery_available_discharge_mw: float = 0.0,
    fcr_headroom_violation: bool = False,
    mfrr_readiness_violation: bool = False,
    savings_floor_violation: bool = False,
) -> ConstraintStatus:
    epsilon = 1e-9
    local_physical_power_mw = max(battery_charge_mw, battery_discharge_mw)
    total_reserved_or_used_mw = local_physical_power_mw + local_reserve_mw + fcr_commit_mw + mfrr_commit_mw
    return ConstraintStatus(
        soc_min_violation=soc_mwh < config.battery.min_soc_mwh - epsilon,
        soc_max_violation=soc_mwh > config.battery.max_soc_mwh + epsilon,
        power_limit_violation=local_physical_power_mw > config.battery.power_mw + epsilon,
        shared_capacity_violation=total_reserved_or_used_mw > config.battery.power_mw + epsilon,
        peak_import_violation=grid_import_kw > peak_threshold_kw + epsilon and battery_available_discharge_mw > epsilon,
        fcr_headroom_violation=fcr_headroom_violation,
        mfrr_readiness_violation=mfrr_readiness_violation,
        savings_floor_violation=savings_floor_violation,
    )


def fcr_headroom_violation(soc_mwh: float, fcr_commit_mw: float, config: PartAModelConfig) -> bool:
    if fcr_commit_mw <= 1e-9:
        return False

    buffer_mwh = fcr_commit_mw * config.reserve.fcr_response_buffer_hours
    return not (
        config.battery.min_soc_mwh + buffer_mwh <= soc_mwh + 1e-9
        and soc_mwh <= config.battery.max_soc_mwh - buffer_mwh + 1e-9
    )
