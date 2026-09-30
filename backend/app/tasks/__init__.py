"""Task dispatch + in-process runner + progress hub (POC).

Production: dispatch writes to Redis Stream and a Worker process consumes it
(see docs/架构设计.md §3, §7). The runner interface (run_task) is unchanged.
"""
from app.tasks.dispatch import create_task, dispatch
from app.tasks.progress import latest, publish, subscribe
from app.tasks.runner import run_task

__all__ = ["create_task", "dispatch", "run_task", "publish", "latest", "subscribe"]
