import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.settings import load_settings
from app.tasks import claim_next_pending, update_task
from app.workflow import HotCopyInputs, run_pipeline


class TaskRunner:
    def __init__(self, logger: logging.Logger, interval: float = 3.0):
        self.logger = logger
        self.interval = interval
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.future = None

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)
        self.executor.shutdown(wait=False, cancel_futures=False)

    def _loop(self) -> None:
        self.logger.info("task runner started, workers=1")
        while not self.stop_event.is_set():
            if self.future is None or self.future.done():
                self.future = self.executor.submit(self.process_next)
            self.stop_event.wait(self.interval)

    def process_next(self) -> None:
        task = claim_next_pending()
        if not task:
            return
        self.logger.info("task started: %s", task["id"])
        try:
            settings = load_settings()
            def progress(step: str) -> None:
                update_task(task["id"], current_step=step)
                self.logger.info("task %s: %s", task["id"], step)

            result = run_pipeline(
                HotCopyInputs(task["viral_video"], task["source_movie"], task["output_dir"]),
                settings,
                progress,
            )
            update_task(task["id"], status="done", current_step="完成", result=result, error="")
            self.logger.info("task done: %s", task["id"])
        except Exception as exc:
            update_task(task["id"], status="failed", current_step="失败", error=str(exc))
            self.logger.exception("task failed: %s", task["id"])
