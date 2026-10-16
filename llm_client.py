"""
Universal LLM Client for Blender MCP Chat
Compatible with OpenRouter, NVIDIA NIM, Ollama, LM Studio, and any OpenAI-compatible API.
Includes Blender tool definitions and multi-turn autonomous tool execution loops.
Implemented using Python's standard urllib for zero-dependency portability on ARM64 PRoot.
"""

import json
import urllib.request
import urllib.error
import ssl
from typing import List, Dict, Any, Optional, Callable
from blender_bridge import bridge

# Define tools available to LLM
BLENDER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_blender_code",
            "description": "Execute Python code directly inside Blender's main thread to create or modify 3D objects, meshes, materials, lighting, cameras, collections, or run animations. 'bpy' and 'mathutils' are pre-imported.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code using bpy. Example: bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0)"
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_scene_info",
            "description": "Retrieve comprehensive information about current Blender scene: objects list, types, coordinates, active selection, materials, and render settings.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_viewport",
            "description": "Takes a visual screenshot of the current 3D viewport or OpenGL frame in Blender. Use this to inspect and verify the visual outcome of your 3D modeling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why you want to capture the viewport."
                    }
                }
            }
        }
    }
]


class LLMClient:
    def __init__(self, provider_config: Dict[str, Any]):
        """
        provider_config:
            provider: 'openrouter' | 'nvidia_nim' | 'local' | 'custom'
            api_key: str
            model: str
            base_url: str (optional)
            reasoning_effort: 'low' | 'medium' | 'high' (optional)
            thinking_budget: int (optional)
            temperature: float (optional)
        """
        self.config = provider_config
        self.base_url, self.headers = self._resolve_endpoint()

    def _resolve_endpoint(self):
        provider = self.config.get("provider", "openrouter")
        api_key = self.config.get("api_key", "").strip()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Blender-MCP-Chat/1.0"
        }

        if provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"
            headers["HTTP-Referer"] = "https://github.com/mcp-chat-for-blender"
            headers["X-Title"] = "Blender MCP Chat Android"
        elif provider == "nvidia_nim":
            base_url = "https://integrate.api.nvidia.com/v1/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"
        elif provider == "local":
            custom_url = self.config.get("base_url") or "http://127.0.0.1:11434/v1"
            base_url = f"{custom_url.rstrip('/')}/chat/completions"
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        else: # custom
            custom_url = self.config.get("base_url") or "https://api.openai.com/v1"
            base_url = f"{custom_url.rstrip('/')}/chat/completions"
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

        return base_url, headers

    def format_history_for_api(self, system_prompt: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Formats stored database messages into OpenAI multimodal chat format."""
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            images = msg.get("images") or []
            tool_calls = msg.get("tool_calls")
            tool_call_id = msg.get("tool_call_id")

            if role == "user":
                if images:
                    content_parts = [{"type": "text", "text": content}]
                    for img in images:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": img}
                        })
                    api_messages.append({"role": "user", "content": content_parts})
                else:
                    api_messages.append({"role": "user", "content": content})

            elif role == "assistant":
                entry = {"role": "assistant", "content": content or ""}
                if tool_calls:
                    entry["tool_calls"] = tool_calls
                api_messages.append(entry)

            elif role == "tool":
                api_messages.append({
                    "role": "tool",
                    "content": content,
                    "tool_call_id": tool_call_id
                })

        return api_messages

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the tool in Blender and returns the result."""
        if tool_name == "execute_blender_code":
            code = arguments.get("code", "")
            res = bridge.execute_python_code(code)
            return res
        elif tool_name == "get_scene_info":
            res = bridge.get_scene_info()
            return res
        elif tool_name == "capture_viewport":
            res = bridge.capture_viewport()
            # Include summary and preview flag
            if "image_base64" in res:
                return {
                    "status": "success",
                    "message": "Viewport screenshot captured successfully.",
                    "image_base64": res["image_base64"]
                }
            return res
        else:
            return {"error": f"Unknown tool name: {tool_name}"}

    def chat_step(self, api_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Performs a single HTTP POST call to the chat completion endpoint."""
        model = self.config.get("model", "anthropic/claude-3.5-sonnet")
        temperature = float(self.config.get("temperature", 0.7))
        reasoning_effort = self.config.get("reasoning_effort")
        thinking_budget = self.config.get("thinking_budget")

        payload = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "tools": BLENDER_TOOLS,
            "tool_choice": "auto"
        }

        # Reasoning / Thinking parameters
        if reasoning_effort in ("low", "medium", "high"):
            payload["reasoning_effort"] = reasoning_effort

        if thinking_budget and str(thinking_budget).isdigit() and int(thinking_budget) > 0:
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": int(thinking_budget)
            }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base_url, data=data_bytes, headers=self.headers, method="POST")
        
        # SSL context ignoring self-signed errors if any for local LLM
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                resp_body = resp.read().decode("utf-8")
                return json.loads(resp_body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code} error from {self.base_url}: {err_body}")
        except Exception as e:
            raise RuntimeError(f"Connection error to {self.base_url}: {str(e)}")

    def run_agent_loop(self, 
                       system_prompt: str, 
                       messages: List[Dict[str, Any]], 
                       on_log_callback: Optional[Callable[[str, Any], None]] = None,
                       max_iterations: int = 6) -> Dict[str, Any]:
        """
        Autonomous tool execution loop.
        Calls LLM -> if tool_calls requested -> executes tool in Blender -> calls LLM again -> completes.
        """
        api_messages = self.format_history_for_api(system_prompt, messages)
        collected_tool_events = []
        captured_images = []

        for step in range(max_iterations):
            if on_log_callback:
                on_log_callback("status", f"AI thinking (Step {step + 1}/{max_iterations})...")

            response = self.chat_step(api_messages)
            choices = response.get("choices", [])
            if not choices:
                raise RuntimeError("No choices returned from LLM response.")

            choice = choices[0]
            message_obj = choice.get("message", {})
            role = message_obj.get("role", "assistant")
            content = message_obj.get("content") or ""
            reasoning = message_obj.get("reasoning_content") or message_obj.get("thought") or ""
            tool_calls = message_obj.get("tool_calls")

            # If there are tool calls, execute them
            if tool_calls:
                api_messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                })

                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    call_id = tc.get("id")
                    
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        args = {}

                    if on_log_callback:
                        on_log_callback("tool_call", {
                            "name": fn_name,
                            "arguments": args,
                            "call_id": call_id
                        })

                    # Execute in Blender
                    tool_result = self.execute_tool(fn_name, args)

                    # If tool captured an image, save for user visual presentation
                    if fn_name == "capture_viewport" and "image_base64" in tool_result:
                        captured_images.append(tool_result["image_base64"])

                    tool_event = {
                        "name": fn_name,
                        "arguments": args,
                        "result": tool_result,
                        "call_id": call_id
                    }
                    collected_tool_events.append(tool_event)

                    if on_log_callback:
                        on_log_callback("tool_result", tool_event)

                    # Append tool result to API history for next step
                    # Filter out base64 string from prompt text if huge to save tokens, only return summary
                    result_for_llm = dict(tool_result)
                    if "image_base64" in result_for_llm:
                        result_for_llm["image_base64"] = "[Image Captured and Displayed to User]"

                    api_messages.append({
                        "role": "tool",
                        "content": json.dumps(result_for_llm, ensure_ascii=False),
                        "tool_call_id": call_id
                    })

                # Loop continues to next iteration for model to synthesize response
                continue
            else:
                # No more tools needed, model produced final response
                return {
                    "content": content,
                    "thought": reasoning,
                    "tool_events": collected_tool_events,
                    "captured_images": captured_images
                }

        return {
            "content": content or "Max tool execution steps reached.",
            "thought": reasoning,
            "tool_events": collected_tool_events,
            "captured_images": captured_images
        }
