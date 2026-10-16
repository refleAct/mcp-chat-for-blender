"""
Blender Bridge for MCP Chat
Handles thread-safe execution of Blender Python code using bpy.app.timers,
viewport capturing, and scene introspection.
Designed for Blender running in Termux PRoot Linux / Android / Desktop.
"""

import sys
import io
import os
import time
import base64
import queue
import threading
import traceback

# Import safe data dir helper to prevent Android permission errors
from session_manager import get_safe_data_dir

# bpy is only available when running inside Blender
try:
    import bpy
    IN_BLENDER = True
except ImportError:
    bpy = None
    IN_BLENDER = False


class BlenderBridge:
    def __init__(self):
        self.cmd_queue = queue.Queue()
        self.is_timer_running = False
        self._lock = threading.Lock()
        self._exec_globals = {"__name__": "__blender_mcp__"}

    # -------------------------------------------------------------
    # Output location / flags (N패널 큐 패널 하단에서 지정)
    # -------------------------------------------------------------

    @staticmethod
    def _setting(key, default=""):
        try:
            from session_manager import session_mgr
            return str(session_mgr.get_setting(key, default) or default)
        except Exception:
            return default

    def output_base_dir(self) -> str:
        """사용자가 지정한 저장 위치. 비어 있거나 만들 수 없으면 기본 위치(<데이터폴더>/output)."""
        base = self._setting("output_dir", "").strip()
        if base:
            try:
                if IN_BLENDER:
                    base = bpy.path.abspath(base)
                base = os.path.expanduser(base)
                os.makedirs(base, exist_ok=True)
                return base
            except Exception:
                pass
        return os.path.join(get_safe_data_dir(), "output")

    @staticmethod
    def _stamp_name(ext: str) -> str:
        stem = "scene"
        try:
            if bpy.data.filepath:
                stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0] or stem
        except Exception:
            pass
        return f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}.{ext}"

    def reset_namespace(self):
        """코드 실행용 공유 네임스페이스 초기화."""
        self._exec_globals = {"__name__": "__blender_mcp__"}

    def start_timer(self):
        """Registers the queue processing timer in Blender's main thread."""
        if not IN_BLENDER:
            return
        with self._lock:
            if not self.is_timer_running:
                # Run process_queue every 0.02 seconds (50Hz)
                bpy.app.timers.register(self._process_queue, persistent=True)
                self.is_timer_running = True

    def stop_timer(self):
        """Unregisters the timer."""
        if not IN_BLENDER:
            return
        with self._lock:
            if self.is_timer_running:
                try:
                    if bpy.app.timers.is_registered(self._process_queue):
                        bpy.app.timers.unregister(self._process_queue)
                except Exception:
                    pass
                self.is_timer_running = False

    def _process_queue(self):
        """Executed inside Blender's main loop via bpy.app.timers."""
        processed_count = 0
        # Process up to 5 commands per tick to prevent stuttering
        while not self.cmd_queue.empty() and processed_count < 5:
            try:
                task = self.cmd_queue.get_nowait()
            except queue.Empty:
                break

            func, args, kwargs, result_holder, event = task
            try:
                result_holder['result'] = func(*args, **kwargs)
                result_holder['success'] = True
            except Exception as e:
                result_holder['error'] = str(e)
                result_holder['traceback'] = traceback.format_exc()
                result_holder['success'] = False
            finally:
                event.set()
                self.cmd_queue.task_done()
                processed_count += 1

        # Return interval for next timer call
        return 0.02

    def run_in_main_thread(self, func, *args, timeout=30.0, **kwargs):
        """Dispatches a function to Blender's main thread and waits for the result."""
        if not IN_BLENDER:
            return {"success": False, "error": "Not running inside Blender environment"}

        self.start_timer()
        event = threading.Event()
        result_holder = {}
        self.cmd_queue.put((func, args, kwargs, result_holder, event))

        # Wait for completion
        completed = event.wait(timeout=timeout)
        if not completed:
            return {
                "success": False,
                "error": f"Execution timed out after {timeout} seconds"
            }
        return result_holder

    # -------------------------------------------------------------
    # Main Thread Operations
    # -------------------------------------------------------------

    def execute_python_code(self, code: str) -> dict:
        """Executes arbitrary Python code safely within Blender and captures output."""
        def _exec():
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            # 실행 간 변수 유지 (여러 단계 계획에서 앞 단계의 변수를 뒤 단계가 사용) + 표준 전역 갱신
            exec_globals = self._exec_globals
            exec_globals.update({
                'bpy': bpy,
                'mathutils': sys.modules.get('mathutils'),
                'context': bpy.context,
                'C': bpy.context,
                'D': bpy.data
            })

            try:
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture
                exec(code, exec_globals)
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                return {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue(),
                    "status": "success"
                }
            except Exception as e:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                return {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue(),
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "status": "error"
                }

        # 무거운 모델링 코드도 완료까지 기다린다 (타임아웃 후에도 코드는 계속 실행되므로 너무 짧으면 경합 발생)
        res = self.run_in_main_thread(_exec, timeout=180.0)
        if res.get("success"):
            return res.get("result", {})
        return {"status": "error", "error": res.get("error", "Unknown error")}

    def get_scene_info(self) -> dict:
        """Collects concise metadata about the current Blender scene."""
        def _inspect():
            scene = bpy.context.scene
            objects = []
            for obj in scene.objects:
                objects.append({
                    "name": obj.name,
                    "type": obj.type,
                    "location": [round(v, 3) for v in obj.location],
                    "rotation": [round(v, 3) for v in obj.rotation_euler],
                    "scale": [round(v, 3) for v in obj.scale],
                    "hide_viewport": obj.hide_viewport,
                    "materials": [slot.material.name for slot in obj.material_slots if slot.material]
                })

            materials = [mat.name for mat in bpy.data.materials]
            active_obj = bpy.context.active_object.name if bpy.context.active_object else None

            return {
                "scene_name": scene.name,
                "active_object": active_obj,
                "object_count": len(objects),
                "objects": objects[:50],  # Limit to 50 objects for token efficiency
                "materials": materials[:30],
                "render_engine": scene.render.engine,
                "current_frame": scene.frame_current,
                "resolution": [scene.render.resolution_x, scene.render.resolution_y]
            }

        res = self.run_in_main_thread(_inspect)
        if res.get("success"):
            return res.get("result", {})
        return {"error": res.get("error", "Failed to inspect scene")}

    def capture_viewport(self, max_dim=800) -> dict:
        """
        Captures the current 3D viewport or renders an OpenGL snapshot.
        Returns a base64 encoded PNG image and temporary path.
        """
        def _capture():
            import tempfile

            temp_dir = tempfile.gettempdir()
            screenshot_path = os.path.join(temp_dir, f"blender_mcp_shot_{int(time.time())}.png")

            screen = bpy.context.screen

            # Find 3D Viewport area
            view3d_area = None
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    view3d_area = area
                    break

            # Fallback: render OpenGL frame if viewport snapshot cannot be triggered
            try:
                if view3d_area:
                    # Save current render settings
                    orig_path = bpy.context.scene.render.filepath
                    orig_format = bpy.context.scene.render.image_settings.file_format

                    bpy.context.scene.render.filepath = screenshot_path
                    bpy.context.scene.render.image_settings.file_format = 'PNG'

                    # Execute OpenGL render (fast, takes current viewport appearance)
                    bpy.ops.render.opengl(write_still=True, view_context=True)

                    # Restore settings
                    bpy.context.scene.render.filepath = orig_path
                    bpy.context.scene.render.image_settings.file_format = orig_format
                else:
                    # Generic viewport screenshot
                    bpy.ops.screen.screenshot(filepath=screenshot_path)
            except Exception:
                # Fallback to screenshot operator
                try:
                    bpy.ops.screen.screenshot(filepath=screenshot_path)
                except Exception as inner_e:
                    return {"error": f"Failed to capture screen: {inner_e}"}

            if not os.path.exists(screenshot_path):
                return {"error": "Screenshot file was not generated"}

            try:
                with open(screenshot_path, "rb") as img_file:
                    encoded_b64 = base64.b64encode(img_file.read()).decode("utf-8")
                return {
                    "image_base64": f"data:image/png;base64,{encoded_b64}",
                    "filepath": screenshot_path,
                    "status": "success"
                }
            except Exception as read_err:
                return {"error": f"Failed to encode screenshot: {read_err}"}

        res = self.run_in_main_thread(_capture, timeout=15.0)
        if res.get("success"):
            return res.get("result", {})
        return {"error": res.get("error", "Failed to capture viewport")}

    def save_blend_snapshot(self, custom_path=None) -> dict:
        """Saves a copy of the active .blend file to the output directory."""
        def _save():
            output_dir = os.path.join(self.output_base_dir(), "blends")
            os.makedirs(output_dir, exist_ok=True)
            target_path = custom_path or os.path.join(output_dir, self._stamp_name("blend"))

            # 리소스 패킹: 외부 텍스처/사운드/폰트를 .blend 안에 포함시켜 단독으로 열 수 있게 한다
            packed, pack_failed = 0, []
            if self._setting("auto_save_pack", "true").lower() == "true":
                for img in bpy.data.images:
                    try:
                        if img.source == 'FILE' and img.filepath and not img.packed_file:
                            img.pack()
                            packed += 1
                    except Exception:
                        pack_failed.append(img.name)
                for coll_name in ("sounds", "fonts"):
                    for res in getattr(bpy.data, coll_name, []):
                        try:
                            fp = getattr(res, "filepath", "")
                            if fp and fp != "<builtin>" and not res.packed_file:
                                res.pack()
                                packed += 1
                        except Exception:
                            pack_failed.append(res.name)

            try:
                # Save a copy without changing active file path
                bpy.ops.wm.save_as_mainfile(filepath=target_path, copy=True)
                return {"status": "success", "filepath": target_path, "packed": packed, "pack_failed": pack_failed}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        res = self.run_in_main_thread(_save, timeout=120.0)
        if res.get("success"):
            return res.get("result", {})
        return {"status": "error", "error": res.get("error", "Failed to save blend snapshot")}

    def export_glb(self, custom_path=None) -> dict:
        """현재 씬을 .glb(glTF Binary)로 내보낸다."""
        def _export():
            out_dir = os.path.join(self.output_base_dir(), "glb")
            os.makedirs(out_dir, exist_ok=True)
            target_path = custom_path or os.path.join(out_dir, self._stamp_name("glb"))
            try:
                bpy.ops.export_scene.gltf(filepath=target_path, export_format='GLB')
            except Exception as e:
                return {"status": "error", "error": f"GLB export failed (glTF add-on enabled?): {e}"}
            if not os.path.exists(target_path):
                return {"status": "error", "error": "GLB file was not generated"}
            return {"status": "success", "filepath": target_path}

        res = self.run_in_main_thread(_export, timeout=180.0)
        if res.get("success"):
            return res.get("result", {})
        return {"status": "error", "error": res.get("error", "Failed to export GLB")}

    def capture_and_save_viewport(self, custom_path=None) -> dict:
        """Captures viewport and permanently saves to the output directory."""
        def _save_img():
            output_dir = os.path.join(self.output_base_dir(), "renders")
            os.makedirs(output_dir, exist_ok=True)
            target_path = custom_path or os.path.join(output_dir, self._stamp_name("png"))

            # Use OpenGL render for fast and true-to-viewport capture
            try:
                orig_path = bpy.context.scene.render.filepath
                orig_format = bpy.context.scene.render.image_settings.file_format

                bpy.context.scene.render.filepath = target_path
                bpy.context.scene.render.image_settings.file_format = 'PNG'

                bpy.ops.render.opengl(write_still=True, view_context=True)

                bpy.context.scene.render.filepath = orig_path
                bpy.context.scene.render.image_settings.file_format = orig_format

                return {"status": "success", "filepath": target_path}
            except Exception as e:
                try:
                    bpy.ops.screen.screenshot(filepath=target_path)
                    return {"status": "success", "filepath": target_path}
                except Exception as inner_e:
                    return {"status": "error", "error": f"{e} / {inner_e}"}

        res = self.run_in_main_thread(_save_img, timeout=15.0)
        if res.get("success"):
            return res.get("result", {})
        return {"status": "error", "error": res.get("error", "Failed to capture and save viewport")}


# Global bridge singleton
bridge = BlenderBridge()
