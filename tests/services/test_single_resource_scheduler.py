# tests/services/test_single_resource_scheduler.py

import pytest
from he_scheduling.services.single_resource_scheduler import (
    SchedulingTask,
    SchedulingResource,
    schedule_forward,
    schedule_backward,
    improvement_move_in,
)


def test_task_creation():
    """Test that a SchedulingTask is created correctly."""
    task = SchedulingTask("Task1", duration=5, target=10, min_margin_before=2)
    assert task.task_id == "Task1"
    assert task.duration == 5
    assert task.target == 10
    assert task.min_margin_before == 2
    assert task.dirty is True
    assert task.previous is None
    assert task.next is None
    assert task.resource is None


def test_resource_creation():
    """Test that a SchedulingResource is created correctly."""
    resource = SchedulingResource("Resource1")
    assert resource.resource_id == "Resource1"
    assert resource.head is None
    assert resource.tail is None


def test_add_task_to_resource():
    """Test adding tasks to a resource."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task2 = SchedulingTask("Task2", duration=3, target=15)

    resource.add_tail(task1)
    resource.add_tail(task2)

    assert resource.head == task1
    assert resource.tail == task2
    assert task1.next == task2
    assert task1.previous is None
    assert task2.previous == task1
    assert task2.next is None

    # Test that tasks have the correct resource reference
    assert task1.resource == resource
    assert task2.resource == resource


def test_schedule_forward():
    """Test the schedule_forward function."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task2 = SchedulingTask("Task2", duration=3, target=15)
    resource.add_tail(task1)
    resource.add_tail(task2)

    schedule_backward(resource.tail)
    score = schedule_forward(resource.head)

    assert score >= 0
    assert task1.start >= task1.earliest_start
    assert task2.start >= task2.earliest_start
    assert task1.start + task1.duration + task2.min_margin_before <= task2.start


def test_schedule():
    """Test the schedule method of SchedulingResource."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task2 = SchedulingTask("Task2", duration=3, target=15)
    resource.add_tail(task1)
    resource.add_tail(task2)

    score = resource.schedule()

    assert score >= 0
    assert task1.start >= task1.earliest_start
    assert task2.start >= task2.earliest_start
    assert task1.start + task1.duration + task2.min_margin_before <= task2.start


def test_improve():
    """Test the improve method of SchedulingResource."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task2 = SchedulingTask("Task2", duration=3, target=8)
    task3 = SchedulingTask("Task3", duration=4, target=20)
    resource.add_tail(task1)
    resource.add_tail(task2)
    resource.add_tail(task3)

    initial_score = resource.schedule()
    improvement = resource.improve()
    final_score = resource.schedule()

    assert improvement <= 0
    assert final_score <= initial_score
    assert task1.start >= task1.earliest_start
    assert task2.start >= task2.earliest_start
    assert task3.start >= task3.earliest_start


def test_task_move_in():
    """Test the move_in method of SchedulingTask."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task2 = SchedulingTask("Task2", duration=3, target=8)
    task3 = SchedulingTask("Task3", duration=4, target=20)
    resource.add_tail(task1)
    resource.add_tail(task2)
    resource.add_tail(task3)

    resource.schedule()
    task3.move_in()
    resource.schedule()

    # Ensure the order is now task1 -> task3 -> task2
    assert resource.head == task1
    assert task1.next == task3
    assert task3.next == task2
    assert resource.tail == task2


def test_task_move_out():
    """Test the move_out method of SchedulingTask."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task2 = SchedulingTask("Task2", duration=3, target=8)
    task3 = SchedulingTask("Task3", duration=4, target=20)
    resource.add_tail(task1)
    resource.add_tail(task2)
    resource.add_tail(task3)

    resource.schedule()
    task2.move_out()
    resource.schedule()

    # Ensure the order is now task1 -> task3 -> task2
    assert resource.head == task1
    assert task1.next == task3
    assert task3.next == task2
    assert resource.tail == task2


def test_task_insert():
    """Test the insert method of SchedulingTask."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task3 = SchedulingTask("Task3", duration=4, target=20)
    task2 = SchedulingTask("Task2", duration=3, target=8)

    resource.add_tail(task1)
    resource.add_tail(task3)

    # Insert task2 before task3
    task3.insert(task2)

    # Ensure the order is now task1 -> task2 -> task3
    assert resource.head == task1
    assert task1.next == task2
    assert task2.next == task3
    assert resource.tail == task3


def test_task_drop():
    """Test the drop method of SchedulingTask."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task2 = SchedulingTask("Task2", duration=3, target=8)
    task3 = SchedulingTask("Task3", duration=4, target=20)
    resource.add_tail(task1)
    resource.add_tail(task2)
    resource.add_tail(task3)

    # Drop task2
    task2.drop()

    # Ensure task2 is not in the resource
    assert task2.previous is None
    assert task2.next is None
    assert task2.resource is None

    # Ensure the order is now task1 -> task3
    assert resource.head == task1
    assert task1.next == task3
    assert task3.previous == task1
    assert resource.tail == task3


def test_iter_tasks():
    """Test the iter_tasks method of Resource."""
    resource = SchedulingResource("Resource1")
    task_ids = ["Task1", "Task2", "Task3", "Task4"]
    tasks = [SchedulingTask(tid, duration=5, target=10) for tid in task_ids]
    for task in tasks:
        resource.add_tail(task)

    iterated_tasks = [task.task_id for task in resource.iter_tasks()]
    assert iterated_tasks == task_ids


def test_schedule_with_margins():
    """Test scheduling with minimum margins before tasks."""
    resource = SchedulingResource("Resource1")
    task1 = SchedulingTask("Task1", duration=5, target=10, min_margin_before=2)
    task2 = SchedulingTask("Task2", duration=3, target=18, min_margin_before=1)
    task3 = SchedulingTask("Task3", duration=4, target=25, min_margin_before=3)
    resource.add_tail(task1)
    resource.add_tail(task2)
    resource.add_tail(task3)

    resource.schedule()

    # Check that margins are respected
    assert task2.start >= task1.start + task1.duration + task2.min_margin_before
    assert task3.start >= task2.start + task2.duration + task3.min_margin_before


def test_improvement_move_in():
    """Test the improvement_move_in function."""
    task1 = SchedulingTask("Task1", duration=5, target=10)
    task2 = SchedulingTask("Task2", duration=3, target=8)
    task1.next = task2
    task2.previous = task1

    score_before = max(0, task1.start - task1.target) + max(0, task2.start - task2.target)
    improvement = improvement_move_in(task2, execute=True)
    score_after = max(0, task1.start - task1.target) + max(0, task2.start - task2.target)

    assert improvement <= 0
    assert score_after <= score_before
