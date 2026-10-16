"""
Multi-threaded HTTP & MCP Server for Blender
Serves the mobile-friendly Web UI, REST APIs, and MCP JSON-RPC endpoints.
Uses Python's standard library http.server for 100% ARM64 / PRoot compatibility.
"""

import os
import json
import mimetypes
import threading
import hmac
import socket
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


LOOPBACK_ADDRS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "[::1]"}
PUBLIC_PATHS = {"/", "/index.html", "/api/status"}
PROTECTED_SETTING_KEYS = {"mcp_token", "allow_lan", "cli_remote_token"}
MAX_BODY_BYTES = 64 * 1024 * 1024  # 이미지 base64 포함 요청 상한
DOWNLOADABLE = {"mcp_bridge.py", "termux_agent.py", "cli_runner.py", "guidelines.py"}


def get_lan_ips():
    """이 PC의 LAN IPv4 주소 목록 (Termux에서 접속할 주소 안내용)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # 실제 전송 없음, 라우팅 인터페이스 조회용
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


class BlenderMCPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy logs, can be turned on for debugging
        pass

    # -------------------------------------------------------------
    # Security: Origin / Host / Bearer token
    #  - 로컬(loopback) 접속: 토큰 불필요, 단 Host가 localhost 계열이고 Origin이 same-origin이어야 함
    #    (악성 웹페이지의 CORS / DNS rebinding 공격 차단)
    #  - 그 외(LAN) 접속: Authorization: Bearer <token> 필수
    # -------------------------------------------------------------

    def _is_loopback(self) -> bool:
        return self.client_address[0] in LOOPBACK_ADDRS

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return urlparse(origin).netloc == self.headers.get("Host", "")

    def _host_ok(self) -> bool:
        host_header = self.headers.get("Host", "") or ""
        host = "[::1]" if host_header.startswith("[") else host_header.rsplit(":", 1)[0]
        return host in LOCAL_HOSTNAMES

    def _token_ok(self) -> bool:
        token = session_mgr.get_or_create_token()
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            cand = auth[7:].strip()
        else:
            cand = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        return bool(cand) and hmac.compare_digest(cand.encode(), token.encode())

    def _gate(self, path: str) -> bool:
        """True면 요청 허용. 거부 시 응답까지 전송."""
        if path in PUBLIC_PATHS or path.startswith("/static/"):
            return True
        if not self._origin_ok():
            self._send_json(403, {"error": "Cross-origin request blocked"})
            return False
        if self._is_loopback():
            if not self._host_ok():
                self._send_json(403, {"error": "Invalid Host header"})
                return False
            return True
        if self._token_ok():
            return True
        self._send_json(401, {"error": "Unauthorized: Bearer token required (Preferences > LAN 접속)"})
        return False

    def _send_cors_headers(self):
        # same-origin 요청만 사용하므로 CORS 허용 헤더를 내보내지 않는다 (와일드카드 제거).
        pass

    def do_OPTIONS(self):
        self.send_response(204)
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
            if content_length > MAX_BODY_BYTES:
                return {}
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
        if not self._gate(path):
            return

        # Termux 연동용: 브릿지 / 원라인 설치 스크립트 배포
        if path == "/bridge.py" or path.startswith("/dl/"):
            name = "mcp_bridge.py" if path == "/bridge.py" else path[len("/dl/"):]
            if name not in DOWNLOADABLE:
                self._send_json(404, {"error": "not found"})
                return
            self._serve_static_file("", force_type="text/x-python", force_name=name)
            return
        elif path == "/termux/setup.sh":
            host = self.headers.get("Host", f"127.0.0.1:{server_mgr.port}")
            body = build_termux_script(f"http://{host}", session_mgr.get_or_create_token()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/x-shellscript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

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
            settings = {k: val for k, val in session_mgr.get_all_settings().items() if k not in PROTECTED_SETTING_KEYS}
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
        if not self._gate(path):
            return
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
            settings = session_mgr.get_all_settings(include_secrets=True)
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
            session_mgr.update_settings({k: val for k, val in body.items() if k not in PROTECTED_SETTING_KEYS})
            self._send_json(200, {"status": "updated", "settings": {k: val for k, val in session_mgr.get_all_settings().items() if k not in PROTECTED_SETTING_KEYS}})
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

            settings = session_mgr.get_all_settings(include_secrets=True)
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

            try:
                # 하나의 지시 = 하나의 큐 작업 (계획 생성/단계 실행은 작업 내부에서 처리)
                task_queue.resume()
                task_queue.start()
                task = session_mgr.enqueue_task(
                    title=prompt.splitlines()[0][:30],
                    task_type="auto_plan",
                    payload={"prompt": prompt, "backend": "API"}
                )
                self._send_json(200, {
                    "status": "auto_started",
                    "task": task,
                    "enqueued_count": 1,
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
        if not self._gate(path):
            return
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
        if not self._gate(path):
            return

        if path.startswith("/api/sessions/"):
            session_id = path[len("/api/sessions/"):].strip("/")
            session_mgr.delete_session(session_id)
            self._send_json(200, {"status": "deleted", "session_id": session_id})
            return

        self._send_json(404, {"error": "Not found"})

    # -------------------------------------------------------------
    # Static Files Serving Helper
    # -------------------------------------------------------------

    def _serve_static_file(self, rel_path: str, force_type: Optional[str] = None, force_name: str = "mcp_bridge.py"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(base_dir, "static")
        if force_type:
            # 허용된 단일 파일(mcp_bridge.py)만 static 밖에서 제공
            safe_path = os.path.join(base_dir, force_name)
            in_scope = force_name in DOWNLOADABLE
        else:
            safe_path = os.path.normpath(os.path.join(static_dir, rel_path))
            in_scope = safe_path.startswith(static_dir + os.sep)

        # Security check to prevent directory traversal
        if not in_scope or not os.path.exists(safe_path) or os.path.isdir(safe_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        mime_type = force_type or mimetypes.guess_type(safe_path)[0]
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


_TERMUX_SCRIPT = r'''#!/usr/bin/env bash
# Blender MCP - Termux 원라인 설정 (PC의 Blender에 연결)
set -e
URL="@@URL@@"
TOKEN="@@TOKEN@@"
DIR="$HOME/.config/blender_mcp_chat"
mkdir -p "$DIR"

echo "[1/4] PC 서버 연결 확인: $URL"
curl -fsS --max-time 8 "$URL/api/status" >/dev/null || { echo "연결 실패: PC IP/포트, 방화벽(TCP @@PORT@@), Preferences의 'LAN 접속 허용'을 확인하세요."; exit 1; }

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "python이 필요합니다: pkg install python"; exit 1; }

echo "[2/4] MCP 브릿지 다운로드"
curl -fsS -H "Authorization: Bearer $TOKEN" "$URL/bridge.py" -o "$DIR/mcp_bridge.py"
chmod +x "$DIR/mcp_bridge.py"
umask 077
printf '{"url": "%s/mcp", "token": "%s"}\n' "$URL" "$TOKEN" > "$DIR/bridge.json"

echo "[3/4] Claude Code 등록"
if command -v claude >/dev/null 2>&1; then
  claude mcp remove blender -s user >/dev/null 2>&1 || true
  claude mcp add -s user blender -- "$PY" "$DIR/mcp_bridge.py" && echo "  claude: 등록 완료"
else
  echo "  claude 미설치 - 건너뜀"
fi

echo "[4/4] agy 등록"
"$PY" - "$DIR/mcp_bridge.py" <<'PYEND'
import json, os, sys
bridge = sys.argv[1]
d = os.path.expanduser("~/.gemini/config"); os.makedirs(d, exist_ok=True)
p = os.path.join(d, "mcp_config.json")
try:
    cfg = json.load(open(p, encoding="utf-8"))
except Exception:
    cfg = {}
cfg.setdefault("mcpServers", {})["blender"] = {"command": sys.executable, "args": [bridge]}
json.dump(cfg, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("  agy: 등록 완료 ->", p)
PYEND

echo "[5/5] Termux Agent 설치 (Blender APK가 Termux의 CLI를 실행하도록 중계)"
mkdir -p "$DIR/agent"
for f in termux_agent.py cli_runner.py guidelines.py; do
  curl -fsS -H "Authorization: Bearer $TOKEN" "$URL/dl/$f" -o "$DIR/agent/$f"
done
AGENT_TOKEN="$("$PY" "$DIR/agent/termux_agent.py" --init)"
# 재시작용 런처 (Termux 재시작/종료 후에는 이 파일을 실행)
cat > "$DIR/start_agent.sh" <<LAUNCH
#!/usr/bin/env bash
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
pkill -f termux_agent.py >/dev/null 2>&1 || true
nohup "$PY" "$DIR/agent/termux_agent.py" > "$DIR/agent.log" 2>&1 &
sleep 1
curl -fsS --max-time 3 http://127.0.0.1:8787/health >/dev/null && echo "Agent OK (127.0.0.1:8787)" || { echo "Agent 시작 실패. 로그:"; tail -n 20 "$DIR/agent.log"; }
LAUNCH
chmod +x "$DIR/start_agent.sh"
bash "$DIR/start_agent.sh"

echo "연결 점검:"
"$PY" "$DIR/mcp_bridge.py" --check
echo ""
echo "================================================================"
echo " Blender > Preferences > Add-ons > MCP Chat > Termux Agent 에 입력:"
echo "   URL  : http://127.0.0.1:8787"
echo "   토큰 : $AGENT_TOKEN"
echo " Termux를 닫았거나 재부팅했다면 먼저 실행: bash $DIR/start_agent.sh"
echo "================================================================"
'''


def build_termux_script(base_url: str, token: str) -> str:
    port = base_url.rsplit(":", 1)[-1]
    return _TERMUX_SCRIPT.replace("@@URL@@", base_url).replace("@@TOKEN@@", token).replace("@@PORT@@", port)


class BlenderServerManager:
    def __init__(self):
        self.server: Optional[ThreadedHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.port = 8000
        self.is_running = False

    def start(self, host=None, port=8000):
        if self.is_running:
            return True, f"Server is already running on port {self.port}"

        if host is None:
            allow_lan = str(session_mgr.get_setting("allow_lan", "false")).lower() == "true"
            host = "0.0.0.0" if allow_lan else "127.0.0.1"
            session_mgr.get_or_create_token()

        self.port = int(port)  # Preferences의 포트 설정을 그대로 사용
        
        # Ensure bridge timer is active inside Blender
        bridge.start_timer()

        try:
            self.server = ThreadedHTTPServer((host, self.port), BlenderMCPRequestHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.is_running = True
            task_queue.start() # Start task queue worker
            mode = "LAN 허용(토큰 인증)" if host == "0.0.0.0" else "로컬 전용"
            return True, f"Blender MCP Chat Server started on http://127.0.0.1:{self.port} [{mode}]"
        except (PermissionError, OSError) as e:
            # Fallback for Android/SELinux or restricted environments if 0.0.0.0 fails
            if host != "127.0.0.1":
                try:
                    self.server = ThreadedHTTPServer(("127.0.0.1", self.port), BlenderMCPRequestHandler)
                    self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
                    self.server_thread.start()
                    self.is_running = True
                    task_queue.start()
                    return True, f"Blender MCP Chat Server started on http://127.0.0.1:{self.port} (Fallback to localhost)"
                except Exception as inner_e:
                    self.is_running = False
                    return False, f"Failed to start server on port {self.port}: {str(inner_e)}"
            self.is_running = False
            return False, f"Failed to start server: {str(e)}"
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
