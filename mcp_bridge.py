#!/usr/bin/env python3
"""
MCP Stdio-to-HTTP Bridge
Cross-platform bridge for Claude Code and agy CLI (Windows, Android Termux, Linux, macOS).
Forwards JSON-RPC between stdio and Blender MCP HTTP Server (http://127.0.0.1:8000/mcp).
Zero dependencies.
"""

import sys
import json
import urllib.request
import urllib.error

ENDPOINT = "http://127.0.0.1:8000/mcp"

# Ensure UTF-8 I/O encoding on Windows and POSIX
if hasattr(sys.stdin, "buffer"):
    import io
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue

            # Parse incoming JSON-RPC line
            req_data = json.loads(line)
            req_bytes = json.dumps(req_data, ensure_ascii=False).encode("utf-8")

            # Forward to Blender MCP Add-on Server
            req = urllib.request.Request(
                ENDPOINT,
                data=req_bytes,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp_bytes = resp.read()
                    if resp_bytes:
                        sys.stdout.write(resp_bytes.decode("utf-8") + "\n")
                        sys.stdout.flush()
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": req_data.get("id"),
                    "error": {
                        "code": -32000,
                        "message": f"Blender MCP HTTP Error {e.code}: {err_body}"
                    }
                }
                sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": req_data.get("id"),
                    "error": {
                        "code": -32000,
                        "message": f"Failed to connect to Blender on {ENDPOINT}. Is Blender running with MCP Chat enabled? Details: {str(e)}"
                    }
                }
                sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()

        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"Bridge error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
