#!/usr/bin/env python3
"""
MCP Stdio-to-HTTP Bridge for Termux
Enables Claude Code and agy CLI to connect to the Blender MCP Add-on via standard stdio.
Zero dependencies (standard library only).

Usage in Termux (~/.claude.json):
{
  "mcpServers": {
    "blender": {
      "command": "python3",
      "args": ["/path/to/mcp_bridge.py"]
    }
  }
}
"""

import sys
import json
import urllib.request
import urllib.error

ENDPOINT = "http://127.0.0.1:8000/mcp"

def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue

            # Parse JSON-RPC line
            req_data = json.loads(line)
            req_bytes = json.dumps(req_data).encode("utf-8")

            # Forward to Blender MCP Add-on Server
            req = urllib.request.Request(
                ENDPOINT,
                data=req_bytes,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
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
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": req_data.get("id"),
                    "error": {
                        "code": -32000,
                        "message": f"Failed to connect to Blender on {ENDPOINT}. Is Blender running with the addon enabled? Details: {str(e)}"
                    }
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()

        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"Bridge loop error: {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
