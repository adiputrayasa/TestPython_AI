# Simulated Strategy-Based Task Scheduler

This project is implemented in Python 3 without external dependencies. It accepts
daily tasks, executes simulated action strategies, and limits the number of task
executions allowed for each user per day.

## Features

- Daily task scheduling using `HH:MM` time values
- Per-user daily execution quotas
- Multiple tasks for the same user and scheduled time
- Dictionary-based task configuration and input validation
- Extensible action strategies (`sync`, `backup`, and `delete`)
- Execution, warning, and error logging using Python's `logging` module
- Isolated task failures so one failed task does not stop other tasks
- Unit tests covering normal, invalid, and edge cases

All actions are simulated. The project does not modify, copy, or delete real
files.

## Requirements

- Git
- Python 3.10 or newer

No framework or third-party package is required.

Verify the Python installation:

```bash
python --version
```

On Windows, use the Python launcher if the `python` command is unavailable:

```bash
py --version
```

## Installation

Clone the repository and enter the project directory:

```bash
git clone https://github.com/adiputrayasa/TestPython_AI.git
cd TestPython_AI
```

There is no dependency installation step because the project only uses the
Python standard library.

## Running the Demo

```bash
python task_scheduler.py
```

On Windows, the equivalent command is:

```bash
py task_scheduler.py
```

The demo creates two users and three tasks scheduled for `12:00`. If the program
is run before `12:00`, the tasks are not due yet and therefore are not executed.
Once due, an execution result looks like this:

```text
task-1: success - Simulated sync on /data/x
task-2: success - Simulated backup on /srv/y
task-3: success - Simulated delete on /tmp/z
```

## Running the Tests

```bash
python -m unittest -v
```

On Windows:

```bash
py -m unittest -v
```

Expected summary:

```text
Ran 9 tests

OK
```

Some tests intentionally log quota warnings and an action failure. These log
messages are expected; the test suite is successful when the final result is
`OK`.

## Task Configuration

Tasks are submitted as dictionaries with the following structure:

```python
{
    "id": "task-1",
    "user": "alice",
    "time": "12:00",
    "action": "sync",
    "parameters": {"target": "/data/x"},
}
```

Required fields:

| Field | Type | Description |
| --- | --- | --- |
| `id` | `str` | Unique task identifier |
| `user` | `str` | ID of a registered user |
| `time` | `str` | Daily execution time in `HH:MM` format |
| `action` | `str` | Registered action name |
| `parameters` | `dict` | Action-specific configuration |

The built-in actions require a non-empty `parameters.target` value.

## Basic Usage

```python
from task_scheduler import Scheduler, UserManager, build_default_executor

users = UserManager()
users.add_user("alice", daily_quota=3)

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

results = scheduler.run_pending()
for result in results:
    print(result.task_id, result.status, result.message)
```

`run_pending()` can be called periodically. A task whose scheduled time has been
reached is attempted at most once per day. Quota usage is tracked separately for
each user and date.

## Project Structure

```text
TestPython_AI/
|-- task_scheduler.py       # Models, quota management, actions, and scheduler
|-- test_task_scheduler.py  # Unit tests
|-- README.md               # Setup and usage documentation
`-- .gitignore              # Files excluded from Git
```

## Design Overview

- `UserManager` registers users and manages daily quota usage.
- `Task` validates dictionary input and represents a scheduled task.
- `ActionStrategy` defines the interface for extensible task actions.
- `TaskExecutor` resolves an action and records traceable logs.
- `Scheduler` selects due tasks, applies quotas, and isolates execution errors.

`run_pending()` scans the registered tasks once, giving it `O(n)` time complexity
for `n` tasks. Dictionary lookups for users, actions, and task IDs are `O(1)` on
average.
