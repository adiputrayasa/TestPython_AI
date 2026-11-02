"""Simulated daily task scheduler with per-user execution quotas."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Callable, Mapping


class SchedulerError(Exception):
    """Base exception for errors that callers may want to handle."""


class ValidationError(SchedulerError, ValueError):
    """Raised when user or task input is invalid."""


class QuotaExceededError(SchedulerError):
    """Raised when a user has no execution quota left for a date."""


@dataclass
class UserQuota:
    user_id: str
    daily_limit: int
    usage_by_date: dict[date, int] = field(default_factory=dict)


class UserManager:
    """Registers users and owns all daily quota calculations."""

    def __init__(self) -> None:
        self._users: dict[str, UserQuota] = {}

    def add_user(self, user_id: str, daily_quota: int) -> None:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValidationError("user_id must be a non-empty string")
        if isinstance(daily_quota, bool) or not isinstance(daily_quota, int):
            raise ValidationError("daily_quota must be an integer")
        if daily_quota < 0:
            raise ValidationError("daily_quota cannot be negative")

        normalized_id = user_id.strip()
        if normalized_id in self._users:
            raise ValidationError(f"user '{normalized_id}' already exists")
        self._users[normalized_id] = UserQuota(normalized_id, daily_quota)

    def has_user(self, user_id: str) -> bool:
        return user_id in self._users

    def consume_quota(self, user_id: str, execution_date: date) -> int:
        user = self._get_user(user_id)
        used = user.usage_by_date.get(execution_date, 0)
        if used >= user.daily_limit:
            raise QuotaExceededError(
                f"user '{user_id}' exceeded daily quota of {user.daily_limit}"
            )

        new_usage = used + 1
        user.usage_by_date[execution_date] = new_usage
        return new_usage

    def get_usage(self, user_id: str, execution_date: date) -> int:
        return self._get_user(user_id).usage_by_date.get(execution_date, 0)

    def _get_user(self, user_id: str) -> UserQuota:
        try:
            return self._users[user_id]
        except KeyError as exc:
            raise ValidationError(f"unknown user '{user_id}'") from exc


@dataclass
class Task:
    task_id: str
    user_id: str
    scheduled_time: time
    action: str
    parameters: dict[str, Any]
    last_attempt_date: date | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Task":
        if not isinstance(data, Mapping):
            raise ValidationError("task must be a dictionary-like object")

        required = ("id", "user", "time", "action", "parameters")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValidationError(f"missing task fields: {', '.join(missing)}")

        task_id = cls._non_empty_string(data["id"], "id")
        user_id = cls._non_empty_string(data["user"], "user")
        action = cls._non_empty_string(data["action"], "action").lower()

        raw_parameters = data["parameters"]
        if not isinstance(raw_parameters, dict):
            raise ValidationError("parameters must be a dictionary")

        raw_time = data["time"]
        if not isinstance(raw_time, str):
            raise ValidationError("time must be a string in HH:MM format")
        try:
            scheduled_time = datetime.strptime(raw_time, "%H:%M").time()
        except ValueError as exc:
            raise ValidationError("time must be a valid HH:MM value") from exc

        return cls(task_id, user_id, scheduled_time, action, dict(raw_parameters))

    @staticmethod
    def _non_empty_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{field_name} must be a non-empty string")
        return value.strip()


class ActionStrategy(ABC):
    """Extension point for a task action."""

    @abstractmethod
    def execute(self, parameters: Mapping[str, Any]) -> str:
        """Execute an action and return a human-readable result."""

    @staticmethod
    def require_target(parameters: Mapping[str, Any]) -> str:
        target = parameters.get("target")
        if not isinstance(target, str) or not target.strip():
            raise ValidationError("parameters.target must be a non-empty string")
        return target.strip()


class SyncAction(ActionStrategy):
    def execute(self, parameters: Mapping[str, Any]) -> str:
        target = self.require_target(parameters)
        return f"Simulated sync on {target}"


class BackupAction(ActionStrategy):
    def execute(self, parameters: Mapping[str, Any]) -> str:
        target = self.require_target(parameters)
        return f"Simulated backup on {target}"


class DeleteAction(ActionStrategy):
    def execute(self, parameters: Mapping[str, Any]) -> str:
        target = self.require_target(parameters)
        return f"Simulated delete on {target}"


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    status: str
    message: str


class TaskExecutor:
    """Resolves actions and runs them with traceable logging."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._strategies: dict[str, ActionStrategy] = {}
        self._logger = logger or logging.getLogger(__name__)

    def register(self, action: str, strategy: ActionStrategy) -> None:
        if not isinstance(action, str) or not action.strip():
            raise ValidationError("action name must be a non-empty string")
        if not isinstance(strategy, ActionStrategy):
            raise ValidationError("strategy must implement ActionStrategy")
        self._strategies[action.strip().lower()] = strategy

    def supports(self, action: str) -> bool:
        return action in self._strategies

    def execute(self, task: Task) -> str:
        strategy = self._strategies.get(task.action)
        if strategy is None:
            raise ValidationError(f"unsupported action '{task.action}'")

        self._logger.info(
            "Executing task_id=%s user=%s action=%s parameters=%s",
            task.task_id,
            task.user_id,
            task.action,
            task.parameters,
        )
        message = strategy.execute(task.parameters)
        self._logger.info("Completed task_id=%s result=%s", task.task_id, message)
        return message


class Scheduler:
    """Stores daily tasks and executes tasks that are due."""

    def __init__(
        self,
        users: UserManager,
        executor: TaskExecutor,
        logger: logging.Logger | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._users = users
        self._executor = executor
        self._logger = logger or logging.getLogger(__name__)
        self._clock = clock
        self._tasks: dict[str, Task] = {}

    def add_task(self, task_data: Mapping[str, Any]) -> Task:
        task = Task.from_dict(task_data)
        if task.task_id in self._tasks:
            raise ValidationError(f"task id '{task.task_id}' already exists")
        if not self._users.has_user(task.user_id):
            raise ValidationError(f"unknown user '{task.user_id}'")
        if not self._executor.supports(task.action):
            raise ValidationError(f"unsupported action '{task.action}'")

        self._tasks[task.task_id] = task
        self._logger.info(
            "Scheduled task_id=%s user=%s time=%s action=%s",
            task.task_id,
            task.user_id,
            task.scheduled_time.strftime("%H:%M"),
            task.action,
        )
        return task

    def run_pending(self, now: datetime | None = None) -> list[ExecutionResult]:
        current = now or self._clock()
        results: list[ExecutionResult] = []

        for task in self._tasks.values():
            if task.last_attempt_date == current.date():
                continue
            if task.scheduled_time > current.time():
                continue

            task.last_attempt_date = current.date()
            try:
                self._users.consume_quota(task.user_id, current.date())
                message = self._executor.execute(task)
                results.append(ExecutionResult(task.task_id, "success", message))
            except QuotaExceededError as exc:
                self._logger.warning("Skipped task_id=%s reason=%s", task.task_id, exc)
                results.append(ExecutionResult(task.task_id, "quota_exceeded", str(exc)))
            except Exception as exc:
                self._logger.exception("Failed task_id=%s", task.task_id)
                results.append(ExecutionResult(task.task_id, "failed", str(exc)))

        return results


def build_default_executor(logger: logging.Logger | None = None) -> TaskExecutor:
    executor = TaskExecutor(logger)
    executor.register("sync", SyncAction())
    executor.register("backup", BackupAction())
    executor.register("delete", DeleteAction())
    return executor


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    users = UserManager()
    users.add_user("alice", daily_quota=3)
    users.add_user("bob", daily_quota=5)

    scheduler = Scheduler(users, build_default_executor())
    scheduler.add_task(
        {
            "id": "task-1",
            "user": "alice",
            "time": "12:00",
            "action": "sync",
            "parameters": {"target": "/data/x"},
        }
    )
    scheduler.add_task(
        {
            "id": "task-2",
            "user": "bob",
            "time": "12:00",
            "action": "backup",
            "parameters": {"target": "/srv/y"},
        }
    )
    scheduler.add_task(
        {
            "id": "task-3",
            "user": "alice",
            "time": "12:00",
            "action": "delete",
            "parameters": {"target": "/tmp/z", "dry_run": True},
        }
    )

    for result in scheduler.run_pending():
        print(f"{result.task_id}: {result.status} - {result.message}")


if __name__ == "__main__":
    main()
