"""
Background Task Queue Manager for Blender
Executes queued tasks sequentially with a configurable global delay.
Automatically saves .blend snapshots and rendered images after task completion.
Zero external dependencies.
"""

import time
import threading
from typing import Dict, Any, Optional

import session_manager
from blender_bridge import bridge


class TaskQueueWorker:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_paused = False
        self.active_task: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()

    def _get_mgr(self):
        mgr = session_manager.session_mgr
        if not hasattr(mgr, "list_queue_tasks"):
            try:
                import importlib
                importlib.reload(session_manager)
                mgr = session_manager.session_mgr
            except Exception:
                pass
        return mgr

    def start(self):
        """Starts the background queue processor."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BlenderTaskQueueWorker")
            self._thread.start()

    def stop(self):
        """Stops the worker thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            mgr = self._get_mgr()
            settings = mgr.get_all_settings()
            delay = float(settings.get("queue_delay_seconds", 2.0))
            tasks = mgr.list_queue_tasks(limit=100) if hasattr(mgr, "list_queue_tasks") else []
            
            pending = sum(1 for t in tasks if t["status"] == "pending")
            running = sum(1 for t in tasks if t["status"] == "running")
            completed = sum(1 for t in tasks if t["status"] == "completed")
            failed = sum(1 for t in tasks if t["status"] == "failed")

            return {
                "is_running": self._thread is not None and self._thread.is_alive(),
                "is_paused": self.is_paused,
                "delay_seconds": delay,
                "active_task": self.active_task,
                "counts": {
                    "pending": pending,
                    "running": running,
                    "completed": completed,
                    "failed": failed,
                    "total": len(tasks)
                }
            }

    def _run_loop(self):
        while not self._stop_event.is_set():
            if self.is_paused:
                time.sleep(0.5)
                continue

            mgr = self._get_mgr()

            # Fetch next pending task
            task = mgr.get_next_pending_task()
            if not task:
                self.active_task = None
                time.sleep(0.5)
                continue

            task_id = task["id"]
            self.active_task = task
            mgr.update_task_status(task_id, "running")

            # Execute task
            result_text = ""
            error_text = None
            output_blend_path = None
            output_image_path = None
            success = True

            try:
                task_type = task.get("task_type", "code")
                payload = task.get("payload", {})

                if task_type == "code":
                    code = payload.get("code", "")
                    
                    # Clean markdown code blocks if AI wrapped code in ```python ... ```
                    import re
                    match = re.search(r"```(?:python)?\s*([\s\S]*?)```", code)
                    if match:
                        code = match.group(1).strip()
                    else:
                        code = code.strip()

                    res = bridge.execute_python_code(code)
                    if res.get("status") == "error":
                        success = False
                        error_text = res.get("error", "Code execution failed")
                    result_text = res.get("stdout") or res.get("stderr") or "Code executed successfully."

                elif task_type == "render":
                    res = bridge.capture_and_save_viewport()
                    if res.get("status") == "error":
                        success = False
                        error_text = res.get("error")
                    else:
                        output_image_path = res.get("filepath")
                        result_text = f"Render saved: {output_image_path}"

                # Auto-save after execution
                if success:
                    # 1. Auto-save .blend snapshot
                    if mgr.get_setting("auto_save_blend", "true") == "true":
                        snap_res = bridge.save_blend_snapshot()
                        if snap_res.get("status") == "success":
                            output_blend_path = snap_res.get("filepath")

                    # 2. Auto-save viewport image
                    if mgr.get_setting("auto_save_image", "true") == "true":
                        img_res = bridge.capture_and_save_viewport()
                        if img_res.get("status") == "success":
                            output_image_path = img_res.get("filepath")

            except Exception as e:
                success = False
                error_text = str(e)

            # Update final status
            final_status = "completed" if success else "failed"
            mgr.update_task_status(
                task_id=task_id,
                status=final_status,
                output_blend=output_blend_path,
                output_image=output_image_path,
                result_text=result_text,
                error=error_text
            )
            self.active_task = None

            # Apply Global Delay between tasks
            try:
                delay = float(mgr.get_setting("queue_delay_seconds", 2.0))
            except Exception:
                delay = 2.0

            if delay > 0 and not self._stop_event.is_set():
                # Sleep in small increments to be responsive to stop/pause
                slept = 0.0
                while slept < delay and not self._stop_event.is_set():
                    time.sleep(min(0.2, delay - slept))
                    slept += 0.2


# Singleton worker instance
task_queue = TaskQueueWorker()
