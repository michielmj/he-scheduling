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
def sample_data_simple():
    resources = [
        MPResource(
            id=1,
            name='R1',
            capacity_profile=[
                (0, 15),  # From day 0, capacity is 15
                (12, 10),  # From day 10, capacity changes to 10
            ]
        ),
    ]

    projects = [
        MPProject(
            id='P1',
            product_type='TypeA',
            target_date=20,
            weight_positive=1,
            weight_negative=4,
            tasks={
                'T1': MPTask(
                    id='T1',
                    duration=6,
                    load=12,
                    predecessors=[],
                    alternative_resources=[1],
                ),
            },
            finish_task_id='T1',
        ),
    ]

    period_constraints = [
        MPPeriodConstraint(start_date=0, end_date=30, product_type='TypeA', max_projects=1),
    ]

    return {
        'resources': resources,
        'projects': projects,
        'period_constraints': period_constraints,
        'horizon': 30,
    }


@pytest.fixture
def sample_data_complex():
    resources = [
        MPResource(
            id=1,
            name='R1',
            capacity_profile=[
                (0, 10),  # From day 0, capacity is 10
                (5, 5),   # From day 5, capacity changes to 5
                (10, 8),  # From day 10, capacity changes to 8
            ]
        ),
        MPResource(
            id=2,
            name='R2',
            capacity_profile=[
                (0, 8),   # From day 0, capacity is 8
                (7, 12),  # From day 7, capacity changes to 12
            ]
        ),
        MPResource(
            id=3,
            name='R3',
            capacity_profile=[
                (0, 15),  # From day 0, capacity is 15
                (10, 10), # From day 10, capacity changes to 10
            ]
        ),
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


# Fixture that dynamically gets the correct data based on parameter
@pytest.fixture
def sample_data(request):
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize('sample_data', ['sample_data_simple', 'sample_data_complex'], indirect=['sample_data'])
def test_model_builder_capacity_profiles(sample_data):
    """Test that the model builder handles resources with capacity profiles."""

    # Re-initialize the scheduler with the updated resources
    scheduler = MasterPlanningModelBuilder(
        projects=sample_data['projects'],
        resources=sample_data['resources'],
        period_constraints=sample_data['period_constraints'],
        horizon=sample_data['horizon'],
    )

    # Build and solve the model
    scheduler.build_model()
    status = scheduler.solve()
    assert status.status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Solver did not find a solution."
    solution = scheduler.get_solution()
    assert len(solution) > 0, "Solution should contain tasks."

    # Verify that the tasks are scheduled considering the capacity profiles
    # For this, we can check that resource usage does not exceed capacity in any period
    # Since we don't have direct access to the internal model variables, we can perform an approximate check

    # Build a resource usage timeline
    resource_usage = {res.id: [0]*sample_data['horizon'] for res in sample_data['resources']}
    capacity_profiles = {res.id: res.capacity_profile for res in sample_data['resources']}

    for task_solution in solution:
        # Get the task details
        project = next(p for p in sample_data['projects'] if p.id == task_solution.project_id)
        task = project.tasks[task_solution.task_id]
        start = task_solution.start
        end = task_solution.end
        resource_name = task_solution.resource_assigned
        print(f'Task {task_solution.task_id} scheduled on {resource_name} from {start} to {end}.')

        if task.load > 0 and resource_name:
            resource = next(res for res in sample_data['resources'] if res.name == resource_name)
            # Update resource usage per day
            for day in range(start, end):
                resource_usage[resource.id][day] += task.load

    # Verify that resource usage does not exceed capacity profiles
    for res in sample_data['resources']:
        capacity_profile = res.capacity_profile
        for day in range(sample_data['horizon']):
            # Determine the capacity for this day
            capacity = None
            for start_date, cap in reversed(capacity_profile):
                if day >= start_date:
                    capacity = cap
                    break
            if capacity is None:
                capacity = capacity_profile[0][1]  # Use the earliest capacity if before profile starts

            # Check if usage exceeds capacity
            usage = resource_usage[res.id][day]
            assert usage <= capacity, f"Resource {res.name} exceeds capacity on day {day}: usage {usage} > capacity {capacity}"

    # Optionally, print the resource usage for verification
    for res_id, usage in resource_usage.items():
        print(f"Resource {res_id} usage over time: {usage}")


