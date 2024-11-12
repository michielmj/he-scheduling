from typing import TypeVar, Generic, Optional, Iterable, Self


class TaskResource:
    pass


class Task:

    def __init__(self, task_id: str):

        self.task_id: str = task_id
        self.next: Optional[Self] = None
        self.previous: Optional[Self] = None
        self.resource: Optional[Self] = None

    def move_out(self):
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

    def move_in(self):
        if self.previous:
            previous = self.previous

            # right side
            previous.next = self.next
            if self.next:
                self.next.previous = previous
            elif self.resource:
                self.resource.tail = previous
            self.next = previous

            # left side
            self.previous = previous.previous
            if previous.previous:
                previous.previous.next = self
            elif self.resource:
                self.resource.head = self
            previous.previous = self

    def drop(self):
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

    def insert(self, task: Self):
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


T = TypeVar('T', bound='Task')


class Resource(Generic[T], TaskResource):
    def __init__(self, resource_id):
        self.resource_id = resource_id
        self.head: Optional[T] = None
        self.tail: Optional[T] = None

    def add_tail(self, task: T):
        task.resource = self
        task.next = None
        if self.tail:
            task.previous = self.tail
            self.tail.next = task
        self.tail = task
        if not self.head:
            self.head = task

    def add_head(self, task: T):
        task.resource = self
        task.previous = None
        if self.head:
            task.next = self.head
            self.head.previous = task
        self.head = task
        if not self.tail:
            self.tail = task

    def iter_tasks(self) -> Iterable[T]:
        t = self.head
        while t:
            yield t
            t = t.next

    def __str__(self):
        return f'{self.resource_id}[{", ".join([str(t) for t in self.iter_tasks()])}]'


class SchedulingTask(Task):
    def __init__(self, task_id: str, duration: int, target: int, min_margin_before: int = 0):
        super().__init__(task_id)

        self._duration = duration
        self._target = target

        self._dirty = True
        self._earliest_start = 0
        self._start = target
        self._min_margin_before = min_margin_before

    def __str__(self):
        if self._dirty:
            return (f"{self.task_id}[d={f'{self._min_margin_before}+' if self._min_margin_before != 0 else ''}"
                    f"{self._duration}, t={self._target}, s=...]")
        else:
            return (f"{self.task_id}[d={f'{self._min_margin_before}+' if self._min_margin_before != 0 else ''}"
                    f"{self._duration}, t={self._target}, s={self._start}]")

    @property
    def dirty(self):
        return self._dirty

    def invalidate(self):
        self._dirty = True
        t = self
        if t.next:
            t.next.invalidate()

    def calculate(self):
        print(f"{str(self)} calculating...")
        if self.previous and isinstance(self, SchedulingTask):
            self._earliest_start = self.previous.earliest_stop + self._min_margin_before
            self._start = max(self._earliest_start + self._min_margin_before, self._start)

        else:
            self._earliest_start = 0

        self._dirty = False

    @property
    def duration(self) -> int:
        return self._duration

    @property
    def min_margin_before(self) -> int:
        return self._min_margin_before

    @property
    def target(self) -> int:
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

    def move_out(self):
        super().move_out()
        self.invalidate()

    def move_in(self):
        super().move_in()
        self.invalidate()

    def insert(self, task: Self):
        super().insert(task)
        task.invalidate()

    def drop(self):
        self.invalidate()
        super().drop()


def schedule_forward(t: SchedulingTask) -> int:
    score = 0

    while t:
        if t.previous:
            t.start = max(t.previous.start + t.previous.duration + t.min_margin_before, t.start)
        score += max(0, t.start - t.target)
        t = t.next

    return score


def schedule_backward(t: SchedulingTask):
    while t:
        if t.next:
            t.start = min(t.target, t.next.start - t.next.min_margin_before - t.duration)
        else:
            t.start = t.target
        t = t.previous


def improvement_move_in(task: SchedulingTask, execute: bool = False) -> int:
    if not task.previous:
        return 0

    t1 = task.previous
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
        task.next.start = max(task.next.earliest_start - task.next.min_margin_before, min(task.target, task.start))
        task.start = max(task.earliest_start,
                         min(task.next.start - task.next.min_margin_before - task.duration, task.target))

    return t1_as + t2_as - t1_cs - t2_cs


class SchedulingResource(Resource[SchedulingTask]):

    def schedule(self):
        schedule_backward(self.tail)
        return schedule_forward(self.head)

    def improve(self):
        if self.tail is None:
            return 0

        improvement = 0

        t = self.tail
        while t:
            step_improvement = improvement_move_in(t, execute=True)
            if step_improvement < 0:
                improvement += step_improvement
            else:
                t = t.previous

        return improvement
