"""
MCP (Model Context Protocol) Handler
Implements JSON-RPC 2.0 protocol specifications for Claude Code, agy CLI, and other MCP clients.
Zero-dependency implementation.
"""

import json
from typing import Dict, Any, List
from blender_bridge import bridge

MCP_PROTOCOL_VERSION = "2024-11-05"

MCP_TOOLS = [
    {
        "name": "execute_blender_code",
        "description": "Execute arbitrary Python code in Blender's main thread. Direct access to bpy, mathutils, and context. Allows creating meshes, modifying materials, setting lights, animating, and rendering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code using bpy. Example: bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2)"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_scene_info",
        "description": "Inspect the active Blender scene: object hierarchy, positions, scales, active materials, and render settings.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "capture_viewport",
        "description": "Take a 3D viewport snapshot or render preview to visually inspect 3D assets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for taking the viewport snapshot"
                }
            }
        }
    },
    {
        "name": "enqueue_blender_task",
        "description": "Add a Python code execution or render task to the Blender background Task Queue. The task will be executed sequentially with the global delay and automatically saved (.blend & render image).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Descriptive title for the task (e.g. 'Build Base Room', 'Add Neon Materials')"
                },
                "code": {
                    "type": "string",
                    "description": "Python code using bpy to execute for this task"
                },
                "task_type": {
                    "type": "string",
                    "enum": ["code", "render"],
                    "description": "Task type (default: code)"
                }
            },
            "required": ["title", "code"]
        }
    },
    {
        "name": "get_queue_status",
        "description": "Check the status of the Blender background Task Queue: pending tasks count, active running task, global delay in seconds, and auto-save state.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "lookup_blender_skill",
        "description": "Lookup specialized Blender standard workflows, recipes, and verified bpy code snippets for cameras, lighting, materials, hard surface, rigging, physics, or game engine export.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords or intent describing the desired Blender workflow or recipe (e.g. 'turntable', 'unreal export', 'boolean cut', 'studio lighting')."
                },
                "domain": {
                    "type": "string",
                    "enum": ["environment", "character", "hard_surface", "materials", "rigging", "animation", "physics", "vfx", "camera_lighting", "pipeline_gamedev"],
                    "description": "Optional category/domain filter."
                }
            },
            "required": ["query"]
        }
    }
]


class MCPHandler:
    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming JSON-RPC request and return response."""
        jsonrpc = request_data.get("jsonrpc", "2.0")
        req_id = request_data.get("id")
        method = request_data.get("method")
        params = request_data.get("params", {})

        # Handle notifications (no id)
        if req_id is None:
            return None

        try:
            if method == "initialize":
                return {
                    "jsonrpc": jsonrpc,
                    "id": req_id,
                    "result": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {
                                "listChanged": False
                            }
                        },
                        "serverInfo": {
                            "name": "blender-mcp-server",
                            "version": "1.0.0"
                        }
                    }
                }

            elif method == "notifications/initialized":
                return None

            elif method == "ping":
                return {
                    "jsonrpc": jsonrpc,
                    "id": req_id,
                    "result": {}
                }

            elif method == "tools/list":
                return {
                    "jsonrpc": jsonrpc,
                    "id": req_id,
                    "result": {
                        "tools": MCP_TOOLS
                    }
                }

            elif method == "tools/call":
                tool_name = params.get("name")
                args = params.get("arguments", {})
                tool_result = self._execute_tool(tool_name, args)

                return {
                    "jsonrpc": jsonrpc,
                    "id": req_id,
                    "result": tool_result
                }

            else:
                return {
                    "jsonrpc": jsonrpc,
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

        except Exception as e:
            return {
                "jsonrpc": jsonrpc,
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            }

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "execute_blender_code":
            code = args.get("code", "")
            res = bridge.execute_python_code(code)
            
            output_text = []
            if res.get("stdout"):
                output_text.append(f"[STDOUT]\n{res['stdout']}")
            if res.get("stderr"):
                output_text.append(f"[STDERR]\n{res['stderr']}")
            if res.get("error"):
                output_text.append(f"[ERROR]\n{res['error']}\n{res.get('traceback', '')}")
            if not output_text:
                output_text.append("Code executed successfully (no stdout returned).")

            is_error = res.get("status") == "error"
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(output_text)
                    }
                ],
                "isError": is_error
            }

        elif name == "get_scene_info":
            res = bridge.get_scene_info()
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(res, indent=2, ensure_ascii=False)
                    }
                ],
                "isError": "error" in res
            }

        elif name == "capture_viewport":
            res = bridge.capture_viewport()
            if "image_base64" in res:
                # Extract pure base64 (without data:image/png;base64, prefix)
                raw_b64 = res["image_base64"].split(",", 1)[-1]
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Viewport snapshot captured: {res.get('filepath')}"
                        },
                        {
                            "type": "image",
                            "data": raw_b64,
                            "mimeType": "image/png"
                        }
                    ],
                    "isError": False
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to capture viewport: {res.get('error')}"
                        }
                    ],
                    "isError": True
                }

        elif name == "enqueue_blender_task":
            title = args.get("title", "Queued Task")
            code = args.get("code", "")
            task_type = args.get("task_type", "code")

            from session_manager import session_mgr
            from task_queue import task_queue

            task_queue.start() # Ensure queue worker is running
            created = session_mgr.enqueue_task(
                title=title,
                task_type=task_type,
                payload={"code": code}
            )

            status = task_queue.get_status()
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Task enqueued: '{title}' (ID: {created['id']})\nQueue: {status['counts']['pending']} pending, Delay between tasks: {status['delay_seconds']}s"
                    }
                ],
                "isError": False
            }

        elif name == "get_queue_status":
            from task_queue import task_queue
            status = task_queue.get_status()
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(status, indent=2, ensure_ascii=False)
                    }
                ],
                "isError": False
            }

        elif name == "lookup_blender_skill":
            try:
                from skill_manager import skill_mgr
                q = args.get("query", "")
                dom = args.get("domain")
                res = skill_mgr.tool_lookup(query=q, domain=dom)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res, indent=2, ensure_ascii=False)
                        }
                    ],
                    "isError": res.get("status") == "not_found"
                }
            except Exception as e:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error querying skills: {str(e)}"
                        }
                    ],
                    "isError": True
                }

        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Unknown tool: {name}"
                    }
                ],
                "isError": True
            }


# Singleton MCP handler
mcp_handler = MCPHandler()
