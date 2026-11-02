# Simulated Strategy-Based Task Scheduler

This project is implemented in Python 3 without external dependencies. It accepts
daily tasks, executes simulated action strategies, and limits the number of task
executions allowed for each user per day.

## Running the Demo

```powershell
python task_scheduler.py
```

## Running the Tests

```powershell
python -m unittest -v
```

Tasks are configured using dictionaries with the following structure:

```python
{
    "id": "task-1",
    "user": "alice",
    "time": "12:00",
    "action": "sync",
    "parameters": {"target": "/data/x"},
}
```

`run_pending()` can be called periodically. A task whose scheduled time has been
reached is executed at most once per day. User quota usage is tracked separately
for each date.
