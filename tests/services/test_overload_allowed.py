import pytest
from ortools.sat.python import cp_model

# Import the classes from your service code
# Adjust the import paths as necessary based on your project structure
from he_scheduling.services.master_planning import MasterPlanningModelBuilder

from he_scheduling.models.master_planning import (
    MPResource,
    MPTask,
    MPProject,
)


# Fixture for the resource
@pytest.fixture
def resource():
    return MPResource(
        id=1,
        name='R1',
        capacity_per_day=10,
        # We'll set 'overloading_allowed' in the test functions
    )


# Fixture for the projects
@pytest.fixture
def projects():
    return [
        MPProject(
            id='P1',
            product_type='TypeA',
            target_date=10,
            weight_positive=100,
            weight_negative=1,
            tasks={
                'T1': MPTask(
                    id='T1',
                    duration=6,  # Increased duration
                    load=6,
                    predecessors=[],
                    alternative_resources=[1],
                ),
            },
            finish_task_id='T1',
        ),
        MPProject(
            id='P2',
            product_type='TypeA',
            target_date=10,
            weight_positive=100,
            weight_negative=1,
            tasks={
                'T2': MPTask(
                    id='T2',
                    duration=6,  # Increased duration
                    load=6,
                    predecessors=[],
                    alternative_resources=[1],
                ),
            },
            finish_task_id='T2',
        ),
    ]


# Fixture for period constraints (empty in these tests)
@pytest.fixture
def empty_period_constraints():
    return []


def test_overloading_allowed(resource, projects, empty_period_constraints):
    """Test that the model allows overloading to meet target dates when overloading is allowed."""
    # Set overloading_allowed to True
    resource.overloading_allowed = True
    resources = [resource]

    scheduler = MasterPlanningModelBuilder(
        projects=projects,
        resources=resources,
        period_constraints=empty_period_constraints,
        horizon=20,
        overload_penalty_coefficient=1,  # Low penalty to favor overloading over missing target dates
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.FEASIBLE, cp_model.OPTIMAL], "Solver did not find a solution."

    solution = scheduler.get_solution()
    assert solution, "No solution returned."

    # Extract task solutions
    t1_solution = next((task for task in solution if task.task_id == 'T1'), None)
    t2_solution = next((task for task in solution if task.task_id == 'T2'), None)

    assert t1_solution is not None, "Task T1 solution not found."
    assert t2_solution is not None, "Task T2 solution not found."

    # Verify that tasks are scheduled concurrently
    t1_start, t1_end = t1_solution.start, t1_solution.end
    t2_start, t2_end = t2_solution.start, t2_solution.end

    # Check for overlap
    tasks_overlap = not (t1_end <= t2_start or t2_end <= t1_start)
    assert tasks_overlap, "Tasks T1 and T2 should overlap when overloading is allowed."

    # Verify that projects finish by the target date
    project1_finish_time = t1_end
    project2_finish_time = t2_end

    assert project1_finish_time <= 10, f"Project P1 should finish by target date 10, but finishes at {project1_finish_time}."
    assert project2_finish_time <= 10, f"Project P2 should finish by target date 10, but finishes at {project2_finish_time}."

    # Verify that an overload penalty is applied
    total_overload_cost = sum(scheduler.solver.Value(cost) for cost in scheduler.overload_costs)
    assert total_overload_cost > 0, "Overload penalty should be applied when overloading is allowed and capacity is exceeded."

    # Optionally, print the overload cost and task schedules for debugging
    print(f"Total overload cost: {total_overload_cost}")
    print(f"Task T1: start={t1_start}, end={t1_end}")
    print(f"Task T2: start={t2_start}, end={t2_end}")


def test_overloading_disallowed(resource, projects, empty_period_constraints):
    """Test that the model does not allow overloading and accepts delays when overloading is disallowed."""
    # Set overloading_allowed to False
    resource.overloading_allowed = False
    resources = [resource]

    scheduler = MasterPlanningModelBuilder(
        projects=projects,
        resources=resources,
        period_constraints=empty_period_constraints,
        horizon=20,
        overload_penalty_coefficient=1,  # Not relevant since overloading is disallowed
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.FEASIBLE, cp_model.OPTIMAL], "Solver did not find a solution."

    solution = scheduler.get_solution()
    assert solution, "No solution returned."

    # Extract task solutions
    t1_solution = next((task for task in solution if task.task_id == 'T1'), None)
    t2_solution = next((task for task in solution if task.task_id == 'T2'), None)

    assert t1_solution is not None, "Task T1 solution not found."
    assert t2_solution is not None, "Task T2 solution not found."

    # Verify that tasks are scheduled sequentially
    t1_start, t1_end = t1_solution.start, t1_solution.end
    t2_start, t2_end = t2_solution.start, t2_solution.end

    # Check for overlap
    tasks_overlap = not (t1_end <= t2_start or t2_end <= t1_start)
    assert not tasks_overlap, "Tasks T1 and T2 should not overlap when overloading is disallowed."

    # Verify that at least one project misses the target date
    project1_finish_time = t1_end
    project2_finish_time = t2_end

    projects_missed_target = 0
    if project1_finish_time > 10:
        projects_missed_target += 1
    if project2_finish_time > 10:
        projects_missed_target += 1

    assert projects_missed_target > 0, "At least one project should miss the target date when overloading is disallowed."

    # Verify that no overload penalty is applied
    total_overload_cost = sum(scheduler.solver.Value(cost) for cost in scheduler.overload_costs)
    assert total_overload_cost == 0, "No overload penalty should be applied when overloading is disallowed."

    # Optionally, print the lateness penalties and task schedules for debugging
    print(f"Project P1 finishes at {project1_finish_time}")
    print(f"Project P2 finishes at {project2_finish_time}")
    print(f"Task T1: start={t1_start}, end={t1_end}")
    print(f"Task T2: start={t2_start}, end={t2_end}")
