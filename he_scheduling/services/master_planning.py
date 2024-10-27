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
            overload_penalty_coefficient: Optional[int] = 1000,
            fixed_violation_penalty_coefficient: Optional[int] = 100,
            logger: Optional[logging.Logger] = None,
    ):
        self.projects = projects
        self.resources = {resource.id: resource for resource in resources}
        self.period_constraints = period_constraints
        self.horizon = horizon
        self.overload_costs = []
        self.overload_penalty_coefficient = overload_penalty_coefficient
        self.fixed_violation_penalty_coefficient = fixed_violation_penalty_coefficient
        self.fixed_violation_costs = []
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

        # Preprocess resource constraints
        self.resource_periods = {}  # Key: resource_id, Value: List of (start, end, capacity)
        self._preprocess_resource_capacities()

        # Solution data
        self.solution = []

    def build_model(self):
        self.logger.debug('Building the model...')
        self._create_task_variables()
        self._add_constraints()
        self._define_objective()
        self.logger.debug('Model building completed.')

    def _create_task_variables(self):
        self.logger.debug('Creating variables...')
        # Create variables for tasks
        for project in self.projects:
            for task_id, task in project.tasks.items():
                unique_task_id = f'{project.id}_{task_id}'

                # Task variables
                self.task_starts[unique_task_id] = self.model.new_int_var(0, self.horizon - 1,
                                                                          f'start_{unique_task_id}')
                self.task_ends[unique_task_id] = self.model.new_int_var(0, self.horizon - 1, f'end_{unique_task_id}')
                self.task_intervals[unique_task_id] = self.model.NewIntervalVar(
                    self.task_starts[unique_task_id],
                    task.duration,
                    self.task_ends[unique_task_id],
                    f'interval_{unique_task_id}'
                )

                # Resource assignment variables
                if task.load > 0:
                    self.task_resources[unique_task_id] = self.model.new_int_var_from_domain(
                        cp_model.Domain.from_values(task.alternative_resources),
                        f'resource_{unique_task_id}'
                    )
        self.logger.debug('Variables created.')

    def _add_task_end_date_hints(self):
        self.logger.debug('Adding task end date hints...')
        self.fixed_violation_costs = []

        for project in self.projects:
            for task_id, task in project.tasks.items():
                if task.end_date_hint is not None and task.fixed_end_date:
                    unique_task_id = f'{project.id}_{task_id}'
                    end_var = self.task_ends[unique_task_id]
                    start_var = self.task_starts[unique_task_id]

                    # Provide the end date hint to the solver
                    self.model.AddHint(end_var, task.end_date_hint)
                    self.model.AddHint(start_var, task.end_date_hint - task.duration)

                    # Create deviation variable
                    deviation = self.model.new_int_var(-self.horizon, self.horizon, f'deviation_{unique_task_id}')
                    self.model.add(deviation == end_var - task.end_date_hint)

                    # Absolute deviation
                    abs_deviation = self.model.new_int_var(0, self.horizon, f'abs_deviation_{unique_task_id}')
                    self.model.add_abs_equality(abs_deviation, deviation)

                    # Multiply by penalty coefficient
                    penalty = self.model.NewIntVar(
                        0,
                        self.fixed_violation_penalty_coefficient * self.horizon,
                        f'penalty_{unique_task_id}'
                    )
                    self.model.add_multiplication_equality(
                        penalty,
                        [abs_deviation, self.fixed_violation_penalty_coefficient])

                    # Add to objective terms
                    self.fixed_violation_costs.append(penalty)

        self.logger.debug('Task end date hints added.')

    def _add_constraints(self):
        self.logger.debug('Adding constraints...')
        self._add_precedence_constraints()
        self._add_resource_constraints()
        self._add_period_constraints()
        self._add_task_end_date_hints()
        self.logger.debug('Constraints added.')

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

                    # Enforce the gaps
                    self.model.add(self.task_starts[unique_task_id] >= self.task_ends[unique_pred_task_id] + min_gap)
                    if predecessor.max_gap is not None:
                        self.model.add(self.task_starts[unique_task_id] <=
                                       self.task_ends[unique_pred_task_id] + predecessor.max_gap)
        self.logger.debug('Precedence constraints added.')

    def _preprocess_resource_capacities(self):
        self.resource_periods = {}  # Key: resource_id, Value: List of (start, end, capacity)
        for res_id, resource in self.resources.items():
            capacity_profile = resource.capacity_profile  # List of (date, capacity)
            periods = []
            if capacity_profile:
                # Sort the capacity profile by date
                capacity_profile.sort(key=lambda x: x[0])
                current_capacity = capacity_profile[0][1]
                start_date = capacity_profile[0][0]
                for i in range(1, len(capacity_profile)):
                    date, capacity = capacity_profile[i]
                    if capacity != current_capacity:
                        periods.append((start_date, date, current_capacity))
                        start_date = date
                        current_capacity = capacity
                periods.append((start_date, self.horizon, current_capacity))
            else:
                # If no capacity profile is provided, assume constant capacity
                periods.append((0, self.horizon, resource.capacity_per_day))
            self.resource_periods[res_id] = periods

    def _add_resource_constraints(self):
        self.logger.debug('Adding resource constraints...')
        # Enforce that each task is assigned to exactly one resource from its alternatives
        for unique_task_id, resource_var in self.task_resources.items():
            project_id, task_id = unique_task_id.split('_', 1)
            task = self.projects_dict[project_id].tasks[task_id]
            self.model.add_allowed_assignments(
                [resource_var],
                [[res_id] for res_id in task.alternative_resources]
            )

        self.overload_costs = []  # Store overload costs for the objective function

        for res_id, periods in self.resource_periods.items():
            for period_start, period_end, capacity in periods:
                intervals = []
                demands = []

                for unique_task_id, resource_var in self.task_resources.items():
                    # Check if the task can be assigned to this resource
                    project_id, task_id = unique_task_id.split('_', 1)
                    task = self.projects_dict[project_id].tasks[task_id]
                    if res_id in task.alternative_resources:
                        # Variables for task assignment and timing
                        start_var = self.task_starts[unique_task_id]
                        end_var = self.task_ends[unique_task_id]

                        # Define Boolean variable for task assignment to resource
                        is_assigned = self.model.new_bool_var(f'is_{unique_task_id}_on_{res_id}')
                        self.model.add(resource_var != res_id).only_enforce_if(is_assigned.Not())

                        # Compute overlap_start and overlap_end
                        overlap_start = self.model.new_int_var(
                            0, self.horizon - 1,
                            f'overlap_start_{unique_task_id}_on_{res_id}_{period_start}_{period_end}')
                        overlap_end = self.model.new_int_var(
                            0, period_end,
                            f'overlap_end_{unique_task_id}_on_{res_id}_{period_start}_{period_end}')

                        self.model.add_max_equality(overlap_start, [start_var, period_start])
                        self.model.add_min_equality(overlap_end, [end_var, period_end])

                        # We may ignore this interval only if there is no overlap or if the task is not assigned to
                        # the resource
                        has_overlap = self.model.new_bool_var(
                            f'has_overlap_{unique_task_id}_on_{res_id}_{period_start}_{period_end}')
                        self.model.add(overlap_end < overlap_start).only_enforce_if(has_overlap.Not())

                        overlap_active = self.model.new_bool_var(
                            f'overlap_active_{unique_task_id}_on_{res_id}_{period_start}_{period_end}')
                        self.model.AddBoolOr([is_assigned.Not(), has_overlap.Not()]).only_enforce_if(
                            overlap_active.Not())

                        # Create an optional interval for the overlap
                        overlap_duration = self.model.new_int_var(
                            0, period_end - period_start,
                            f'overlap_duration_{unique_task_id}_on_{res_id}_{period_start}_{period_end}')
                        overlap_interval = self.model.new_optional_interval_var(
                            overlap_start,
                            overlap_duration,
                            overlap_end,
                            overlap_active,
                            f'overlap_interval_{unique_task_id}_on_{res_id}_{period_start}_{period_end}'
                        )
                        intervals.append(overlap_interval)
                        demands.append(task.load)

                # add overload costs only if there are intervals and the total demands may exceed capacity
                if intervals and sum(demands) > capacity:
                    # Create an overload variable for this resource and period
                    overload = self.model.new_int_var(0, sum(demands) - capacity,
                                                      f'overload_{res_id}_{period_start}_{period_end}')

                    self.model.add_cumulative(intervals, demands, capacity + overload)

                    # Add overload penalty to the objective function
                    overload_cost = self.model.new_int_var(
                        0, self.overload_penalty_coefficient * capacity * (period_end - period_start),
                        f'overload_cost_{res_id}_{period_start}_{period_end}')
                    self.model.add_multiplication_equality(overload_cost, [overload, self.overload_penalty_coefficient])
                    self.overload_costs.append(overload_cost)

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
                    # Get the finish task in the project
                    unique_task_id = f'{project.id}_{project.finish_task_id}'
                    project_finish = self.task_ends[unique_task_id]
                    finish_before = self.model.new_bool_var(f'finish_before_{project.id}_{idx}')
                    self.model.add(project_finish < start_date).only_enforce_if(finish_before)
                    finish_after = self.model.new_bool_var(f'finish_after_{project.id}_{idx}')
                    self.model.add(project_finish >= end_date).only_enforce_if(finish_after)

                    is_in_period = self.model.new_bool_var(f'is_in_period_{project.id}_{idx}')
                    self.model.add_bool_or([finish_before, finish_after]).only_enforce_if(is_in_period.Not())

                    is_in_period_list.append(is_in_period)
            # Enforce max_projects
            if is_in_period_list:
                self.model.add(sum(is_in_period_list) <= max_projects)
        self.logger.debug('Period constraints added.')

    def _define_objective(self):
        self.logger.debug('Defining objective...')
        # Objective function
        objective_terms = []

        for project in self.projects:
            # Get the last task in the project
            unique_task_id = f'{project.id}_{project.finish_task_id}'
            project_finish = self.task_ends[unique_task_id]

            target_deviation = self.model.new_int_var(-self.horizon, self.horizon, f'target_deviation_{project.id}')
            self.model.add(target_deviation == project_finish - project.target_date)

            # Positive and negative deviations
            positive_deviation = self.model.new_int_var(0, self.horizon * project.weight_positive,
                                                        f'pos_dev_{project.id}')
            negative_deviation = self.model.new_int_var(0, self.horizon * project.weight_negative,
                                                        f'neg_dev_{project.id}')
            self.model.add_max_equality(positive_deviation, [project.weight_positive * target_deviation, 0])
            self.model.add_max_equality(negative_deviation, [-project.weight_negative * target_deviation, 0])

            objective_terms.append(positive_deviation)
            objective_terms.append(negative_deviation)

            if project.weight_late > 0:
                lateness = self.model.new_int_var(-self.horizon, self.horizon, f'lateness_{project.id}')
                self.model.add(lateness == project_finish - project.latest_date)

                tardiness = self.model.new_int_var(0, self.horizon * project.weight_late,
                                                   f'tardiness_{project.id}')
                self.model.add_max_equality(tardiness, [lateness * project.weight_late, 0])

                objective_terms.append(tardiness)

        # Add overload costs to the objective
        objective_terms.extend(self.overload_costs)

        # Add task end date penalties
        objective_terms.extend(self.fixed_violation_costs)

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
            objective_value = self.solver.objective_value
            # Collect solution data
            self._collect_solution()
            self.logger.info(f'Solution found with objective value: {objective_value}')
        else:
            self.solution = []
            self.logger.warning(f'No solution found. Solver status: {status_text}')

        # noinspection PyTypeChecker
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
