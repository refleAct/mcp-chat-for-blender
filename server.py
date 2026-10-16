"""
Multi-threaded HTTP & MCP Server for Blender
Serves the mobile-friendly Web UI, REST APIs, and MCP JSON-RPC endpoints.
Uses Python's standard library http.server for 100% ARM64 / PRoot compatibility.
"""

import os
import json
import mimetypes
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from typing import Optional

from blender_bridge import bridge
from session_manager import session_mgr
from llm_client import LLMClient
from mcp_handler import mcp_handler
from task_queue import task_queue
from cli_runner import cli_runner


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads for concurrency."""
    daemon_threads = True
    allow_reuse_address = True


class BlenderMCPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy logs, can be turned on for debugging
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_data = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw_data)
        except Exception:
            pass
        return {}

    # -------------------------------------------------------------
    # GET Handlers
    # -------------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Static Files & Web UI
        if path == "/" or path == "/index.html":
            self._serve_static_file("index.html")
            return
        elif path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            self._serve_static_file(rel_path)
            return

        # 2. REST API Endpoints
        if path == "/api/status":
            self._send_json(200, {
                "status": "online",
                "blender_active": True,
                "version": "1.0.0"
            })
            return

        elif path == "/api/sessions":
            sessions = session_mgr.list_sessions()
            self._send_json(200, {"sessions": sessions})
            return

        elif path.startswith("/api/sessions/"):
            session_id = path[len("/api/sessions/"):].strip("/")
            session = session_mgr.get_session(session_id)
            if session:
                self._send_json(200, {"session": session})
            else:
                self._send_json(404, {"error": "Session not found"})
            return

        elif path == "/api/settings":
            settings = session_mgr.get_all_settings()
            self._send_json(200, {"settings": settings})
            return

        elif path == "/api/blender/scene":
            info = bridge.get_scene_info()
            self._send_json(200, info)
            return

        elif path == "/api/blender/viewport":
            shot = bridge.capture_viewport()
            self._send_json(200, shot)
            return

        elif path == "/api/queue":
            status = task_queue.get_status()
            tasks = session_mgr.list_queue_tasks(limit=100)
            self._send_json(200, {
                "status": status,
                "tasks": tasks
            })
            return

        elif path == "/api/environment":
            env = cli_runner.detect_environment()
            self._send_json(200, env)
            return

        # 3. MCP SSE Endpoint (for SSE-compatible MCP clients)
        elif path == "/sse":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._send_cors_headers()
            self.end_headers()
            
            # Send initial endpoint event pointing to /mcp
            init_event = f"event: endpoint\ndata: /mcp\n\n"
            try:
                self.wfile.write(init_event.encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass
            return

        self._send_json(404, {"error": f"Path not found: {path}"})

    # -------------------------------------------------------------
    # POST Handlers
    # -------------------------------------------------------------

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        # 1. MCP JSON-RPC Endpoint (for Claude Code, agy CLI, and mcp_bridge)
        if path == "/mcp":
            res = mcp_handler.handle_request(body)
            if res is not None:
                self._send_json(200, res)
            else:
                self.send_response(204)
                self.end_headers()
            return

        # 2. REST API: Create Session
        elif path == "/api/sessions":
            title = body.get("title", "New Chat")
            model = body.get("model")
            provider = body.get("provider")
            new_session = session_mgr.create_session(title=title, model_name=model, provider=provider)
            self._send_json(201, {"session": new_session})
            return

        # 3. REST API: Send Message & Chat with LLM
        elif path.startswith("/api/sessions/") and path.endswith("/messages"):
            # Format: /api/sessions/<session_id>/messages
            parts = path.split("/")
            session_id = parts[3]
            session = session_mgr.get_session(session_id)
            if not session:
                self._send_json(404, {"error": "Session not found"})
                return

            user_content = body.get("content", "").strip()
            images = body.get("images", []) # array of base64 data URLs
            
            if not user_content and not images:
                self._send_json(400, {"error": "Message content or image required"})
                return

            # Save user message
            session_mgr.add_message(
                session_id=session_id,
                role="user",
                content=user_content,
                images=images
            )

            # Auto-title session if it's the first message and still "New Chat"
            if len(session["messages"]) == 0 and session["title"] == "New Chat" and user_content:
                short_title = user_content[:25].replace("\n", " ").strip()
                session_mgr.update_session_title(session_id, short_title)

            # Load provider configuration
            settings = session_mgr.get_all_settings()
            active_provider = session.get("provider") or settings.get("active_provider", "openrouter")
            
            api_key = ""
            base_url = ""
            model_name = session.get("model_name")

            if active_provider == "openrouter":
                api_key = settings.get("openrouter_api_key", "")
                if not model_name:
                    model_name = settings.get("openrouter_model", "anthropic/claude-3.5-sonnet")
            elif active_provider == "nvidia_nim":
                api_key = settings.get("nvidia_nim_api_key", "")
                if not model_name:
                    model_name = settings.get("nvidia_nim_model", "meta/llama-3.3-70b-instruct")
            elif active_provider == "local":
                base_url = settings.get("local_base_url", "http://127.0.0.1:11434/v1")
                if not model_name:
                    model_name = settings.get("local_model", "qwen2.5-coder:latest")
            else: # custom
                api_key = settings.get("custom_api_key", "")
                base_url = settings.get("custom_base_url", "")
                if not model_name:
                    model_name = settings.get("custom_model", "gpt-4o")

            provider_config = {
                "provider": active_provider,
                "api_key": api_key,
                "base_url": base_url,
                "model": model_name,
                "reasoning_effort": session.get("reasoning_effort") or settings.get("reasoning_effort", "medium"),
                "thinking_budget": settings.get("thinking_budget", "2048"),
                "temperature": float(settings.get("temperature", 0.7))
            }

            # Run agent loop
            client = LLMClient(provider_config)
            
            # Fetch updated messages
            current_session = session_mgr.get_session(session_id)
            try:
                result = client.run_agent_loop(
                    system_prompt=current_session.get("system_prompt", ""),
                    messages=current_session.get("messages", [])
                )
                
                # Save assistant response
                assistant_msg = session_mgr.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=result["content"],
                    thought=result.get("thought"),
                    images=result.get("captured_images"),
                    tool_calls=result.get("tool_events")
                )

                self._send_json(200, {
                    "status": "success",
                    "reply": assistant_msg,
                    "session": session_mgr.get_session(session_id)
                })

            except Exception as e:
                # Save error notice in chat
                err_msg = session_mgr.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=f"⚠️ **Error executing request**: {str(e)}"
                )
                self._send_json(500, {
                    "error": str(e),
                    "reply": err_msg,
                    "session": session_mgr.get_session(session_id)
                })
            return

        # 4. REST API: Update Settings
        elif path == "/api/settings":
            session_mgr.update_settings(body)
            self._send_json(200, {"status": "updated", "settings": session_mgr.get_all_settings()})
            return

        # 5. REST API: Direct Code Execution from UI
        elif path == "/api/blender/execute":
            code = body.get("code", "")
            res = bridge.execute_python_code(code)
            self._send_json(200, res)
            return

        # 6. REST API: Task Queue Controls
        elif path == "/api/queue":
            title = body.get("title", "Queued Task")
            task_type = body.get("task_type", "code")
            payload = body.get("payload", {})
            task_queue.start()
            new_task = session_mgr.enqueue_task(title=title, task_type=task_type, payload=payload)
            self._send_json(201, {"task": new_task, "status": task_queue.get_status()})
            return

        elif path == "/api/queue/batch":
            tasks = body.get("tasks", [])
            task_queue.start()
            created = session_mgr.enqueue_batch_tasks(tasks)
            self._send_json(201, {"tasks": created, "status": task_queue.get_status()})
            return

        elif path == "/api/queue/clear":
            session_mgr.clear_queue()
            self._send_json(200, {"status": "cleared", "queue_status": task_queue.get_status()})
            return

        elif path == "/api/queue/pause":
            task_queue.pause()
            self._send_json(200, {"status": "paused", "queue_status": task_queue.get_status()})
            return

        elif path == "/api/queue/resume":
            task_queue.resume()
            task_queue.start()
            self._send_json(200, {"status": "resumed", "queue_status": task_queue.get_status()})
            return

        # 7. Plan Mode Endpoint
        elif path == "/api/plan":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_json(400, {"error": "Prompt is required"})
                return

            settings = session_mgr.get_all_settings()
            provider = body.get("provider") or settings.get("active_provider", "openrouter")
            model = body.get("model") or settings.get(f"{provider}_model", "anthropic/claude-3.5-sonnet")
            api_key = settings.get(f"{provider}_api_key", "")
            base_url = settings.get(f"{provider}_base_url", "")

            client = LLMClient({
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "reasoning_effort": settings.get("reasoning_effort", "medium")
            })

            try:
                plan = client.generate_plan(prompt)
                self._send_json(200, {"status": "success", "plan": plan})
            except Exception as e:
                self._send_json(500, {"error": f"Plan generation failed: {str(e)}"})
            return

        # 8. Auto Mode Endpoint
        elif path == "/api/auto":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_json(400, {"error": "Prompt is required"})
                return

            settings = session_mgr.get_all_settings()
            provider = body.get("provider") or settings.get("active_provider", "openrouter")
            model = body.get("model") or settings.get(f"{provider}_model", "anthropic/claude-3.5-sonnet")
            api_key = settings.get(f"{provider}_api_key", "")
            base_url = settings.get(f"{provider}_base_url", "")

            client = LLMClient({
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "reasoning_effort": settings.get("reasoning_effort", "medium")
            })

            try:
                # 1. Generate plan
                plan = client.generate_plan(prompt)
                steps = plan.get("steps", [])

                # 2. Convert steps to queue tasks
                batch_tasks = []
                for s in steps:
                    batch_tasks.append({
                        "title": s.get("title", f"Step {s.get('step_number', 1)}"),
                        "task_type": s.get("task_type", "code"),
                        "payload": {"code": s.get("code", "")}
                    })

                # 3. Add to queue & start worker
                task_queue.start()
                enqueued = session_mgr.enqueue_batch_tasks(batch_tasks)

                self._send_json(200, {
                    "status": "auto_started",
                    "plan": plan,
                    "enqueued_count": len(enqueued),
                    "queue_status": task_queue.get_status()
                })
            except Exception as e:
                self._send_json(500, {"error": f"Auto mode execution failed: {str(e)}"})
            return

        self._send_json(404, {"error": f"Path not found: {path}"})

    # -------------------------------------------------------------
    # PATCH & DELETE Handlers
    # -------------------------------------------------------------

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path.startswith("/api/sessions/"):
            session_id = path[len("/api/sessions/"):].strip("/")
            if "title" in body:
                session_mgr.update_session_title(session_id, body["title"])
            if "model" in body and "provider" in body:
                session_mgr.update_session_model(
                    session_id, 
                    body["model"], 
                    body["provider"], 
                    body.get("reasoning_effort")
                )
            updated = session_mgr.get_session(session_id)
            self._send_json(200, {"session": updated})
            return

        self._send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/sessions/"):
            session_id = path[len("/api/sessions/"):].strip("/")
            session_mgr.delete_session(session_id)
            self._send_json(200, {"status": "deleted", "session_id": session_id})
            return

        self._send_json(404, {"error": "Not found"})

    # -------------------------------------------------------------
    # Static Files Serving Helper
    # -------------------------------------------------------------

    def _serve_static_file(self, rel_path: str):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(base_dir, "static")
        safe_path = os.path.normpath(os.path.join(static_dir, rel_path))

        # Security check to prevent directory traversal
        if not safe_path.startswith(static_dir) or not os.path.exists(safe_path) or os.path.isdir(safe_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        mime_type, _ = mimetypes.guess_type(safe_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(safe_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if "text" in mime_type or "javascript" in mime_type or "json" in mime_type else mime_type)
            self.send_header("Content-Length", str(len(content)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))


class BlenderServerManager:
    def __init__(self):
        self.server: Optional[ThreadedHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.port = 8000
        self.is_running = False

    def start(self, host="0.0.0.0", port=8000):
        if self.is_running:
            return True, f"Server is already running on port {self.port}"

        self.port = int(session_mgr.get_setting("port", port))
        
        # Ensure bridge timer is active inside Blender
        bridge.start_timer()

        try:
            self.server = ThreadedHTTPServer((host, self.port), BlenderMCPRequestHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.is_running = True
            task_queue.start() # Start task queue worker
            return True, f"Blender MCP Chat Server started on http://127.0.0.1:{self.port}"
        except Exception as e:
            self.is_running = False
            return False, f"Failed to start server: {str(e)}"

    def stop(self):
        if not self.is_running:
            return True, "Server is not running"

        try:
            task_queue.stop() # Stop task queue worker
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            bridge.stop_timer()
            self.is_running = False
            return True, "Server stopped successfully"
        except Exception as e:
            return False, f"Error stopping server: {str(e)}"


# Singleton server manager
server_mgr = BlenderServerManager()
