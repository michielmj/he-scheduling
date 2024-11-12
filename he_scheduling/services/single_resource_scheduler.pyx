# distutils: language = c++

# Cython module: single_resource_scheduler.pyx

cdef class TaskResource:
    pass

cdef class Task:

    cdef str task_id
    cdef Task next
    cdef Task previous
    cdef TaskResource resource

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.next = None
        self.previous = None
        self.resource = None

    cpdef move_out(self):
        cdef Task nxt

        if self.next:
            nxt = self.next

            # left side
            nxt.previous = self.previous
            if self.previous:
                self.previous.next = nxt
            elif self.resource:
                self.resource.head = nxt
            self.previous = nxt

            # right side
            self.next = nxt.next
            if nxt.next:
                nxt.next.previous = self
            elif self.resource:
                self.resource.tail = self
            nxt.next = self

    cpdef move_in(self):
        cdef Task prev

        if self.previous:
            prev = self.previous

            # right side
            prev.next = self.next
            if self.next:
                self.next.previous = prev
            elif self.resource:
                self.resource.tail = prev
            self.next = prev

            # left side
            self.previous = prev.previous
            if prev.previous:
                prev.previous.next = self
            elif self.resource:
                self.resource.head = self
            prev.previous = self

    cpdef drop(self):
        if self.previous:
            self.previous.next = self.next
        elif self.resource:
            self.resource.head = self.next

        if self.next:
            self.next.previous = self.previous
        elif self.resource:
            self.resource.tail = self.previous

        self.previous = None
        self.next = None
        self.resource = None

    cpdef insert(self, Task task):
        # remove from existing resource
        task.drop()
        task.resource = self.resource
        if self.previous:
            self.previous.next = task
        elif self.resource:
            self.resource.head = task

        task.next = self
        task.previous = self.previous
        self.previous = task

    def __str__(self):
        return self.task_id


cdef class Resource(TaskResource):

    cdef public str resource_id
    cdef Task head
    cdef Task tail

    def __init__(self, resource_id):
        self.resource_id = resource_id
        self.head = None
        self.tail = None

    cpdef add_tail(self, Task task):
        task.resource = self
        task.next = None
        if self.tail:
            task.previous = self.tail
            self.tail.next = task
        else:
            task.previous = None
        self.tail = task
        if not self.head:
            self.head = task

    cpdef add_head(self, Task task):
        task.resource = self
        task.previous = None
        if self.head:
            task.next = self.head
            self.head.previous = task
        else:
            task.next = None
        self.head = task
        if not self.tail:
            self.tail = task

    def iter_tasks(self):
        cdef Task t = self.head
        while t:
            yield t
            t = t.next

    def __str__(self):
        return f'{self.resource_id}[{", ".join([str(t) for t in self.iter_tasks()])}]'


cdef class SchedulingTask(Task):

    cdef int _duration
    cdef int _target
    cdef int _min_margin_before
    cdef bint _dirty
    cdef int _earliest_start
    cdef int _start

    def __init__(self, task_id, int duration, int target, int min_margin_before=0):
        super().__init__(task_id)

        self._duration = duration
        self._target = target
        self._dirty = True
        self._earliest_start = 0
        self._start = target
        self._min_margin_before = min_margin_before

    def __str__(self):
        if self._dirty:
            return (f"{self.task_id}"
                    f"[d={f'{self._min_margin_before}+' if self._min_margin_before != 0 else ''}"
                    f"{self._duration}, t={self._target}, s=...]")
        else:
            return (f"{self.task_id}"
                    f"[d={f'{self._min_margin_before}+' if self._min_margin_before != 0 else ''}"
                    f"{self._duration}, t={self._target}, s={self._start}]")

    @property
    def dirty(self):
        return self._dirty

    cpdef invalidate(self):
        cdef SchedulingTask next_task
        self._dirty = True
        if self.next:
            next_task = <SchedulingTask>self.next
            if next_task is not None:
                next_task.invalidate()

    cpdef calculate(self):
        cdef SchedulingTask prev_task
        print(f"{str(self)} calculating...")
        prev_task = <SchedulingTask>self.previous
        if prev_task is not None:
            self._earliest_start = prev_task.earliest_stop + self._min_margin_before
            self._start = max(self._earliest_start, self._start)
        else:
            self._earliest_start = 0

        self._dirty = False

    @property
    def duration(self):
        return self._duration

    @property
    def min_margin_before(self):
        return self._min_margin_before

    @property
    def target(self):
        return self._target

    @property
    def earliest_start(self):
        if self._dirty:
            self.calculate()

        return self._earliest_start

    @property
    def earliest_stop(self):
        return self.earliest_start + self._duration

    @property
    def start(self):
        if self._dirty:
            self.calculate()

        return self._start

    @start.setter
    def start(self, value):
        self._start = max(self.earliest_start, value)

    cpdef move_out(self):
        super().move_out()
        self.invalidate()

    cpdef move_in(self):
        super().move_in()
        self.invalidate()

    cpdef insert(self, Task task):
        cdef SchedulingTask sched_task = <SchedulingTask> task
        super().insert(sched_task)
        sched_task.invalidate()

    cpdef drop(self):
        self.invalidate()
        super().drop()


cpdef int schedule_forward(SchedulingTask t):
    cdef int score = 0
    cdef SchedulingTask prev

    while t:
        prev = <SchedulingTask>t.previous
        if prev is not None:
            t.start = max(prev.start + prev.duration + t.min_margin_before, t.start)
        score += max(0, t.start - t.target)
        t = t.next

    return score


cpdef schedule_backward(SchedulingTask t):
    cdef SchedulingTask next_task

    while t:
        next_task = <SchedulingTask>t.next
        if next_task is not None:
            t.start = min(t.target, next_task.start - next_task.min_margin_before - t.duration)
        else:
            t.start = t.target
        t = t.previous


cpdef int improvement_move_in(SchedulingTask task, bint execute=False):
    cdef SchedulingTask t1
    cdef SchedulingTask t2
    cdef int t1_cs
    cdef int t2_cs
    cdef int t1_as
    cdef int t2_as
    cdef int improvement
    cdef SchedulingTask next_task

    if not task.previous:
        return 0

    t1 = <SchedulingTask>task.previous
    if t1 is None:
        return 0

    t2 = task

    # current t1 -> t2
    t1_cs = max(0, t1.start - t1.target)
    t2_cs = max(0, t2.start - t2.target)

    # alternative s2 -> s1
    # as: improved score
    t1_as = max(0, t1.earliest_start + t2.min_margin_before + t2.duration - t1.target)
    t2_as = max(0, t1.earliest_start - t1.min_margin_before + t2.min_margin_before - t2.target)

    improvement = t1_as + t2_as - t1_cs - t2_cs
    if execute and improvement < 0:
        task.move_in()
        next_task = <SchedulingTask>task.next
        if next_task is not None:
            next_task.start = max(
                next_task.earliest_start - next_task.min_margin_before,
                min(task.target, task.start)
            )
        task.start = max(
            task.earliest_start,
            min(next_task.start - next_task.min_margin_before - task.duration, task.target)
        )

    return improvement


cdef class SchedulingResource(Resource):

    # Note: We cannot redeclare 'head' and 'tail' as 'SchedulingTask' directly.
    # We'll access them and cast when necessary.

    def __init__(self, resource_id):
        super().__init__(resource_id)

    cpdef int schedule(self):
        cdef SchedulingTask tail_task
        cdef SchedulingTask head_task


        tail_task = <SchedulingTask>self.tail
        if tail_task is not None:
            schedule_backward(tail_task)
        head_task = <SchedulingTask>self.head
        if head_task is not None:
            return schedule_forward(head_task)
        return 0  # If there are no tasks, return zero score

    cpdef int improve(self):
        cdef SchedulingTask t
        cdef int improvement
        cdef int step_improvement

        t = <SchedulingTask>self.tail
        if t is None:
            return 0

        improvement = 0

        while t:
            step_improvement = improvement_move_in(t, execute=True)
            if step_improvement < 0:
                improvement += step_improvement
            else:
                t = t.previous

        return improvement
