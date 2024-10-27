import pytest
from ortools.sat.python import cp_model

# Import the classes from your service code
# Adjust the import paths as necessary based on your project structure
from he_scheduling.services.master_planning import MasterPlanningModelBuilder

from he_scheduling.models.master_planning import (
    MPTask,
    MPPredecessor,
    MPProject,
    MPResource,
)


# Sample data for testing
@pytest.fixture
def sample_data():
    resources = [
        MPResource(
            id=1,
            name='R1',
            capacity_per_day=10
        ),
    ]

    projects = [
        MPProject(
            id='P1',
            product_type='TypeA',
            target_date=25,
            weight_positive=1,
            weight_negative=1,
            tasks={
                'T1': MPTask(
                    id='T1',
                    duration=5,
                    load=5,
                    predecessors=[],
                    alternative_resources=[1],
                    end_date_hint=15,
                    fixed_end_date=True  # Fixed end date
                ),
                'T2': MPTask(
                    id='T2',
                    duration=4,
                    load=5,
                    predecessors=[
                        MPPredecessor(task_id='T1', min_gap=0, max_gap=0)
                    ],
                    alternative_resources=[1],
                    end_date_hint=20,
                    fixed_end_date=False  # Non-fixed end date
                ),
                'T3': MPTask(
                    id='T3',
                    duration=3,
                    load=5,
                    predecessors=[
                        MPPredecessor(task_id='T2', min_gap=0, max_gap=0)
                    ],
                    alternative_resources=[1],
                    # No end_date_hint
                ),
            },
            finish_task_id='T3',
        ),
    ]

    period_constraints = []

    return {
        'resources': resources,
        'projects': projects,
        'period_constraints': period_constraints,
        'horizon': 30,
    }


# Test function
def test_task_end_date_hinting(sample_data):

    # Create scheduler with a penalty coefficient for deviations
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=30,
        fixed_violation_penalty_coefficient=100  # Adjust as needed
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    solution = scheduler.get_solution()

    # Extract task solutions
    t1_solution = next((task for task in solution if task.project_id == 'P1' and task.task_id == 'T1'), None)
    t2_solution = next((task for task in solution if task.project_id == 'P1' and task.task_id == 'T2'), None)
    t3_solution = next((task for task in solution if task.project_id == 'P1' and task.task_id == 'T3'), None)

    assert t1_solution is not None, "Task T1 solution not found."
    assert t2_solution is not None, "Task T2 solution not found."
    assert t3_solution is not None, "Task T3 solution not found."

    # Verify that Task T1 ends exactly at its hinted end date (fixed_end_date=True)
    t1_end = t1_solution.end
    t1_deviation = abs(t1_end - 15)
    assert t1_deviation == 0, f"Task T1 deviated from its end date hint: deviation {t1_deviation} != 0"

    # Verify that Task T2 may not necessarily end at its hinted end date (fixed_end_date=False)
    t2_end = t2_solution.end
    t2_deviation = abs(t2_end - 20)
    # Since fixed_end_date is False, deviations are acceptable
    # We can check that T2 starts after T1 ends due to the predecessor constraint
    assert t2_solution.start >= t1_solution.end, "Task T2 should start after Task T1 ends."

    # Verify that Task T3 starts after T2 ends
    assert t3_solution.start >= t2_solution.end, "Task T3 should start after Task T2 ends."

    # Optionally, print the solutions for debugging
    print(f"Task T1: start={t1_solution.start}, end={t1_solution.end}")
    print(f"Task T2: start={t2_solution.start}, end={t2_solution.end}")
    print(f"Task T3: start={t3_solution.start}, end={t3_solution.end}")

    # Check that the fixed violation cost is correctly calculated
    total_fixed_violation_cost = sum(scheduler.solver.Value(cost) for cost in scheduler.fixed_violation_costs)
    assert total_fixed_violation_cost == 0, f"Total fixed violation cost should be zero, got {total_fixed_violation_cost}"


def test_task_end_date_hinting_with_unavoidable_deviation(sample_data):
    """Test that the model penalizes deviations when fixed end date cannot be met."""
    projects = [
        MPProject(
            id='P2',
            product_type='TypeB',
            target_date=30,
            weight_positive=1,
            weight_negative=1,
            weight_late=0,
            tasks={
                'T4': MPTask(
                    id='T4',
                    duration=5,
                    load=10,  # Maxes out the resource capacity
                    predecessors=[],
                    alternative_resources=[1],
                    end_date_hint=10,
                    fixed_end_date=True  # Fixed end date
                ),
                'T5': MPTask(
                    id='T5',
                    duration=5,
                    load=10,  # Maxes out the resource capacity
                    predecessors=[],
                    alternative_resources=[1],
                    end_date_hint=10,
                    fixed_end_date=True  # Fixed end date
                ),
            },
            finish_task_id='T5',
        ),
    ]

    scheduler = MasterPlanningModelBuilder(
        projects=projects,
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=30,
        fixed_violation_penalty_coefficient=100
    )
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    solution = scheduler.get_solution()

    # Extract task solutions
    t4_solution = next((task for task in solution if task.project_id == 'P2' and task.task_id == 'T4'), None)
    t5_solution = next((task for task in solution if task.project_id == 'P2' and task.task_id == 'T5'), None)

    assert t4_solution is not None, "Task T4 solution not found."
    assert t5_solution is not None, "Task T5 solution not found."

    # Verify that tasks cannot both end at day 10 due to resource constraints
    t4_end = t4_solution.end
    t5_end = t5_solution.end

    # Calculate deviations
    t4_deviation = abs(t4_end - 10)
    t5_deviation = abs(t5_end - 10)

    # Since both tasks cannot be scheduled to end at day 10, at least one will have a deviation
    total_deviation = t4_deviation + t5_deviation
    assert total_deviation > 0, "At least one task should deviate from its end date hint due to resource constraints."

    # Verify that the fixed violation cost reflects the deviation
    total_fixed_violation_cost = sum(scheduler.solver.Value(cost) for cost in scheduler.fixed_violation_costs)
    expected_penalty = total_deviation * scheduler.fixed_violation_penalty_coefficient
    assert total_fixed_violation_cost == expected_penalty, f"Fixed violation cost mismatch: expected {expected_penalty}, got {total_fixed_violation_cost}"
