from ortools.sat.python import cp_model
from he_scheduling.core.logging import get_logger
import logging
from typing import Optional, List
from he_scheduling.models.master_planning import (
    MPProject,
    MPResource,
    MPPeriodConstraint,
    MPSolverStatus,
    MPTaskSolution
)


class MasterPlanningModelBuilder:
    def __init__(
            self,
            projects: List[MPProject],
            resources: List[MPResource],
            period_constraints: List[MPPeriodConstraint],
            horizon: int,
            logger: Optional[logging.Logger] = None,
    ):
        self.projects = projects
        self.resources = {resource.id: resource for resource in resources}
        self.period_constraints = period_constraints
        self.horizon = horizon
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Use the provided logger or create a default one
        self.logger = logger or get_logger(__name__)

        # Variables
        self.task_starts = {}
        self.task_ends = {}
        self.task_intervals = {}
        self.task_resources = {}
        self.projects_dict = {project.id: project for project in self.projects}

        # Solution data
        self.solution = []

    def build_model(self):
        self.logger.debug('Building the model...')
        self._create_variables()
        self._add_constraints()
        self._define_objective()
        self.logger.debug('Model building completed.')

    def _create_variables(self):
        self.logger.debug('Creating variables...')
        # Create variables for tasks
        for project in self.projects:
            for task_id, task in project.tasks.items():
                unique_task_id = f'{project.id}_{task_id}'

                # Task variables
                self.task_starts[unique_task_id] = self.model.NewIntVar(0, self.horizon - 1, f'start_{unique_task_id}')
                self.task_ends[unique_task_id] = self.model.NewIntVar(0, self.horizon - 1, f'end_{unique_task_id}')
                self.task_intervals[unique_task_id] = self.model.NewIntervalVar(
                    self.task_starts[unique_task_id],
                    task.duration,
                    self.task_ends[unique_task_id],
                    f'interval_{unique_task_id}'
                )

                # Resource assignment variables
                if task.load > 0:
                    self.task_resources[unique_task_id] = self.model.NewIntVarFromDomain(
                        cp_model.Domain.FromValues(task.alternative_resources),
                        f'resource_{unique_task_id}'
                    )
        self.logger.debug('Variables created.')

    def _add_constraints(self):
        self.logger.debug('Adding constraints...')
        self._add_duration_constraints()
        self._add_precedence_constraints()
        self._add_resource_constraints()
        self._add_period_constraints()
        self.logger.debug('Constraints added.')

    def _add_duration_constraints(self):
        self.logger.debug('Adding duration constraints...')
        # Duration constraints
        for unique_task_id in self.task_starts:
            task_duration = self.task_intervals[unique_task_id].SizeExpr()
            self.model.Add(self.task_ends[unique_task_id] == self.task_starts[unique_task_id] + task_duration)
        self.logger.debug('Duration constraints added.')

    def _add_precedence_constraints(self):
        self.logger.debug('Adding precedence constraints...')
        # Precedence constraints with gaps
        for project in self.projects:
            for task_id, task in project.tasks.items():
                unique_task_id = f'{project.id}_{task_id}'
                for predecessor in task.predecessors:
                    pred_task_id = predecessor.task_id
                    unique_pred_task_id = f'{project.id}_{pred_task_id}'
                    min_gap = predecessor.min_gap
                    max_gap = predecessor.max_gap if predecessor.max_gap is not None else self.horizon
                    # Enforce the gaps
                    self.model.Add(self.task_starts[unique_task_id] >= self.task_ends[unique_pred_task_id] + min_gap)
                    self.model.Add(self.task_starts[unique_task_id] <= self.task_ends[unique_pred_task_id] + max_gap)
        self.logger.debug('Precedence constraints added.')

    def _add_resource_constraints(self):
        self.logger.debug('Adding resource constraints...')
        # Resource assignment and capacity constraints
        for resource_id, resource in self.resources.items():
            intervals = []
            demands = []
            for unique_task_id in self.task_resources:
                project_id, task_id = unique_task_id.split('_', 1)
                task = self.projects_dict[project_id].tasks[task_id]
                if resource_id in task.alternative_resources:
                    # Create presence literal
                    is_resource_assigned = self.model.NewBoolVar(f'is_{unique_task_id}_on_{resource_id}')
                    self.model.Add(self.task_resources[unique_task_id] == resource_id).OnlyEnforceIf(
                        is_resource_assigned)
                    self.model.Add(self.task_resources[unique_task_id] != resource_id).OnlyEnforceIf(
                        is_resource_assigned.Not())
                    # Create optional interval
                    interval = self.model.NewOptionalIntervalVar(
                        self.task_starts[unique_task_id],
                        task.duration,
                        self.task_ends[unique_task_id],
                        is_resource_assigned,
                        f'interval_{unique_task_id}_{resource_id}'
                    )
                    intervals.append(interval)
                    demands.append(task.load)
            # Add cumulative constraint
            if intervals:
                self.model.AddCumulative(intervals, demands, resource.capacity_per_day)
        self.logger.debug('Resource constraints added.')

    def _add_period_constraints(self):
        self.logger.debug('Adding period constraints...')

        for idx, period in enumerate(self.period_constraints):
            start_date = period.start_date
            end_date = period.end_date
            product_type = period.product_type
            max_projects = period.max_projects
            is_in_period_list = []
            for project in self.projects:
                if project.product_type == product_type:
                    # Get the last task in the project
                    last_task_id = list(project.tasks.keys())[-1]
                    unique_task_id = f'{project.id}_{last_task_id}'
                    project_finish = self.task_ends[unique_task_id]
                    is_in_period = self.model.NewBoolVar(f'is_in_period_{project.id}_{idx}')
                    # Define whether the project finishes in the period
                    is_ge_start = self.model.NewBoolVar(f'is_ge_start_{project.id}_{idx}')
                    self.model.Add(project_finish >= start_date).OnlyEnforceIf(is_ge_start)
                    self.model.Add(project_finish < start_date).OnlyEnforceIf(is_ge_start.Not())
                    is_lt_end = self.model.NewBoolVar(f'is_lt_end_{project.id}_{idx}')
                    self.model.Add(project_finish < end_date).OnlyEnforceIf(is_lt_end)
                    self.model.Add(project_finish >= end_date).OnlyEnforceIf(is_lt_end.Not())
                    # is_in_period = is_ge_start AND is_lt_end
                    self.model.AddBoolAnd([is_ge_start, is_lt_end]).OnlyEnforceIf(is_in_period)
                    self.model.AddBoolOr([is_ge_start.Not(), is_lt_end.Not()]).OnlyEnforceIf(is_in_period.Not())
                    is_in_period_list.append(is_in_period)
            # Enforce max_projects
            if is_in_period_list:
                self.model.Add(sum(is_in_period_list) <= max_projects)
        self.logger.debug('Period constraints added.')

    def _define_objective(self):
        self.logger.debug('Defining objective...')
        # Objective function
        objective_terms = []

        for project in self.projects:
            # Get the last task in the project
            last_task_id = list(project.tasks.keys())[-1]
            unique_task_id = f'{project.id}_{last_task_id}'
            project_finish = self.task_ends[unique_task_id]

            target_deviation = self.model.NewIntVar(-self.horizon, self.horizon, f'target_deviation_{project.id}')
            self.model.Add(target_deviation == project_finish - project.target_date)

            # Positive and negative deviations
            positive_deviation = self.model.NewIntVar(0, self.horizon, f'pos_dev_{project.id}')
            negative_deviation = self.model.NewIntVar(0, self.horizon, f'neg_dev_{project.id}')
            self.model.AddMaxEquality(positive_deviation, [target_deviation, 0])
            self.model.AddMinEquality(negative_deviation, [target_deviation, 0])

            # Weighted deviations
            weighted_positive = self.model.NewIntVar(0, self.horizon * project.weight_positive,
                                                     f'weighted_pos_{project.id}')
            weighted_negative = self.model.NewIntVar(0, self.horizon * project.weight_negative,
                                                     f'weighted_neg_{project.id}')
            self.model.Add(weighted_positive == positive_deviation * project.weight_positive)
            self.model.Add(weighted_negative == (-negative_deviation) * project.weight_negative)

            objective_terms.append(weighted_positive)
            objective_terms.append(weighted_negative)

            if project.weight_late > 0:
                lateness = self.model.NewIntVar(-self.horizon, self.horizon, f'lateness_{project.id}')
                self.model.Add(lateness == project_finish -
                               (project.target_date if project.latest_date is None else project.latest_date))

                tardiness = self.model.NewIntVar(0, self.horizon, f'tardiness_{project.id}')
                self.model.AddMaxEquality(tardiness, [lateness, 0])

                weighted_tardiness = self.model.NewIntVar(0, self.horizon * project.weight_late,
                                                          f'weighted_tard_{project.id}')

                self.model.Add(weighted_tardiness == tardiness * project.weight_late)

                objective_terms.append(weighted_tardiness)

        self.model.Minimize(sum(objective_terms))
        self.logger.debug('Objective defined.')

    def solve(self, time_limit: Optional[int] = None) -> MPSolverStatus:
        self.logger.info('Starting solver...')
        # Solver parameters
        if time_limit is not None:
            self.solver.parameters.max_time_in_seconds = time_limit
        else:
            self.solver.parameters.max_time_in_seconds = 10  # Default time limit

        # Enable search logging
        self.solver.parameters.log_search_progress = True

        # Set up logging callback
        self.solver.log_callback = self._solver_log_callback

        # Solve the model
        status_code = self.solver.Solve(self.model)
        status_text = self.solver.StatusName(status_code)
        objective_value = None

        if status_code in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            objective_value = self.solver.ObjectiveValue()
            # Collect solution data
            self._collect_solution()
            self.logger.info(f'Solution found with objective value: {objective_value}')
        else:
            self.solution = []
            self.logger.warning(f'No solution found. Solver status: {status_text}')

        return MPSolverStatus(status_code=status_code, status_text=status_text, objective_value=objective_value)

    def _collect_solution(self):
        self.logger.debug('Collecting solution...')
        self.solution = []
        for project in self.projects:
            for task_id, task in project.tasks.items():
                unique_task_id = f'{project.id}_{task_id}'
                start = self.solver.Value(self.task_starts[unique_task_id])
                end = self.solver.Value(self.task_ends[unique_task_id])
                resource_assigned = None
                if unique_task_id in self.task_resources:
                    resource_id = self.solver.Value(self.task_resources[unique_task_id])
                    resource_assigned = self.resources[resource_id].name
                self.solution.append(MPTaskSolution(
                    project_id=project.id,
                    task_id=task_id,
                    start=start,
                    end=end,
                    resource_assigned=resource_assigned
                ))
        self.logger.debug('Solution collected.')

    def _solver_log_callback(self, log):
        # This function is called by the solver during the search
        self.logger.debug(log)

    def get_solution(self) -> List[MPTaskSolution]:
        return self.solution
