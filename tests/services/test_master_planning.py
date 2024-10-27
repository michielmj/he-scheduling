# File: tests/services/test_master_planning.py

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
    MPPeriodConstraint,
)


# Sample data for testing
@pytest.fixture
def sample_data():
    resources = [
        MPResource(id=1, name='R1', capacity_per_day=10),
        MPResource(id=2, name='R2', capacity_per_day=8),
        MPResource(id=3, name='R3', capacity_per_day=15),
    ]

    projects = [
        MPProject(
            id='P1',
            product_type='TypeA',
            target_date=15,
            latest_date=20,
            weight_positive=2,
            weight_negative=3,
            tasks={
                'T1': MPTask(
                    id='T1',
                    duration=5,
                    load=10,
                    predecessors=[],
                    alternative_resources=[1, 2],
                ),
                'T2': MPTask(
                    id='T2',
                    duration=3,
                    load=5,
                    predecessors=[
                        MPPredecessor(task_id='T1', min_gap=0, max_gap=0)
                    ],
                    alternative_resources=[2],
                ),
            },
            finish_task_id='T1',
        ),
        MPProject(
            id='P2',
            product_type='TypeB',
            target_date=20,
            weight_positive=1,
            weight_negative=4,
            tasks={
                'T3': MPTask(
                    id='T3',
                    duration=4,
                    load=8,
                    predecessors=[],
                    alternative_resources=[1],
                ),
                'T4': MPTask(
                    id='T4',
                    duration=6,
                    load=12,
                    predecessors=[
                        MPPredecessor(task_id='T3', min_gap=0, max_gap=0)
                    ],
                    alternative_resources=[3],
                ),
            },
            finish_task_id='T4',
        ),
    ]

    period_constraints = [
        MPPeriodConstraint(start_date=0, end_date=10, product_type='TypeA', max_projects=1),
        MPPeriodConstraint(start_date=0, end_date=10, product_type='TypeB', max_projects=1),
        MPPeriodConstraint(start_date=10, end_date=20, product_type='TypeA', max_projects=1),
        MPPeriodConstraint(start_date=10, end_date=20, product_type='TypeB', max_projects=1),
        MPPeriodConstraint(start_date=20, end_date=30, product_type='TypeA', max_projects=1),
        MPPeriodConstraint(start_date=20, end_date=30, product_type='TypeB', max_projects=1),
    ]

    return {
        'resources': resources,
        'projects': projects,
        'period_constraints': period_constraints,
        'horizon': 30,
    }


def test_model_builder_valid_solution(sample_data):
    """Test that the model builder finds a valid solution with the sample data."""
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=sample_data['horizon'],
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    assert status.objective_value is not None, "Objective value should not be None."
    solution = scheduler.get_solution()
    assert len(solution) > 0, "Solution should contain tasks."
    # Further assertions can be added to check the correctness of the solution
    for task_solution in solution:
        assert task_solution.start >= 0, "Task start time should be non-negative."
        assert task_solution.end > task_solution.start, "Task end time should be after start time."
        if task_solution.resource_assigned:
            assert task_solution.resource_assigned in [res.name for res in sample_data['resources']], \
                "Assigned resource is invalid."


def test_model_builder_infeasible_problem(sample_data):
    """Test that the model builder correctly identifies an infeasible problem."""
    # Modify the sample data to create an infeasible problem

    # Set max_projects to zero for all periods covering the project's target date
    for period_constraint in sample_data['period_constraints']:
        if period_constraint.product_type == 'TypeA':
            period_constraint.max_projects = 0  # Disallow TypeA projects in all periods

    # Adjust the target date of the TypeA project to fall within these periods
    sample_data['projects'][0].target_date = 10  # Set P1's target date to 10

    # Since all periods disallow TypeA projects, and P1's target date is 10,
    # it's impossible to schedule P1 to meet its target date without violating period constraints.

    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=sample_data['horizon'],
    )
    scheduler.build_model()
    status = scheduler.solve()

    # Assert that the solver reports infeasibility
    assert status.status_code == cp_model.INFEASIBLE, "Solver should report infeasibility due to period constraints."
    solution = scheduler.get_solution()
    assert len(solution) == 0, "Solution should be empty for infeasible problems."


def test_model_builder_invalid_input():
    """Test that the model builder handles invalid input data gracefully."""

    with pytest.raises(ValueError):
        # Create invalid sample data (e.g., negative duration)
        resources = [
            MPResource(id=1, name='R1', capacity_per_day=10),
        ]
        projects = [
            MPProject(
                id='P1',
                product_type='TypeA',
                target_date=15,
                latest_date=20,
                weight_positive=2,
                weight_negative=3,
                weight_late=30,
                tasks={
                    'T1': MPTask(
                        id='T1',
                        duration=-5,  # Invalid negative duration
                        load=10,
                        predecessors=[],
                        alternative_resources=[1],
                    ),
                },
                finish_task_id='T1',
            ),
        ]
        period_constraints = []


def test_model_builder_zero_capacity(sample_data):
    """Test that the model builder handles resources with zero capacity."""
    # Set resource capacity to zero to create a capacity issue
    for resource in sample_data['resources']:
        resource.capacity_per_day = 0
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=sample_data['horizon'],
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code == cp_model.INFEASIBLE, "Solver should report infeasibility due to zero capacity."
    solution = scheduler.get_solution()
    assert len(solution) == 0, "Solution should be empty when resources have zero capacity."


def test_model_builder_multiple_solutions(sample_data):
    """Test that the model builder can handle multiple possible solutions."""
    # Adjust sample data to allow multiple solutions
    # For example, remove period constraints
    sample_data['period_constraints'] = []
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=[],
        horizon=sample_data['horizon'],
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    solution = scheduler.get_solution()
    assert len(solution) > 0, "Solution should contain tasks."
    # Optionally, you could run the solver multiple times or modify the objective to test different solutions


def test_model_builder_time_limit(sample_data):
    """Test that the model builder respects the time limit parameter."""
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=sample_data['horizon'],
    )
    scheduler.build_model()
    # Set a very short time limit
    status = scheduler.solve(time_limit=0.001)
    assert status.status_code == cp_model.UNKNOWN, "Solver should return UNKNOWN due to time limit."
    # Depending on the problem size, the solver may or may not find a solution
    # So we don't assert on the solution content in this case


def test_model_builder_large_horizon(sample_data):
    """Test that the model builder handles a large scheduling horizon."""
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=1000,  # Large horizon
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        "Solver did not find a solution with large horizon."
    solution = scheduler.get_solution()
    assert len(solution) > 0, "Solution should contain tasks."
    # Check that task start and end times are within the horizon
    for task_solution in solution:
        assert 0 <= task_solution.start <= 1000, "Task start time out of bounds."
        assert 0 < task_solution.end <= 1000, "Task end time out of bounds."


def test_model_builder_no_resources():
    """Test that the model builder handles cases with no available resources."""
    resources = []
    projects = [
        MPProject(
            id='P1',
            product_type='TypeA',
            target_date=15,
            latest_date=20,
            weight_positive=2,
            weight_negative=3,
            weight_late=30,
            tasks={
                'T1': MPTask(
                    id='T1',
                    duration=5,
                    load=10,
                    predecessors=[],
                    alternative_resources=[],  # Resource ID that doesn't exist
                ),
            },
            finish_task_id='T1',
        ),
    ]
    period_constraints = []
    scheduler = MasterPlanningModelBuilder(
        projects=projects,
        resources=resources,
        period_constraints=period_constraints,
        horizon=30,
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code == cp_model.MODEL_INVALID, "Solver should report invalid due to no resources."
    solution = scheduler.get_solution()
    assert len(solution) == 0, "Solution should be empty when there are no resources."


def test_model_builder_task_without_load(sample_data):
    """Test that the model builder handles tasks without resource load."""
    # Add a task with zero load
    sample_data['projects'][0].tasks['T3'] = MPTask(
        id='T3',
        duration=2,
        load=0,  # Zero load
        predecessors=[],
        alternative_resources=[1, 2],
    )
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=sample_data['horizon'],
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    solution = scheduler.get_solution()
    assert any(task.task_id == 'T3' for task in solution), "Task T3 should be in the solution."
    # Check that task T3 has correct start and end times
    for task_solution in solution:
        if task_solution.task_id == 'T3' and task_solution.project_id == 'P1':
            assert task_solution.start >= 0, "Task T3 start time should be non-negative."
            assert task_solution.end > task_solution.start, "Task T3 end time should be after start time."
            assert task_solution.resource_assigned is None, "Task T3 should not have a resource assigned."


def test_model_builder_task_with_predecessors(sample_data):
    """Test that the model builder correctly enforces task predecessors."""
    # Add a chain of tasks with predecessors
    sample_data['projects'][0].tasks['T5'] = MPTask(
        id='T5',
        duration=2,
        load=5,
        predecessors=[MPPredecessor(task_id='T2', min_gap=1, max_gap=1)],
        alternative_resources=[1],
    )
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=sample_data['horizon'],
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    solution = scheduler.get_solution()
    # Check that T5 starts exactly 1 time unit after T2 ends
    t2_end = None
    t5_start = None
    for task_solution in solution:
        if task_solution.task_id == 'T2':
            t2_end = task_solution.end
        if task_solution.task_id == 'T5':
            t5_start = task_solution.start
    assert t2_end is not None, "Task T2 should be in the solution."
    assert t5_start is not None, "Task T4 should be in the solution."
    assert t5_start == t2_end + 1, "Task T4 should start exactly 1 time unit after T2 ends."


