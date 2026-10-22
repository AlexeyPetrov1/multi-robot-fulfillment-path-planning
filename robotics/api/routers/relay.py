"""Energy-aware relay missions; no database mutation is needed for a simulation."""

from fastapi import APIRouter, Depends, HTTPException

from robotics.api.dependencies import require_role
from robotics.api.schemas.relay import RelayContinueRequest, RelayPlanRequest, RelayReplayRequest
from robotics.api.security import Role
from robotics.relay.examples import example_scenarios
from robotics.services.relay_service import continue_mission, plan_mission, replay_mission


router = APIRouter(prefix="/relay", tags=["relay"])


@router.get("/scenarios", dependencies=[Depends(require_role(Role.viewer))])
def scenarios():
    return example_scenarios()


@router.post("/plan", dependencies=[Depends(require_role(Role.operator))])
def plan(body: RelayPlanRequest):
    try:
        return plan_mission(body.scenario, max_timesteps=body.max_timesteps,
                            max_states=body.max_states, time_limit=body.time_limit,
                            strategy=body.strategy)
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/continue", dependencies=[Depends(require_role(Role.operator))])
def continue_run(body: RelayContinueRequest):
    try:
        return continue_mission(body.report, max_timesteps=body.max_timesteps,
                                max_states=body.max_states, time_limit=body.time_limit,
                                strategy=body.strategy)
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/replay", dependencies=[Depends(require_role(Role.operator))])
def replay(body: RelayReplayRequest):
    try:
        return replay_mission(body.scenario, body.actions)
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
