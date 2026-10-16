"""
Session and Configuration Manager
Uses Python's built-in sqlite3 database to persist chat sessions,
messages, multimodal attachments, and LLM provider configurations.
Zero external dependencies.
"""

import os
import json
import sqlite3
import time
import uuid
from typing import List, Dict, Any, Optional

DEFAULT_SYSTEM_PROMPT = """You are an expert 3D Artist and Blender Python automation assistant.
You have direct access to Blender tools via MCP / function calling:
- execute_blender_code: Execute Python code using bpy/mathutils to manipulate 3D scenes, create objects, adjust materials, lighting, cameras, or animation.
- get_scene_info: Inspect current objects, materials, active selection, and render settings.
- capture_viewport: Capture the current 3D viewport to inspect the visual results.

Guidelines:
1. When asked to create or modify 3D objects, write robust Python code using `bpy`.
2. Clean up or handle name collisions gracefully.
3. Keep code concise, safe, and explain your steps clearly.
4. If you need to verify what was created or rendered, capture the viewport image to evaluate the scene.
"""

class SessionManager:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            home = os.path.expanduser("~")
            data_dir = os.path.join(home, ".config", "blender_mcp_chat")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "chat_data.db")
        
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                system_prompt TEXT,
                model_name TEXT,
                provider TEXT,
                reasoning_effort TEXT
            )
            """)

            # Messages table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                images TEXT, -- JSON array of image URLs / base64
                thought TEXT, -- Reasoning / chain of thought
                tool_calls TEXT, -- JSON array
                tool_call_id TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
            """)

            # Config key-value store
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)

            conn.commit()

        # Initialize default configs if missing
        self._init_default_settings()

    def _init_default_settings(self):
        defaults = {
            "active_provider": "openrouter",
            "openrouter_api_key": "",
            "openrouter_model": "anthropic/claude-3.5-sonnet",
            "nvidia_nim_api_key": "",
            "nvidia_nim_model": "meta/llama-3.3-70b-instruct",
            "local_base_url": "http://127.0.0.1:11434/v1",
            "local_model": "qwen2.5-coder:latest",
            "custom_base_url": "",
            "custom_api_key": "",
            "custom_model": "",
            "reasoning_effort": "medium", # low | medium | high
            "thinking_budget": "2048",
            "temperature": "0.7",
            "port": "8000"
        }
        for k, v in defaults.items():
            if self.get_setting(k) is None:
                self.set_setting(k, v)

    # -------------------------------------------------------------
    # Settings Management
    # -------------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._get_connection() as conn:
            row = conn.cursor().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                return row["value"]
            return default

    def set_setting(self, key: str, value: Any):
        with self._get_connection() as conn:
            conn.cursor().execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            conn.commit()

    def get_all_settings(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            rows = conn.cursor().execute("SELECT key, value FROM settings").fetchall()
            return {r["key"]: r["value"] for r in rows}

    def update_settings(self, settings_dict: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for k, v in settings_dict.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (k, str(v) if v is not None else "")
                )
            conn.commit()

    # -------------------------------------------------------------
    # Sessions Management
    # -------------------------------------------------------------

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.cursor().execute(
                "SELECT id, title, created_at, updated_at, model_name, provider FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def create_session(self, title: str = "New Chat", model_name: Optional[str] = None, provider: Optional[str] = None) -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        now = time.time()
        
        provider = provider or self.get_setting("active_provider", "openrouter")
        if not model_name:
            if provider == "openrouter":
                model_name = self.get_setting("openrouter_model", "anthropic/claude-3.5-sonnet")
            elif provider == "nvidia_nim":
                model_name = self.get_setting("nvidia_nim_model", "meta/llama-3.3-70b-instruct")
            elif provider == "local":
                model_name = self.get_setting("local_model", "qwen2.5-coder:latest")
            else:
                model_name = self.get_setting("custom_model", "gpt-4o")

        reasoning = self.get_setting("reasoning_effort", "medium")

        with self._get_connection() as conn:
            conn.cursor().execute("""
                INSERT INTO sessions (id, title, created_at, updated_at, system_prompt, model_name, provider, reasoning_effort)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, title, now, now, DEFAULT_SYSTEM_PROMPT, model_name, provider, reasoning))
            conn.commit()

        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            s_row = conn.cursor().execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not s_row:
                return None
            session = dict(s_row)
            
            # Fetch messages
            m_rows = conn.cursor().execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,)
            ).fetchall()
            
            messages = []
            for m in m_rows:
                item = dict(m)
                if item.get("images"):
                    try:
                        item["images"] = json.loads(item["images"])
                    except Exception:
                        item["images"] = []
                else:
                    item["images"] = []
                
                if item.get("tool_calls"):
                    try:
                        item["tool_calls"] = json.loads(item["tool_calls"])
                    except Exception:
                        item["tool_calls"] = None
                messages.append(item)

            session["messages"] = messages
            return session

    def update_session_title(self, session_id: str, new_title: str):
        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (new_title, time.time(), session_id)
            )
            conn.commit()

    def update_session_model(self, session_id: str, model_name: str, provider: str, reasoning_effort: Optional[str] = None):
        with self._get_connection() as conn:
            if reasoning_effort:
                conn.cursor().execute(
                    "UPDATE sessions SET model_name = ?, provider = ?, reasoning_effort = ?, updated_at = ? WHERE id = ?",
                    (model_name, provider, reasoning_effort, time.time(), session_id)
                )
            else:
                conn.cursor().execute(
                    "UPDATE sessions SET model_name = ?, provider = ?, updated_at = ? WHERE id = ?",
                    (model_name, provider, time.time(), session_id)
                )
            conn.commit()

    def delete_session(self, session_id: str):
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.cursor().execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()

    # -------------------------------------------------------------
    # Messages Management
    # -------------------------------------------------------------

    def add_message(self, session_id: str, role: str, content: str, 
                    images: Optional[List[str]] = None, 
                    thought: Optional[str] = None, 
                    tool_calls: Optional[List[Dict[str, Any]]] = None,
                    tool_call_id: Optional[str] = None) -> Dict[str, Any]:
        msg_id = str(uuid.uuid4())
        now = time.time()
        images_json = json.dumps(images) if images else None
        tools_json = json.dumps(tool_calls) if tool_calls else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (id, session_id, role, content, images, thought, tool_calls, tool_call_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, session_id, role, content, images_json, thought, tools_json, tool_call_id, now))
            
            # Update session's updated_at
            cursor.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            conn.commit()

        return {
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "images": images or [],
            "thought": thought,
            "tool_calls": tool_calls,
            "tool_call_id": tool_call_id,
            "created_at": now
        }


# Global session manager instance
session_mgr = SessionManager()
