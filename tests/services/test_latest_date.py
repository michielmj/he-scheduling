import pytest
from ortools.sat.python import cp_model

# Import the classes from your service code
# Adjust the import paths as necessary based on your project structure
from he_scheduling.services.master_planning import (
    MasterPlanningModelBuilder
)

from he_scheduling.models.master_planning import (
    MPResource,
    MPPredecessor,
    MPTask,
    MPProject,
)


# Fixtures for resources
@pytest.fixture
def resource_r1():
    return MPResource(
        id=1,
        name='R1',
        capacity_per_day=10
    )


# Fixture for project with a latest date that can be met
@pytest.fixture
def project_with_meetable_latest_date():
    return MPProject(
        id='P1',
        product_type='TypeA',
        target_date=5,
        latest_date=10,
        weight_positive=1,
        weight_negative=1,
        weight_late=1000,  # High penalty for finishing after latest_date
        tasks={
            'T1': MPTask(
                id='T1',
                duration=3,
                load=5,
                predecessors=[],
                alternative_resources=[1],
            ),
            'T2': MPTask(
                id='T2',
                duration=4,
                load=5,
                predecessors=[
                    MPPredecessor(task_id='T1', min_gap=0, max_gap=0)
                ],
                alternative_resources=[1],
            ),
        },
        finish_task_id='T2',
    )


# Fixture for project with a latest date that cannot be met
@pytest.fixture
def project_with_unavoidable_lateness():
    return MPProject(
        id='P1',
        product_type='TypeA',
        target_date=5,
        latest_date=7,
        weight_positive=1,
        weight_negative=1,
        weight_late=1000,  # High penalty for finishing after latest_date
        tasks={
            'T1': MPTask(
                id='T1',
                duration=5,
                load=10,
                predecessors=[],
                alternative_resources=[1],
            ),
            'T2': MPTask(
                id='T2',
                duration=5,
                load=10,
                predecessors=[
                    MPPredecessor(task_id='T1', min_gap=0, max_gap=0)
                ],
                alternative_resources=[1],
            ),
        },
        finish_task_id='T2',
    )


# Fixture for period constraints (empty in these tests)
@pytest.fixture
def empty_period_constraints():
    return []


# Test case for a project where the latest date can be met
def test_model_builder_latest_date_constraint(resource_r1, project_with_meetable_latest_date, empty_period_constraints):
    """Test that the model builder correctly enforces the latest date for projects."""
    resources = [resource_r1]
    projects = [project_with_meetable_latest_date]
    period_constraints = empty_period_constraints

    # Create a scheduler with a horizon that allows the project to potentially exceed the latest date
    scheduler = MasterPlanningModelBuilder(
        projects=projects,
        resources=resources,
        period_constraints=period_constraints,
        horizon=20,
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    solution = scheduler.get_solution()

    # Verify that the project does not finish after the latest date if possible
    project_finish_time = None
    for task_solution in solution:
        if task_solution.project_id == 'P1' and task_solution.task_id == 'T2':
            project_finish_time = task_solution.end
            assert project_finish_time <= 10, f"Project P1 finished after latest date: {project_finish_time} > 10"

    assert project_finish_time is not None, "Project finish time not found in the solution."

    # Additionally, check that the tasks are scheduled correctly
    t1_start = t1_end = t2_start = t2_end = None
    for task_solution in solution:
        if task_solution.project_id == 'P1':
            if task_solution.task_id == 'T1':
                t1_start = task_solution.start
                t1_end = task_solution.end
            elif task_solution.task_id == 'T2':
                t2_start = task_solution.start
                t2_end = task_solution.end

    assert t1_start is not None and t1_end is not None, "Task T1 timings not found."
    assert t2_start is not None and t2_end is not None, "Task T2 timings not found."

    # Check that T1 and T2 are scheduled sequentially with no gaps
    assert t2_start >= t1_end, "Task T2 should start after T1 ends."
    assert t1_end - t1_start == 3, "Task T1 duration should be 3."
    assert t2_end - t2_start == 4, "Task T2 duration should be 4."


# Test case for a project where the latest date cannot be met
def test_model_builder_latest_date_constraint_with_unavoidable_lateness(
    resource_r1,
    project_with_unavoidable_lateness,
    empty_period_constraints
):
    """Test that the model builder correctly applies lateness penalties when latest date cannot be met."""
    resources = [resource_r1]
    projects = [project_with_unavoidable_lateness]
    period_constraints = empty_period_constraints

    # Create a scheduler with a horizon that makes it impossible to finish before the latest date
    scheduler = MasterPlanningModelBuilder(
        projects=projects,
        resources=resources,
        period_constraints=period_constraints,
        horizon=20,
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    solution = scheduler.get_solution()

    # Verify that the project finishes after the latest date and lateness penalty is applied
    project_finish_time = None
    for task_solution in solution:
        if task_solution.project_id == 'P1' and task_solution.task_id == 'T2':
            project_finish_time = task_solution.end
            assert project_finish_time > 7, f"Project P1 should finish after latest date: {project_finish_time} <= 7"

    assert project_finish_time is not None, "Project finish time not found in the solution."

    # Check that the lateness penalty is reflected in the objective value
    expected_lateness = project_finish_time - 7
    expected_penalty = expected_lateness * projects[0].weight_late

    assert status.objective_value >= expected_penalty, "Objective value does not reflect the expected lateness penalty."
