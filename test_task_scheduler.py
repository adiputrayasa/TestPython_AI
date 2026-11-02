import unittest
from datetime import date, datetime

from task_scheduler import (
    ActionStrategy,
    Scheduler,
    UserManager,
    ValidationError,
    build_default_executor,
)


def task(task_id: str, user: str = "alice", **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": task_id,
        "user": user,
        "time": "12:00",
        "action": "sync",
        "parameters": {"target": "/data/input"},
    }
    data.update(overrides)
    return data


class ExplodingAction(ActionStrategy):
    def execute(self, parameters: object) -> str:
        raise RuntimeError("simulated action failure")


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.users = UserManager()
        self.users.add_user("alice", 2)
        self.executor = build_default_executor()
        self.scheduler = Scheduler(self.users, self.executor)
        self.now = datetime(2026, 11, 2, 12, 0)

    def test_multiple_tasks_at_same_time_execute_independently(self) -> None:
        self.scheduler.add_task(task("one"))
        self.scheduler.add_task(task("two", action="backup"))

        results = self.scheduler.run_pending(self.now)

        self.assertEqual([result.status for result in results], ["success", "success"])
        self.assertEqual(self.users.get_usage("alice", date(2026, 11, 2)), 2)

    def test_daily_quota_skips_extra_task(self) -> None:
        for task_id in ("one", "two", "three"):
            self.scheduler.add_task(task(task_id))

        results = self.scheduler.run_pending(self.now)

        self.assertEqual(
            [result.status for result in results],
            ["success", "success", "quota_exceeded"],
        )

    def test_task_is_not_repeated_on_same_day_but_runs_next_day(self) -> None:
        self.scheduler.add_task(task("daily"))

        first = self.scheduler.run_pending(self.now)
        repeated = self.scheduler.run_pending(datetime(2026, 11, 2, 13, 0))
        next_day = self.scheduler.run_pending(datetime(2026, 11, 3, 12, 0))

        self.assertEqual(len(first), 1)
        self.assertEqual(repeated, [])
        self.assertEqual(len(next_day), 1)

    def test_future_task_is_not_run(self) -> None:
        self.scheduler.add_task(task("future", time="12:01"))
        self.assertEqual(self.scheduler.run_pending(self.now), [])

    def test_action_failure_is_logged_as_failed_without_stopping_scheduler(self) -> None:
        self.executor.register("explode", ExplodingAction())
        self.scheduler.add_task(task("bad", action="explode"))
        self.scheduler.add_task(task("good"))

        with self.assertLogs("task_scheduler", level="ERROR"):
            results = self.scheduler.run_pending(self.now)

        self.assertEqual([result.status for result in results], ["failed", "success"])

    def test_invalid_inputs_are_rejected(self) -> None:
        invalid_tasks = (
            task("bad-time", time="25:00"),
            task("bad-params", parameters="not-a-dict"),
            task("unknown-action", action="compress"),
            task("unknown-user", user="nobody"),
        )
        for invalid_task in invalid_tasks:
            with self.subTest(task_id=invalid_task["id"]):
                with self.assertRaises(ValidationError):
                    self.scheduler.add_task(invalid_task)

    def test_missing_target_fails_at_execution(self) -> None:
        self.scheduler.add_task(task("missing-target", parameters={}))
        result = self.scheduler.run_pending(self.now)
        self.assertEqual(result[0].status, "failed")
        self.assertIn("parameters.target", result[0].message)

    def test_zero_quota_user_cannot_execute(self) -> None:
        users = UserManager()
        users.add_user("zero", 0)
        scheduler = Scheduler(users, build_default_executor())
        scheduler.add_task(task("no-capacity", user="zero"))

        result = scheduler.run_pending(self.now)

        self.assertEqual(result[0].status, "quota_exceeded")
        self.assertEqual(users.get_usage("zero", self.now.date()), 0)

    def test_invalid_user_quota_is_rejected(self) -> None:
        for quota in (-1, 1.5, True):
            with self.subTest(quota=quota):
                with self.assertRaises(ValidationError):
                    UserManager().add_user("user", quota)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
