import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


TASKS_DIR = Path(".data/tasks")


def now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def task_output_dir(task_id: str) -> Path:
    return Path.cwd() / "output" / task_id


def write_task(task: dict[str, Any]) -> dict[str, Any]:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    path = task_path(task["id"])
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", "utf-8")
    tmp_path.replace(path)
    return task


def add_task(viral_video: str, source_movie: str, output_dir: str | None = None) -> dict[str, str]:
    task_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
    task = {
        "id": task_id,
        "status": "pending",
        "current_step": "等待执行",
        "viral_video": viral_video,
        "source_movie": source_movie,
        "output_dir": output_dir or str(task_output_dir(task_id)),
        "created_at": now(),
        "updated_at": now(),
        "error": "",
        "result": {},
    }
    return write_task(task)


def list_tasks() -> list[dict[str, Any]]:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = []
    for path in TASKS_DIR.glob("*.json"):
        try:
            text = path.read_text("utf-8").strip()
            if text:
                tasks.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return sorted(tasks, key=lambda task: task.get("created_at", ""), reverse=True)


def update_task(task_id: str, **changes) -> dict[str, Any]:
    task = json.loads(task_path(task_id).read_text("utf-8"))
    task.update(changes)
    task["updated_at"] = now()
    return write_task(task)


def retry_task(task_id: str) -> dict[str, Any]:
    task = json.loads(task_path(task_id).read_text("utf-8"))
    if task.get("status") == "done":
        shutil.rmtree(task_output_dir(task_id), ignore_errors=True)
    return update_task(task_id, status="pending", current_step="等待执行", output_dir=str(task_output_dir(task_id)), error="", result={})


def delete_task(task_id: str) -> None:
    path = task_path(task_id)
    if path.exists():
        path.unlink()


def pause_active_tasks() -> None:
    for task in list_tasks():
        if task.get("status") in {"pending", "running"}:
            update_task(task["id"], status="paused", current_step="已暂停")


def resume_paused_tasks() -> None:
    for task in list_tasks():
        if task.get("status") == "paused":
            update_task(task["id"], status="pending", current_step="等待执行")


def claim_next_pending() -> dict[str, Any] | None:
    pending = [task for task in list_tasks() if task.get("status") == "pending"]
    if not pending:
        return None
    task = sorted(pending, key=lambda item: item.get("created_at", ""))[0]
    return update_task(task["id"], status="running", current_step="开始执行", output_dir=str(task_output_dir(task["id"])), error="")
