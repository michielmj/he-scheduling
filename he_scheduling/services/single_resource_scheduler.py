from typing import TypeVar, Generic, Optional, Iterable, Self
from uuid import uuid4


class TaskResource:
    pass


class Task:

    def __init__(self, task_id: str):

        self.task_id: str = task_id
        self.next: Optional[Self] = None
        self.previous: Optional[Self] = None
        self.resource: Optional[TaskResource] = None

        self.__branch__ = b''

    def move_out(self):

        if self.next:

            nxt = self.next_in_branch

            # left side
            nxt.previous = self.previous
            if self.previous_in_branch:  # creates previous in branch if necessary
                self.previous.next = nxt
            elif self.resource and self.__branch__ == b'':
                self.resource.head = nxt
            self.previous = nxt

            # right side
            self.next = nxt.next_in_branch  # creates next in branch if necessary
            if nxt.next:
                nxt.next.previous = self
            elif self.resource and self.__branch__ == b'':
                self.resource.tail = self
            nxt.next = self

    def move_in(self):

        if self.previous:

            previous = self.previous_in_branch

            # right side
            previous.next = self.next
            if self.next_in_branch:  # creates next in branch if necessary
                self.next.previous = previous
            elif self.resource and self.__branch__ == b'':
                self.resource.tail = previous
            self.next = previous

            # left side
            self.previous = previous.previous_in_branch  # creates previous in branch if necessary
            if previous.previous:
                previous.previous.next = self
            elif self.resource and self.__branch__ == b'':
                self.resource.head = self
            previous.previous = self

    def drop(self):

        if self.previous and self.previous.__branch__ == self.__branch__:
            self.previous.next = self.next
        elif self.resource and self.__branch__ == b'':
            self.resource.head = self.next

        if self.next and self.next.__branch__ == self.__branch__:
            self.next.previous = self.previous
        elif self.resource and self.__branch__ == b'':
            self.resource.tail = self.previous

        self.previous = None
        self.next = None
        self.resource = None

    def insert(self, task: Self):
        # remove from existing resource
        task.drop()
        task.resource = self.resource
        task.__branch__ = self.__branch__
        if self.previous_in_branch:
            self.previous.next = task
        elif self.resource and self.__branch__ == b'':
            self.resource.head = task

        task.next = self
        task.previous = self.previous_in_branch
        self.previous = task

    def __str__(self):
        return self.task_id if self.__branch__ == b'' else f"{self.task_id}'"

    def branch(self):
        return self._copy_with_branch(uuid4().bytes)

    def _copy_with_branch(self, branch: bytes):
        task = object.__new__(SchedulingTask)
        task.__dict__ = self.__dict__.copy()

        task.__branch__ = branch

        return task

    @property
    def next_in_branch(self):

        if self.next and self.next.__branch__ != self.__branch__:
            self.next = self.next._copy_with_branch(self.__branch__)

        return self.next

    @property
    def previous_in_branch(self):

        if self.previous and self.previous.__branch__ != self.__branch__:
            self.previous = self.previous._copy_with_branch(self.__branch__)

        return self.previous

    def merge(self):
        if self.__branch__ == b'':
            return
        elif self.resource is None:
            raise AttributeError('Task not assigned to a resource.')

        # reset branch
        self.__branch__ = b''

        # find branch tail
        branch_tail = self
        link_tail = self.next
        while link_tail and link_tail.__branch__ != b'':
            branch_tail = link_tail
            branch_tail.__branch__ = b''
            link_tail = link_tail.next

        # find branch head
        branch_head = self
        link_head = self.previous
        while link_head and link_head.__branch__ != b'':
            branch_head = link_head
            branch_head.__branch__ = b''
            link_head = link_head.previous

        if link_head is None:
            self.resource.head = branch_head
        else:
            link_head.next = branch_head

        if link_tail is None:
            self.resource.tail = branch_tail
        else:
            link_tail.previous = branch_tail


T = TypeVar('T', bound='Task')


def iter_tasks(head: T):
    t = head
    while t:
        yield t
        t = t.next


def task_string(head: T) -> str:
    return f'[{", ".join([str(t) for t in iter_tasks(head)])}]'


def branch_head(task: T) -> T:
    h = task
    while h.previous and h.previous.__branch__ == task.__branch__:
        h = h.previous

    return h


def branch_tail(task: T) -> T:
    t = task
    while t.next and t.next.__branch__ == task.__branch__:
        t = t.next

    return t


class Resource(Generic[T], TaskResource):
    def __init__(self, resource_id):
        self.resource_id = resource_id
        self.head: Optional[T] = None
        self.tail: Optional[T] = None

    def add_tail(self, task: T):
        if task.__branch__ != b'':
            raise AttributeError('Branched tasks cannot be added as tail to a resource.')

        task.resource = self
        task.next = None
        if self.tail:
            task.previous = self.tail
            self.tail.next = task
        self.tail = task
        if not self.head:
            self.head = task

    def add_head(self, task: T):
        if task.__branch__ != b'':
            raise AttributeError('Branched tasks cannot be added as head to a resource.')

        task.resource = self
        task.previous = None
        if self.head:
            task.next = self.head
            self.head.previous = task
        self.head = task
        if not self.tail:
            self.tail = task

    def iter_tasks(self) -> Iterable[T]:
        return iter_tasks(self.head)

    def __str__(self):
        return f'{self.resource_id}[{", ".join([str(t) for t in self.iter_tasks()])}]'


class SchedulingTask(Task):
    def __init__(self, task_id: str, duration: int, target: int, min_margin_before: int = 0):
        super(SchedulingTask, self).__init__(task_id)

        self._duration = duration
        self._target = target

        self._dirty = True
        self._dirty_start = True
        self._earliest_start = 0
        self._start = target
        self._min_margin_before = min_margin_before

    def __str__(self):
        if self._dirty_start:
            return (
                f"{super(SchedulingTask, self).__str__()}"
                f"[d={f'{self._min_margin_before}+' if self._min_margin_before != 0 else ''}"
                f"{self._duration}, t={self._target}, s=...]")
        else:
            return (
                f"{super(SchedulingTask, self).__str__()}"
                f"[d={f'{self._min_margin_before}+' if self._min_margin_before != 0 else ''}"
                f"{self._duration}, t={self._target}, s={self._start}]")

    @property
    def dirty(self):
        return self._dirty

    def invalidate(self):
        self._dirty = True
        if self.next and self.next.__branch__ == self.__branch__:
            self.next.invalidate()

        self.invalidate_start()

    def invalidate_start(self, next_needed: int = None):
        self._dirty_start = True
        if next_needed is None:
            if self.previous and self.previous.__branch__ == self.__branch__:
                self.previous.invalidate_start()

        else:
            # Direct calculation to determine if propagation is needed
            print(f"{str(self)} calculating start...")
            new_start = max(self.earliest_start, min(self._target, next_needed - self.duration))
            if new_start != self._start:
                self._start = new_start
                if self.previous and self.previous.__branch__ == self.__branch__:
                    self.previous.invalidate_start(next_needed=new_start - self._min_margin_before)

            self._dirty_start = False

    def calculate(self):
        print(f"{str(self)} calculating...")
        if self.previous:
            self._earliest_start = self.previous.earliest_stop + self._min_margin_before
        else:
            self._earliest_start = 0

        self._dirty = False

    def calculate_start(self):
        print(f"{str(self)} calculating start...")
        if self.next:
            self._start = max(self.earliest_start,
                              min(self._target, self.next.start - self.next.min_margin_before - self.duration))
        else:
            self._start = max(self.earliest_start, self._target)

        self._dirty_start = False

    @property
    def duration(self) -> int:
        return self._duration

    @property
    def min_margin_before(self) -> int:
        return self._min_margin_before

    @property
    def target(self) -> int:
        return self._target

    @target.setter
    def target(self, value: int):
        self._target = value
        self.invalidate_start(
            next_needed=value + self.duration if self.next is None else self.next.start - self.next.min_margin_before)

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
        if self._dirty_start:
            self.calculate_start()

        return self._start

    @property
    def slack(self) -> float:
        """
        Amount of time before this task that can be utilized without moving this task later.
        To be used to identify possible locations for inserting a new task.
        """
        return self.start - self.earliest_start

    @property
    def lateness(self) -> float:
        """
        Amount of time that the task starts late (positive, after target) or early (negative, before target).
        To be used to identify tasks that may be moved to another resource.
        """
        return self.start - self.target

    def move_out(self):
        super(SchedulingTask, self).move_out()
        self.invalidate()

    def move_in(self):
        super(SchedulingTask, self).move_in()
        self.invalidate()

    def insert(self, task: Self):
        super(SchedulingTask, self).insert(task)
        task.invalidate()

    def drop(self):
        self.invalidate()
        super(SchedulingTask, self).drop()

    def merge(self):
        super(SchedulingTask, self).merge()
        self.invalidate()


def improvement_move_in(task: SchedulingTask, dry_run: bool = True) -> int:
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
    if not dry_run and improvement < 0:
        task.move_in()

    return t1_as + t2_as - t1_cs - t2_cs


def score(task: SchedulingTask):
    s = 0
    t = task
    while t:
        s += max(0, t.start - t.target)
        t = t.next

    t = task.previous
    while t:
        s += max(0, t.start - t.target)
        t = t.previous

    return s


class SchedulingResource(Resource[SchedulingTask]):

    def improve(self, branch: bool = False):
        if self.tail is None:
            return 0

        improvement = 0

        t = self.tail
        head = None
        if t and branch:
            t = t.branch()

        while t:
            head = t
            step_improvement = improvement_move_in(t, dry_run=False)
            if step_improvement < 0:
                improvement += step_improvement
                print(f'move before {t.next.task_id}.')
            else:
                t = t.previous_in_branch
                print('')

        if branch:
            return improvement, head
        else:
            return improvement

    def find_after(self, after: int) -> Optional[SchedulingTask]:

        task = self.tail
        nxt = None
        while task and task.start > after:
            nxt = task
            task = task.previous

        return nxt

    def find_slack(self, after: int, amount: int) -> Optional[SchedulingTask]:
        t = self.find_after(after)

        while t and t.slack < amount:
            t = t.next

        return t

    def insert_best(self, task: SchedulingTask, branch: bool = False):
        nxt = self.find_slack(task.target, task.min_margin_before + task.duration)
        while nxt and nxt.target <= task.target:
            nxt = nxt.next

        if nxt:
            if branch:
                nxt = nxt.branch()

            nxt.insert(task)

            # try improvement by moving next in
            while improvement_move_in(nxt, dry_run=False) < 0:
                pass
        elif branch:
            task.__branch__ = uuid4().bytes
            task.previous = self.tail
            task.invalidate()
        else:
            self.add_tail(task)

    def score(self) -> int:
        return score(self.head)
