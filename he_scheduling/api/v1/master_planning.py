from fastapi import APIRouter, HTTPException
from he_scheduling.models.master_planning import MPModelRequest, MPModelResponse
from he_scheduling.services.master_planning import MasterPlanningModelBuilder
from ortools.sat.python import cp_model

router = APIRouter(prefix='/api/v1/master-planning')


@router.post("/schedule", response_model=MPModelResponse)
async def schedule_projects(request: MPModelRequest):
    # Instantiate and use the MasterPlanningModelBuilder
    scheduler = MasterPlanningModelBuilder(
        projects=request.projects,
        resources=request.resources,
        period_constraints=request.period_constraints,
        horizon=request.horizon,
        overload_penalty_coefficient=request.overload_penalty_coefficient,
        fixed_violation_penalty_coefficient=request.fixed_violation_penalty_coefficient
    )
    scheduler.build_model()
    status = scheduler.solve(time_limit=request.time_limit)
    solution = scheduler.get_solution()

    return MPModelResponse(
        solver_status=status,
        solution=solution
    )
