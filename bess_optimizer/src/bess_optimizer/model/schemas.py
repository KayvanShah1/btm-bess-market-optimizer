from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ActivationScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    activation_probability: float


class CandidateAllocation(BaseModel):
    model_config = ConfigDict(frozen=True)

    local_reserve_mw: float
    fcr_commit_mw: float
    mfrr_commit_mw: float


class ConstraintStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    soc_min_violation: bool = False
    soc_max_violation: bool = False
    power_limit_violation: bool = False
    shared_capacity_violation: bool = False
    peak_import_violation: bool = False
    fcr_headroom_violation: bool = False
    mfrr_readiness_violation: bool = False
    savings_floor_violation: bool = False

    @property
    def feasible(self) -> bool:
        return not any(self.model_dump().values())


CONSTRAINT_FIELDS = tuple(ConstraintStatus().model_dump().keys())


def status_label(status: ConstraintStatus) -> str:
    failures = [name for name, failed in status.model_dump().items() if failed]
    return "ok" if not failures else "|".join(failures)

