import json

from app.tasks import (
    add_task,
    claim_next_pending,
    delete_task,
    list_tasks,
    pause_active_tasks,
    resume_paused_tasks,
    retry_task,
    task_output_dir,
    update_task,
)


def test_add_task_writes_pending_task_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    task = add_task("viral.mp4", "movie.mkv")

    path = tmp_path / ".data" / "tasks" / f"{task['id']}.json"
    saved = json.loads(path.read_text("utf-8"))
    assert saved["status"] == "pending"
    assert saved["viral_video"] == "viral.mp4"
    assert saved["source_movie"] == "movie.mkv"
    assert saved["output_dir"] == str(task_output_dir(task["id"]))
    assert saved["current_step"] == "等待执行"


def test_task_queue_claims_and_updates_one_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = add_task("a.mp4", "a.mkv")
    add_task("b.mp4", "b.mkv")

    claimed = claim_next_pending()
    update_task(claimed["id"], status="done", current_step="完成", result={"final_video": "final.mp4"})

    tasks = {task["id"]: task for task in list_tasks()}
    assert claimed["id"] == first["id"]
    assert tasks[first["id"]]["status"] == "done"
    assert tasks[first["id"]]["result"]["final_video"] == "final.mp4"
    assert any(task["status"] == "pending" for task in tasks.values())


def test_list_tasks_ignores_empty_or_invalid_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = add_task("viral.mp4", "movie.mkv")
    (tmp_path / ".data" / "tasks" / "empty.json").write_text("", "utf-8")
    (tmp_path / ".data" / "tasks" / "bad.json").write_text("{", "utf-8")

    tasks = list_tasks()

    assert [item["id"] for item in tasks] == [task["id"]]


def test_retry_and_delete_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = add_task("viral.mp4", "movie.mkv", "old")
    update_task(task["id"], status="failed", current_step="失败", error="boom")
    task_output_dir(task["id"]).mkdir(parents=True)
    (task_output_dir(task["id"]) / "keep.txt").write_text("partial", "utf-8")

    retried = retry_task(task["id"])
    assert retried["status"] == "pending"
    assert retried["current_step"] == "等待执行"
    assert retried["output_dir"] == str(task_output_dir(task["id"]))
    assert retried["error"] == ""
    assert (task_output_dir(task["id"]) / "keep.txt").exists()

    delete_task(task["id"])
    assert list_tasks() == []


def test_retry_done_task_removes_previous_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = add_task("viral.mp4", "movie.mkv")
    update_task(task["id"], status="done", current_step="完成", result={"final_video": "old.mp4"})
    task_output_dir(task["id"]).mkdir(parents=True)
    (task_output_dir(task["id"]) / "old.txt").write_text("old", "utf-8")

    retried = retry_task(task["id"])

    assert retried["status"] == "pending"
    assert not (task_output_dir(task["id"]) / "old.txt").exists()


def test_pause_and_resume_active_tasks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pending = add_task("pending.mp4", "movie.mkv")
    running = add_task("running.mp4", "movie.mkv")
    failed = add_task("failed.mp4", "movie.mkv")
    done = add_task("done.mp4", "movie.mkv")
    update_task(running["id"], status="running", current_step="镜头匹配")
    update_task(failed["id"], status="failed", current_step="失败")
    update_task(done["id"], status="done", current_step="完成")

    pause_active_tasks()
    tasks = {task["id"]: task for task in list_tasks()}
    assert tasks[pending["id"]]["status"] == "paused"
    assert tasks[running["id"]]["status"] == "paused"
    assert tasks[failed["id"]]["status"] == "failed"
    assert tasks[done["id"]]["status"] == "done"

    resume_paused_tasks()
    tasks = {task["id"]: task for task in list_tasks()}
    assert tasks[pending["id"]]["status"] == "pending"
    assert tasks[running["id"]]["status"] == "pending"


def test_claim_next_pending_normalizes_output_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = add_task("viral.mp4", "movie.mkv", "old")

    claimed = claim_next_pending()

    assert claimed["id"] == task["id"]
    assert claimed["output_dir"] == str(task_output_dir(task["id"]))
