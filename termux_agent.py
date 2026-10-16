#!/usr/bin/env python3
"""
Termux Agent - Android 네이티브 Blender(APK)가 Termux의 claude / agy / codex CLI를 쓰기 위한 실행 대리자.

Blender(APK)는 앱 샌드박스 때문에 Termux 바이너리를 직접 실행할 수 없다.
이 에이전트가 Termux 안에서 127.0.0.1:8787 로 대기하다가 Blender의 요청을 받아 CLI를 실행하고 결과를 돌려준다.
(CLI -> Blender 제어는 기존 MCP 브릿지가 http://127.0.0.1:8000/mcp 로 연결)

Usage:
  python3 termux_agent.py --init      토큰 생성/표시 후 종료
  python3 termux_agent.py             서버 시작 (기본 127.0.0.1:8787)
  python3 termux_agent.py --port 9000 --host 127.0.0.1

보안: Bearer 토큰 필수(~/.config/blender_mcp_chat/agent_token), 기본 127.0.0.1 바인딩.
표준 라이브러리만 사용.
"""

import argparse
import hmac
import json
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli_runner import cli_runner  # noqa: E402

CONF_DIR = os.path.join(os.path.expanduser("~"), ".config", "blender_mcp_chat")
TOKEN_PATH = os.path.join(CONF_DIR, "agent_token")
ALLOWED_CLIS = {"claude", "agy", "codex"}
ALLOWED_MODES = {"CHAT", "PLAN", "AUTO"}


def load_token() -> str:
    os.makedirs(CONF_DIR, exist_ok=True)
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            tok = f.read().strip()
            if tok:
                return tok
    except Exception:
        pass
    tok = secrets.token_urlsafe(18)
    old = os.umask(0o077)
    try:
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(tok)
    finally:
        os.umask(old)
    return tok


TOKEN = ""


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        cand = auth[7:].strip() if auth.startswith("Bearer ") else ""
        return bool(cand) and hmac.compare_digest(cand.encode(), TOKEN.encode())

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {
                "ok": True,
                "claude": cli_runner.find_claude_cli(),
                "agy": cli_runner.find_agy_cli(),
                "codex": cli_runner.find_codex_cli(),
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/run":
            self._json(404, {"error": "not found"})
            return
        if self.headers.get("Origin"):  # 브라우저 발 요청 차단
            self._json(403, {"error": "forbidden"})
            return
        if not self._auth():
            self._json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._json(400, {"error": "bad request"})
            return

        cli = req.get("cli")
        mode = req.get("mode", "CHAT")
        if cli not in ALLOWED_CLIS or mode not in ALLOWED_MODES:
            self._json(400, {"error": "invalid cli/mode"})
            return
        opts = {k: str(v) for k, v in (req.get("opts") or {}).items() if isinstance(k, str)}
        image_paths = cli_runner.save_images([u for u in (req.get("images") or []) if isinstance(u, str)][:3])
        ok, out = cli_runner.run_local_sync(
            cli, str(req.get("prompt", "")), mode, opts, str(req.get("guidelines", "")),
            image_paths=image_paths
        )
        self._json(200, {"ok": ok, "output": out})


def main():
    global TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="토큰만 생성/출력")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()

    TOKEN = load_token()
    if args.init:
        print(TOKEN)
        return

    srv = Server((args.host, args.port), Handler)
    print(f"Termux Agent listening on http://{args.host}:{args.port}  (token: {TOKEN_PATH})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
