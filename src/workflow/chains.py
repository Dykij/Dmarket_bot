"""
Workflow Chains — асинхронные пайплайны (Conductor pattern) для OpenCode.
Инкапсулирует логику: Parser -> Coder -> Tester.
Использует asyncio.Queue + TaskGroup для исключения блокировки GIL.
"""

from __future__ import annotations

import asyncio
import enum
import time
import traceback
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


class AgentRole(str, enum.Enum):
    PARSER = "parser"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    ROLLED_BACK = "rolled_back"


@dataclass
class AgentTask:
    id: str
    role: AgentRole
    payload: dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    depends_on: list[str] = field(default_factory=list)


class TaskRegistry:
    """In-memory DAG for task dependencies and state."""

    def __init__(self):
        self._tasks: dict[str, AgentTask] = {}
        self._dependencies: dict[str, list[str]] = {}

    def add(self, task: AgentTask) -> None:
        self._tasks[task.id] = task
        self._dependencies[task.id] = list(task.depends_on)

    def get(self, task_id: str) -> AgentTask:
        return self._tasks[task_id]

    def is_ready(self, task_id: str) -> bool:
        deps = self._dependencies.get(task_id, [])
        return all(self._tasks[d].status == TaskStatus.SUCCESS for d in deps)

    def all_complete(self) -> bool:
        return all(t.status in {TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.ROLLED_BACK} for t in self._tasks.values())

    def reset_all(self) -> None:
        for t in self._tasks.values():
            t.status = TaskStatus.PENDING
            t.result = None
            t.error = None


class WorkItem:
    """Unit of work passed between agents in the queue."""

    def __init__(self, task: AgentTask, callback: Callable[[AgentTask], Awaitable[None]] | None = None, future: asyncio.Future | None = None):
        self.task = task
        self.callback = callback
        self.future: asyncio.Future = future if future is not None else asyncio.get_event_loop().create_future()


class Conductor:
    """
    Orchestrates workflow via asyncio.Queue + TaskGroup.
    Each agent role has its own worker pool size (default 1).
    """

    def __init__(self, max_workers_per_role: dict[AgentRole, int] | None = None):
        self.queues: dict[AgentRole, asyncio.Queue[WorkItem]] = {}
        self.workers: list[asyncio.Task] = []
        self.registry = TaskRegistry()
        self._handlers: dict[AgentRole, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]] = {}
        self.max_workers = max_workers_per_role or {}

    def register_handler(self, role: AgentRole, handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]) -> None:
        self._handlers[role] = handler

    def submit(self, task: AgentTask, callback: Callable[[AgentTask], Awaitable[None]] | None = None) -> asyncio.Future:
        if task.role not in self._handlers:
            raise ValueError(f"No handler registered for role {task.role}")
        if task.role not in self.queues:
            self.queues[task.role] = asyncio.Queue()
        self.registry.add(task)
        item = WorkItem(task, callback)
        asyncio.create_task(self._enqueue_when_ready(item))
        return item.future

    async def _enqueue_when_ready(self, item: WorkItem) -> None:
        while not self.registry.is_ready(item.task.id):
            await asyncio.sleep(0.01)
        queue = self.queues[item.task.role]
        await queue.put(item)

    async def _worker(self, role: AgentRole, queue: asyncio.Queue) -> None:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if not self.workers:
                    break
                continue
            if item is None:
                queue.task_done()
                return  # Graceful exit for this worker
            task = item.task
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            try:
                handler = self._handlers[role]
                result = await handler(task.payload)
                task.result = result
                task.status = TaskStatus.SUCCESS
            except Exception:
                task.status = TaskStatus.FAILURE
                task.error = traceback.format_exc()
            task.finished_at = time.time()
            if item.callback:
                await item.callback(task)
            if not item.future.done():
                item.future.set_result(task)
            queue.task_done()

    async def start(self) -> None:
        for role, queue in self.queues.items():
            num_workers = self.max_workers.get(role, 1)
            for _ in range(num_workers):
                self.workers.append(asyncio.create_task(self._worker(role, queue)))

    async def shutdown(self) -> None:
        # Send sentinel to each worker
        for queue in self.queues.values():
            for _ in range(self.max_workers.get(next(iter(self.queues)), 1)):
                await queue.put(None)
        # Wait for workers (not join, to avoid deadlock with sentinel processing)
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()


# ── Example DSL / Builder ──

class WorkflowBuilder:
    """Fluent API for building workflow chains."""

    def __init__(self):
        self.conductor = Conductor()
        self._tasks: list[AgentTask] = []

    def add_step(self, role: AgentRole, payload: dict[str, Any], depends_on: list[str] | None = None) -> str:
        task_id = f"{role.value}_{uuid.uuid4().hex[:8]}"
        task = AgentTask(
            id=task_id,
            role=role,
            payload=payload,
            depends_on=depends_on or [],
        )
        self._tasks.append(task)
        return task_id

    def register_handler(self, role: AgentRole, handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]) -> WorkflowBuilder:
        self.conductor.register_handler(role, handler)
        return self

    async def run(self) -> list[AgentTask]:
        futures = []
        for task in self._tasks:
            fut = self.conductor.submit(task)
            futures.append(fut)
        await self.conductor.start()
        # Wait until all tasks are processed
        while not self.conductor.registry.all_complete():
            await asyncio.sleep(0.01)
        await self.conductor.shutdown()
        return self._tasks
