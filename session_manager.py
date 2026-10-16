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

def get_safe_data_dir() -> str:
    """
    Finds a reliable, writable directory across Windows, Android (Termux/PRoot), and Linux.
    Avoids Android permission errors (e.g. read-only root '/' or unpermitted ~/.config).
    """
    candidates = []

    # 1. Standard home directory (~/.config/blender_mcp_chat)
    try:
        home = os.path.expanduser("~")
        if home and home != "/" and os.path.exists(home):
            candidates.append(os.path.join(home, ".config", "blender_mcp_chat"))
    except Exception:
        pass

    # 2. Termux native storage
    if os.path.exists("/data/data/com.termux/files/home"):
        candidates.append("/data/data/com.termux/files/home/.config/blender_mcp_chat")

    # 3. Blender user resources directory (if running inside Blender)
    try:
        import bpy
        user_dir = bpy.utils.user_resource('DATAFILES', path='blender_mcp_chat', create=False)
        if user_dir:
            candidates.append(user_dir)
    except Exception:
        pass

    # 4. Standard system temp directory (/tmp/blender_mcp_chat or %TEMP%)
    import tempfile
    candidates.append(os.path.join(tempfile.gettempdir(), "blender_mcp_chat"))

    # Try each candidate until one can be created and written to
    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            test_file = os.path.join(c, ".perm_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            return c
        except Exception:
            continue

    # Absolute fallback to current addon directory
    return os.path.abspath(os.path.dirname(__file__))


class SessionManager:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            data_dir = get_safe_data_dir()
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

            # Task Queue table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                task_type TEXT NOT NULL, -- 'code' | 'prompt' | 'render'
                payload TEXT NOT NULL, -- JSON string
                status TEXT NOT NULL, -- 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
                output_blend TEXT,
                output_image TEXT,
                result_text TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                completed_at REAL
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
            "port": "8000",
            # Queue & Auto-save settings
            "queue_delay_seconds": "2.0",
            "auto_save_blend": "true",
            "auto_save_image": "true"
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
    # Tab Sessions Management (Stable 3-Tab Mapping & Renaming)
    # -------------------------------------------------------------

    def get_tab_session_id(self, tab_index: int) -> str:
        """Gets or creates the persistent session ID assigned to tab_index (0, 1, or 2)."""
        key = f"tab_{tab_index}_session_id"
        sid = self.get_setting(key)
        if sid:
            s = self.get_session(sid)
            if s:
                return sid
        # Create a new session for this tab slot
        new_s = self.create_session(f"세션 {tab_index + 1}")
        self.set_setting(key, new_s["id"])
        return new_s["id"]

    def set_tab_session(self, tab_index: int, session_id: str):
        """Assigns a session ID to a tab slot."""
        self.set_setting(f"tab_{tab_index}_session_id", session_id)

    def get_tab_sessions(self, max_tabs: int = 3) -> List[Dict[str, Any]]:
        """Returns the list of persistent sessions for the tabs (always stable slot order)."""
        tabs = []
        for i in range(max_tabs):
            sid = self.get_tab_session_id(i)
            s = self.get_session(sid)
            if not s:
                s = self.create_session(f"세션 {i + 1}")
                self.set_setting(f"tab_{i}_session_id", s["id"])
            tabs.append(s)
        return tabs

    def rename_tab_session(self, tab_index: int, new_title: str) -> bool:
        """Renames the session associated with the tab_index."""
        sid = self.get_tab_session_id(tab_index)
        self.update_session_title(sid, new_title)
        return True

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

    # -------------------------------------------------------------
    # Task Queue Management
    # -------------------------------------------------------------

    def enqueue_task(self, title: str, task_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = time.time()
        payload_str = json.dumps(payload, ensure_ascii=False)

        with self._get_connection() as conn:
            conn.cursor().execute("""
                INSERT INTO task_queue (id, title, task_type, payload, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (task_id, title, task_type, payload_str, now))
            conn.commit()

        return self.get_task(task_id)

    def enqueue_batch_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        created = []
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for t in tasks:
                t_id = str(uuid.uuid4())
                payload_str = json.dumps(t.get("payload", {}), ensure_ascii=False)
                cursor.execute("""
                    INSERT INTO task_queue (id, title, task_type, payload, status, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                """, (t_id, t.get("title", "Queued Task"), t.get("task_type", "code"), payload_str, now))
                created.append(t_id)
            conn.commit()
        return [self.get_task(tid) for tid in created]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.cursor().execute("SELECT * FROM task_queue WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload"])
            except Exception:
                pass
            return item

    def get_next_pending_task(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.cursor().execute(
                "SELECT * FROM task_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload"])
            except Exception:
                pass
            return item

    def update_task_status(self, task_id: str, status: str, 
                           output_blend: Optional[str] = None,
                           output_image: Optional[str] = None,
                           result_text: Optional[str] = None,
                           error: Optional[str] = None):
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status == "running":
                cursor.execute("UPDATE task_queue SET status = ?, started_at = ? WHERE id = ?", (status, now, task_id))
            elif status in ("completed", "failed", "cancelled"):
                cursor.execute("""
                    UPDATE task_queue 
                    SET status = ?, output_blend = ?, output_image = ?, result_text = ?, error = ?, completed_at = ?
                    WHERE id = ?",
                """, (status, output_blend, output_image, result_text, error, now, task_id))
            else:
                cursor.execute("UPDATE task_queue SET status = ? WHERE id = ?", (status, task_id))
            conn.commit()

    def list_queue_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.cursor().execute(
                "SELECT * FROM task_queue ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            result = []
            for r in rows:
                item = dict(r)
                try:
                    item["payload"] = json.loads(item["payload"])
                except Exception:
                    pass
                result.append(item)
            return result

    def clear_queue(self, status_filter: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status_filter:
                cursor.execute("DELETE FROM task_queue WHERE status = ?", (status_filter,))
            else:
                cursor.execute("DELETE FROM task_queue")
            conn.commit()

    def cancel_task(self, task_id: str):
        with self._get_connection() as conn:
            conn.cursor().execute("UPDATE task_queue SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (task_id,))
            conn.commit()


# Global session manager instance
session_mgr = SessionManager()


