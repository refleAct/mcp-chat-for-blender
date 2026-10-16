"""
Background Task Queue Manager for Blender
Executes queued tasks sequentially with a configurable global delay.
Automatically saves .blend snapshots and rendered images after task completion.
Zero external dependencies.
"""

import os
import re
import time
import threading
from typing import Dict, Any, Optional

import session_manager
from blender_bridge import bridge


NL = chr(10)


def repair_indentation(code: str) -> str:
    """AI가 만든 코드의 흔한 들여쓰기 오류를 자동 복구한다.
    - 공통 들여쓰기 제거(dedent), 탭 -> 공백
    - 'unexpected indent': 직전 줄이 블록 시작(:)이 아니면 해당 줄의 들여쓰기를 직전 줄 수준으로 맞춤
    """
    import textwrap
    code = textwrap.dedent(code.expandtabs(4)).strip(NL)
    lines = code.split(NL)
    for _ in range(20):
        try:
            compile(NL.join(lines), "<queue>", "exec")
            break
        except IndentationError as e:
            n = (e.lineno or 0) - 1
            if not (0 < n < len(lines)) or "unexpected indent" not in str(e.msg):
                break
            prev = next((l for l in reversed(lines[:n]) if l.strip() and not l.strip().startswith("#")), "")
            prev_indent = len(prev) - len(prev.lstrip())
            if prev.rstrip().endswith(":"):
                break
            lines[n] = " " * prev_indent + lines[n].lstrip()
        except SyntaxError:
            break
    return NL.join(lines)


class TaskQueueWorker:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_paused = False
        self.active_task: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()
        self._recovered = False
        self.progress = ""

    def _set_progress(self, text: str):
        """진행 문구를 갱신하고 UI(채팅/큐 패널)를 다시 그리도록 알린다."""
        self.progress = text
        try:
            import bpy

            def _ui():
                hook = bpy.app.driver_namespace.get("mcpchat_redraw")
                if hook:
                    hook()
                return None
            bpy.app.timers.register(_ui, first_interval=0.05)
        except Exception:
            pass

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
            if not self._recovered:
                self._recovered = True
                try:
                    self._get_mgr().recover_interrupted_tasks()
                except Exception:
                    pass
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
            delay = float(settings.get("queue_delay_seconds", 60))
            c = mgr.queue_counts() if hasattr(mgr, "queue_counts") else {}
            pending = c.get("pending", 0)
            running = c.get("running", 0)
            completed = c.get("completed", 0)
            failed = c.get("failed", 0)
            tasks = [None] * c.get("total", 0)

            return {
                "is_running": self._thread is not None and self._thread.is_alive(),
                "is_paused": self.is_paused,
                "delay_seconds": delay,
                "active_task": self.active_task,
                "progress": self.progress,
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

            # Fetch next pending task (DB 오류로 워커 스레드가 죽지 않도록 보호)
            try:
                task = mgr.get_next_pending_task()
            except Exception:
                time.sleep(1.0)
                continue
            if not task:
                self.active_task = None
                time.sleep(0.5)
                continue

            task_id = task["id"]
            task_title = task.get("title", "작업")
            self.active_task = task
            mgr.update_task_status(task_id, "running")
            self._set_progress("실행 중")

            # Execute task
            result_text = ""
            error_text = None
            output_blend_path = None
            output_image_path = None
            output_glb_path = None
            pack_note = ""
            success = True

            try:
                task_type = task.get("task_type", "code")
                payload = task.get("payload", {})

                if task_type == "code":
                    code = payload.get("code", "")
                    
                    # Clean markdown code blocks if AI wrapped code in ```python ... ```
                    match = re.search(r"```(?:python)?\s*([\s\S]*?)```", code)
                    if match:
                        code = match.group(1).strip()
                    else:
                        code = code.strip()

                    code = repair_indentation(code)
                    res = bridge.execute_python_code(code)
                    if res.get("status") == "error":
                        success = False
                        error_text = res.get("error", "Code execution failed")
                    result_text = res.get("stdout") or res.get("stderr") or "Code executed successfully."

                elif task_type == "prompt":
                    prompt = payload.get("prompt", "")
                    backend = payload.get("backend", "CLAUDE")
                    from cli_runner import cli_runner
                    self._set_progress("CLI 작업 중")
                    
                    done_event = threading.Event()
                    cli_res = {"success": False, "output": ""}
                    def _done(s, out):
                        cli_res["success"] = s
                        cli_res["output"] = out
                        done_event.set()
                    
                    cli_type = {"CLAUDE": "claude", "AGY": "agy", "CODEX": "codex"}.get(backend, "claude")
                    try:
                        n_img = len([u for u in (payload.get("images") or []) if u])
                        mgr.set_sent_prompt(task_id, cli_runner.compose_prompt(
                            cli_type, "AUTO", prompt, cli_runner.build_guidelines(),
                            [f"<첨부이미지 {k + 1}>" for k in range(n_img)]))
                    except Exception:
                        pass
                    cli_runner.run_cli_command_async(cli_type, prompt, mode="AUTO", on_complete=_done,
                                                     images=payload.get("images"))
                    done_event.wait(timeout=300)
                    success = cli_res["success"]
                    result_text = cli_res["output"]
                    if not success:
                        error_text = result_text or "Prompt task execution failed"

                elif task_type == "auto_plan":
                    # 하나의 지시 = 하나의 작업: 계획 생성 -> 단계별 코드를 이 작업 안에서 순차 실행
                    from llm_client import LLMClient
                    self._set_progress("계획 수립 중")
                    client = LLMClient.from_settings(mgr.get_all_settings(include_secrets=True))
                    from llm_client import compose_plan_messages
                    msgs = compose_plan_messages(payload.get("prompt", ""))
                    n_img = len([u for u in (payload.get("images") or []) if u])
                    img_note = (NL + f"[첨부 이미지 {n_img}장 포함]") if n_img else ""
                    mgr.set_sent_prompt(task_id, "== 전송 프롬프트 (system) ==" + NL + msgs[0]["content"]
                                        + NL + NL + "== 전송 프롬프트 (user) ==" + NL + msgs[1]["content"] + img_note)
                    approved = payload.get("plan")
                    plan = approved if isinstance(approved, dict) and approved.get("steps") else client.generate_plan(
                        payload.get("prompt", ""), images=payload.get("images"))
                    steps = plan.get("steps", [])
                    try:
                        import json as _json
                        mgr.append_sent_prompt(task_id, NL + NL + ("== 사용자가 승인한 계획 ==" if approved else "== AI가 생성한 계획 ==") + NL
                                               + _json.dumps(plan, ensure_ascii=False, indent=2))
                    except Exception:
                        pass
                    if not steps:
                        raise RuntimeError("계획에 실행할 단계가 없습니다.")
                    logs = []
                    for n, s in enumerate(steps, 1):
                        while self.is_paused and not self._stop_event.is_set():
                            time.sleep(0.5)
                        if self._stop_event.is_set():
                            break
                        step_title = s.get("title") or f"Step {n}"
                        self._set_progress(f"Step {n}/{len(steps)} 실행 중: {step_title}")
                        raw = s.get("code") or ""
                        if not str(raw).strip():
                            logs.append(f"- Step {n}/{len(steps)}: {step_title} (코드 없음, 건너뜀)")
                            continue
                        m = re.search(r"```(?:python)?\s*([\s\S]*?)```", str(raw))
                        step_code = repair_indentation((m.group(1) if m else str(raw)).strip())
                        res = bridge.execute_python_code(step_code)
                        if res.get("status") == "error":
                            success = False
                            error_text = f"Step {n}/{len(steps)} '{step_title}' 실패: {res.get('error', '')}"
                            logs.append("✖ " + error_text)
                            break
                        logs.append(f"✔ Step {n}/{len(steps)}: {step_title}")
                    result_text = NL.join(logs)

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
                            pack_note = f" (리소스 {snap_res.get('packed', 0)}개 패킹)" if snap_res.get("packed") else ""

                    # 1-b. GLB export
                    if mgr.get_setting("auto_save_glb", "true") == "true":
                        glb_res = bridge.export_glb()
                        if glb_res.get("status") == "success":
                            output_glb_path = glb_res.get("filepath")

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
                output_glb=output_glb_path,
                result_text=result_text,
                error=error_text
            )
            self.active_task = None
            self._set_progress("")

            # Leave completion message in active session
            try:
                tabs = mgr.get_tab_sessions(3)
                if tabs:
                    sid = tabs[0]["id"]
                    if success:
                        comp_msg = f"✅ '{task_title}' 생성이 완료되었습니다."
                        if output_blend_path:
                            comp_msg += f"\n📁 스냅샷: {os.path.basename(output_blend_path)}{pack_note}"
                        if output_glb_path:
                            comp_msg += f"\n🧊 GLB: {os.path.basename(output_glb_path)}"
                        if output_image_path:
                            comp_msg += f"\n📸 렌더: {os.path.basename(output_image_path)}"
                        mgr.add_message(sid, "assistant", comp_msg)
                    else:
                        mgr.add_message(sid, "assistant", f"⚠️ '{task_title}' 실행 실패: {error_text}")

                    # Check if all tasks in queue are finished
                    next_task = mgr.get_next_pending_task()
                    if not next_task and success:
                        mgr.add_message(sid, "assistant", "🎉 모든 큐 작업의 생성이 완료되었습니다!")

                    # Refresh Blender UIList if running inside Blender
                    try:
                        import bpy
                        def _refresh_ui():
                            try:
                                hook = bpy.app.driver_namespace.get("mcpchat_sync")
                                if hook:
                                    hook(sid)
                            except Exception:
                                pass
                            return None
                        bpy.app.timers.register(_refresh_ui, first_interval=0.1)
                    except Exception:
                        pass
            except Exception:
                pass

            # Apply Global Delay between tasks
            try:
                delay = float(mgr.get_setting("queue_delay_seconds", 60))
            except Exception:
                delay = 60.0

            if delay > 0 and not self._stop_event.is_set():
                # Sleep in small increments to be responsive to stop/pause
                slept = 0.0
                while slept < delay and not self._stop_event.is_set():
                    time.sleep(min(0.2, delay - slept))
                    slept += 0.2


# Singleton worker instance
task_queue = TaskQueueWorker()
