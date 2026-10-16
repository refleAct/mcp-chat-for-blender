#!/usr/bin/env python3
"""
MCP Stdio-to-HTTP Bridge
Cross-platform bridge for Claude Code and agy CLI (Windows, Android Termux, Linux, macOS).
Forwards JSON-RPC between stdio and the Blender MCP HTTP Server.
Zero dependencies.

Connection settings (priority order):
  1. env  BLENDER_MCP_URL / BLENDER_MCP_TOKEN
  2. ~/.config/blender_mcp_chat/bridge.json  {"url": "...", "token": "..."}
  3. default http://127.0.0.1:8000/mcp (로컬 접속, 토큰 불필요)

Usage:  mcp_bridge.py           stdio bridge (MCP client가 실행)
        mcp_bridge.py --check   연결/토큰/도구 목록 점검
"""

import io
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "http://127.0.0.1:8000/mcp"


def load_config():
    url, token = DEFAULT_ENDPOINT, ""
    cfg_path = os.path.join(os.path.expanduser("~"), ".config", "blender_mcp_chat", "bridge.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        url = cfg.get("url") or url
        token = cfg.get("token") or token
    except Exception:
        pass
    return os.environ.get("BLENDER_MCP_URL", url), os.environ.get("BLENDER_MCP_TOKEN", token)


ENDPOINT, TOKEN = load_config()

# Ensure UTF-8 I/O encoding on Windows and POSIX
if hasattr(sys.stdin, "buffer"):
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def post(req_data, timeout=120):
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(req_data, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def error_response(req_id, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": message}}


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def check():
    print(f"endpoint: {ENDPOINT}")
    print(f"token   : {'set' if TOKEN else 'none (local connections only)'}")
    try:
        out = post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=10)
        tools = [t.get("name") for t in json.loads(out).get("result", {}).get("tools", [])]
        print("OK - tools:", ", ".join(tools) or "(none)")
        return 0
    except urllib.error.HTTPError as e:
        hint = " (token missing or wrong)" if e.code == 401 else ""
        print(f"FAIL - HTTP {e.code}{hint}")
    except Exception as e:
        print(f"FAIL - {e}\n  Check that Blender is running with the server started, the PC IP, the firewall (TCP port) and 'Allow LAN access'.")
    return 1


def main():
    if "--check" in sys.argv:
        sys.exit(check())

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                req_data = json.loads(line)
            except json.JSONDecodeError as e:
                emit(error_response(None, f"Invalid JSON: {e}"))
                continue

            try:
                out = post(req_data)
                if out:
                    sys.stdout.write(out.strip() + "\n")
                    sys.stdout.flush()
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")
                if req_data.get("id") is not None:
                    emit(error_response(req_data.get("id"), f"Blender MCP HTTP Error {e.code}: {body}"))
            except Exception as e:
                if req_data.get("id") is not None:
                    emit(error_response(req_data.get("id"), f"Failed to connect to Blender on {ENDPOINT}. Details: {e}"))
        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"Bridge error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
