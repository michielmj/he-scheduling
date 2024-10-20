from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class MPResource(BaseModel):
    id: int = Field(
        ...,
        description="Unique identifier for the resource."
    )
    name: str = Field(
        ...,
        description="Name of the resource."
    )
    capacity_per_day: int = Field(
        ...,
        description="Daily capacity of the resource in terms of the maximum load it can handle."
    )


class MPPredecessor(BaseModel):
    task_id: str = Field(
        ...,
        description="Identifier of the predecessor task."
    )
    min_gap: int = Field(
        default=0,
        ge=0,
        description="Minimum time gap (in days) required after the predecessor task ends before this task can start."
    )
    max_gap: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum time gap (in days) allowed after the predecessor task ends before this task must start."
    )


class MPTask(BaseModel):
    id: str = Field(
        ...,
        description="Unique identifier for the task."
    )
    duration: int = Field(
        ge=1,
        description="Duration of the task in days."
    )
    load: int = Field(
        ge=0,
        description="Resource load required for the task. Represents the amount of resource capacity consumed per day."
    )
    predecessors: List['MPPredecessor'] = Field(
        default_factory=list,
        description="List of predecessor tasks with specified time gaps."
    )
    alternative_resources: List[int] = Field(
        ...,
        description="List of resource IDs that can be assigned to this task."
    )


class MPProject(BaseModel):
    id: str = Field(
        ...,
        description="Unique identifier for the project."
    )
    product_type: str = Field(
        ...,
        description="Type of product associated with the project."
    )
    target_date: int = Field(
        ge=0,
        description="Desired completion date for the project."
    )
    latest_date: Optional[int] = Field(
        None,
        ge=0,
        description="Latest completion date for the project."
    )
    weight_positive: int = Field(
        ge=0,
        description="Weight assigned to positive deviations (project finishing after the target date)."
    )
    weight_negative: int = Field(
        ge=0,
        description="Weight assigned to negative deviations (project finishing before the target date)."
    )
    weight_late: int = Field(
        0,
        ge=0,
        description="Weight assigned to lateness (project finishing after latest date)."
    )
    tasks: Dict[str, MPTask] = Field(
        ...,
        description="Dictionary of tasks belonging to the project, keyed by task ID."
    ),
    finish_task_id: str = Field(
        ...,
        description="Id of the last task to be completed in the project."
    )


class MPPeriodConstraint(BaseModel):
    start_date: int = Field(
        ge=0,
        description="Start date of the period during which the constraint is applied."
    )
    end_date: int = Field(
        ge=0,
        description="End date of the period during which the constraint is applied."
    )
    product_type: str = Field(
        ...,
        description="Product type to which this period constraint applies."
    )
    max_projects: int = Field(
        ge=0,
        description="Maximum number of projects of the specified product type that can finish within this period."
    )


class MPSolverStatus(BaseModel):
    status_code: int = Field(
        ...,
        description="Numeric code representing the solver's status."
    )
    status_text: str = Field(
        ...,
        description="Text description of the solver's status."
    )
    objective_value: Optional[float] = Field(
        None,
        description="Value of the objective function if a solution is found."
    )


class MPTaskSolution(BaseModel):
    project_id: str = Field(
        ...,
        description="Identifier of the project to which the task belongs."
    )
    task_id: str = Field(
        ...,
        description="Identifier of the task."
    )
    start: int = Field(
        ...,
        description="Scheduled start time of the task."
    )
    end: int = Field(
        ...,
        description="Scheduled end time of the task."
    )
    resource_assigned: Optional[str] = Field(
        None,
        description="Name of the resource assigned to the task, if any."
    )


# Update forward references in MPTask
MPTask.update_forward_refs()


# Request Model
class MPModelRequest(BaseModel):
    projects: List[MPProject] = Field(
        ...,
        description="List of projects to be scheduled."
    )
    resources: List[MPResource] = Field(
        ...,
        description="List of available resources."
    )
    period_constraints: List[MPPeriodConstraint] = Field(
        default_factory=list,
        description="List of period constraints to be applied."
    )
    horizon: int = Field(
        ...,
        description="Scheduling horizon defining the maximum time frame for scheduling tasks."
    )
    time_limit: int = Field(
        10,
        description="Solver time limit in seconds (default=10)."
    )


# Response Model
class MPModelResponse(BaseModel):
    solver_status: MPSolverStatus = Field(
        ...,
        description="Status of the solver after attempting to solve the model."
    )
    solution: List[MPTaskSolution] = Field(
        default_factory=list,
        description="List of task solutions representing the scheduling results."
    )
