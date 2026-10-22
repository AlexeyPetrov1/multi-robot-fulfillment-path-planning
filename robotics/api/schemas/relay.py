"""A complete finite-energy graph scenario and limits for a bounded search."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RelayPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: dict[str, Any]
    max_timesteps: int = Field(default=1000, ge=0, le=1000)
    max_states: int = Field(default=150000, ge=1, le=500000)
    time_limit: float = Field(default=10, gt=0, le=60)
    strategy: Literal["auto", "exact", "dispatch"] = "auto"


class RelayContinueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report: dict[str, Any]
    max_timesteps: int = Field(default=1000, ge=0, le=1000)
    max_states: int = Field(default=150000, ge=1, le=500000)
    time_limit: float = Field(default=10, gt=0, le=60)
    strategy: Literal["auto", "exact", "dispatch"] = "auto"


class RelayReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: dict[str, Any]
    actions: list[dict[str, Any]] = Field(max_length=1000)
