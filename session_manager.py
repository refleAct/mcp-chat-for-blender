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
import secrets
try:
    import secrets_store
except ImportError:  # loaded as a package submodule
    from . import secrets_store
from typing import List, Dict, Any, Optional, Tuple

try:
    import guidelines as _g
    from guidelines import GUIDELINES, format_user_rules
except ImportError:  # loaded as a package submodule
    from . import guidelines as _g
    from .guidelines import GUIDELINES, format_user_rules

DEFAULT_SYSTEM_PROMPT = """You are an expert 3D Artist and Blender Python automation assistant.
You have direct access to Blender tools via MCP / function calling:
- execute_blender_code: Execute Python code using bpy/mathutils to manipulate 3D scenes, create objects, adjust materials, lighting, cameras, or animation.
- get_scene_info: Inspect current objects, materials, active selection, and render settings.
- capture_viewport: Capture the current 3D viewport to inspect the visual results.

""" + GUIDELINES

def build_default_system_prompt() -> str:
    """기본 시스템 프롬프트 = 역할 설명 + (사용자 수정 가능한) Blender Execution Rules."""
    return DEFAULT_SYSTEM_PROMPT.split("[Blender Execution Rules", 1)[0] + _g.get_guidelines()


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
        conn.execute("PRAGMA foreign_keys = ON")  # 세션 삭제 시 메시지 CASCADE 삭제
        conn.execute("PRAGMA busy_timeout = 10000")  # 워커/UI/서버 스레드 동시 접근 시 대기
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

            # 전송된 최종 프롬프트 / AI 계획 기록 (key = 메시지 id 또는 큐 작업 id)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_prompts (
                key TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """)

            # Config key-value store
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)

            # Migration: GLB output column
            _cols0 = [r[1] for r in cursor.execute("PRAGMA table_info(task_queue)").fetchall()]
            if "output_glb" not in _cols0:
                cursor.execute("ALTER TABLE task_queue ADD COLUMN output_glb TEXT")

            # Migration: queue ordering column
            cols = [r[1] for r in cursor.execute("PRAGMA table_info(task_queue)").fetchall()]
            if "position" not in cols:
                cursor.execute("ALTER TABLE task_queue ADD COLUMN position REAL")
                cursor.execute("UPDATE task_queue SET position = created_at WHERE position IS NULL")

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
            "queue_delay_seconds": "60",
            "auto_save_blend": "true",
            "auto_save_image": "true",
            # LAN (Termux 등 외부 기기) 접속: 기본은 로컬 전용
            "allow_lan": "false"
        }
        for k, v in defaults.items():
            if k in secrets_store.SECRET_KEYS:
                continue   # 비밀값은 암호화 금고에만 저장
            if self.get_setting(k) is None:
                self.set_setting(k, v)
        self._migrate_secrets()

    def _migrate_secrets(self):
        """이전 버전이 DB에 평문으로 저장한 키/토큰을 암호화 금고로 옮기고 DB에서 제거."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            for key in secrets_store.SECRET_KEYS:
                row = cur.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
                if row is None:
                    continue
                if row["value"] and not secrets_store.has(key):
                    secrets_store.set(key, row["value"])
                cur.execute("DELETE FROM settings WHERE key = ?", (key,))
            conn.commit()

    # -------------------------------------------------------------
    # Settings Management
    # -------------------------------------------------------------

    def set_sent_prompt(self, key: str, text: str):
        with self._get_connection() as conn:
            conn.cursor().execute(
                "INSERT OR REPLACE INTO sent_prompts (key, text, created_at) VALUES (?, ?, ?)",
                (key, text, time.time())
            )
            conn.commit()

    def append_sent_prompt(self, key: str, text: str):
        old = self.get_sent_prompt(key) or ""
        self.set_sent_prompt(key, old + text)

    def get_sent_prompt(self, key: str) -> Optional[str]:
        with self._get_connection() as conn:
            row = conn.cursor().execute("SELECT text FROM sent_prompts WHERE key = ?", (key,)).fetchone()
            return row["text"] if row else None

    # 검토 대기 중인 Plan (세션당 1개). sent_prompts 테이블을 재사용한다.
    def set_pending_plan(self, session_id: str, data: Dict[str, Any]):
        self.set_sent_prompt("pending_plan:" + session_id, json.dumps(data, ensure_ascii=False))

    def get_pending_plan(self, session_id: str) -> Optional[Dict[str, Any]]:
        raw = self.get_sent_prompt("pending_plan:" + session_id)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def clear_pending_plan(self, session_id: str):
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM sent_prompts WHERE key = ?", ("pending_plan:" + session_id,))
            conn.commit()

    def sent_prompt_keys(self) -> set:
        with self._get_connection() as conn:
            return {r["key"] for r in conn.cursor().execute("SELECT key FROM sent_prompts").fetchall()}

    def get_user_rules_block(self) -> str:
        """사용자 작업 지침 블록 (저장된 설정 'user_rules' 기반)."""
        try:
            return format_user_rules(self.get_setting("user_rules", "") or "")
        except Exception:
            return ""

    def get_or_create_token(self) -> str:
        """LAN 접속용 Bearer 토큰 (최초 1회 자동 생성)."""
        tok = self.get_setting("mcp_token", "")
        if not tok:
            tok = secrets.token_urlsafe(18)
            self.set_setting("mcp_token", tok)
        return tok

    def regenerate_token(self) -> str:
        tok = secrets.token_urlsafe(18)
        self.set_setting("mcp_token", tok)
        return tok

    def get_setting(self, key: str, default: Any = None) -> Any:
        if key in secrets_store.SECRET_KEYS:
            return secrets_store.get(key, default if default is not None else "")
        with self._get_connection() as conn:
            row = conn.cursor().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                return row["value"]
            return default

    def set_setting(self, key: str, value: Any):
        if key in secrets_store.SECRET_KEYS:
            secrets_store.set(key, "" if value is None else str(value))
            return
        with self._get_connection() as conn:
            conn.cursor().execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            conn.commit()

    def get_all_settings(self, include_secrets: bool = False) -> Dict[str, Any]:
        """include_secrets=False(기본): 키/토큰은 마스킹('********')하거나 빈 값으로 반환."""
        with self._get_connection() as conn:
            rows = conn.cursor().execute("SELECT key, value FROM settings").fetchall()
            out = {r["key"]: r["value"] for r in rows if r["key"] not in secrets_store.SECRET_KEYS}
        for key in secrets_store.SECRET_KEYS:
            val = secrets_store.get(key, "")
            out[key] = val if include_secrets else (secrets_store.MASK if val else "")
        return out

    def update_settings(self, settings_dict: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for k, v in settings_dict.items():
                if k in secrets_store.SECRET_KEYS:
                    # 빈 값/마스크는 '변경 없음'. 새 값이면 금고에 저장.
                    if v and v != secrets_store.MASK:
                        secrets_store.set(k, str(v))
                    continue
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

    def get_session(self, session_id: str, with_messages: bool = True) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            s_row = conn.cursor().execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not s_row:
                return None
            session = dict(s_row)

            if not with_messages:
                # 패널 draw 등 가벼운 조회용: 메시지(이미지 base64 포함) 로딩 생략
                session["messages"] = []
                return session

            # 기본 프롬프트 기반 세션은 항상 '현재 규칙'(사용자 수정 규칙 포함)으로 동적 생성
            sp = session.get("system_prompt") or ""
            if "Critical Guidelines" in sp or sp.startswith("You are an expert 3D Artist"):
                session["system_prompt"] = build_default_system_prompt()

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
            session["system_prompt"] = (session.get("system_prompt") or "") + self.get_user_rules_block()
            return session

    def compact_session(self, session_id: str, summarizer, keep_last: int = 4) -> int:
        """
        오래된 메시지를 한 개의 요약 메시지로 압축 (최근 keep_last개는 그대로 유지).
        summarizer(text, role) -> 한 줄 요약. 압축된 메시지 수를 반환(0이면 변경 없음).
        """
        session = self.get_session(session_id)
        if not session:
            return 0
        msgs = [m for m in session["messages"] if m["role"] in ("user", "assistant")]
        if len(msgs) <= keep_last + 1:
            return 0
        old = msgs[:-keep_last]
        first_kept = msgs[-keep_last]
        lines = []
        for m in old:
            who = "You" if m["role"] == "user" else "AI"
            lines.append(f"• {who}: {summarizer(m['content'], m['role'])}")
        summary = f"📦 이전 대화 요약 ({len(old)}개 메시지)\n" + "\n".join(lines)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.executemany("DELETE FROM messages WHERE id = ?", [(m["id"],) for m in old])
            cur.execute(
                "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, 'assistant', ?, ?)",
                (str(uuid.uuid4()), session_id, summary, first_kept["created_at"] - 0.001),
            )
            conn.commit()
        return len(old)

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
    # 1 to 3 Dynamic Session Tabs Management
    # -------------------------------------------------------------

    def get_tab_sessions(self, max_tabs: int = 3) -> List[Dict[str, Any]]:
        """Returns the list of active tab sessions (1 to 3). Initially only 1 session."""
        raw = self.get_setting("tab_session_ids", "")
        tab_ids = []
        if raw:
            try:
                tab_ids = json.loads(raw)
            except Exception:
                tab_ids = []

        # Validate that sessions exist in DB
        valid_sessions = []
        for sid in tab_ids:
            s = self.get_session(sid, with_messages=False)
            if s and s not in valid_sessions:
                valid_sessions.append(s)

        # If no valid sessions exist, initialize with exactly 1 session
        if not valid_sessions:
            all_s = self.list_sessions()
            first_s = all_s[0] if all_s else self.create_session("세션 1")
            valid_sessions = [first_s]
            self.set_setting("tab_session_ids", json.dumps([first_s["id"]]))

        # Limit to max_tabs (up to 3)
        valid_sessions = valid_sessions[:max_tabs]
        current_ids = [s["id"] for s in valid_sessions]
        if current_ids != tab_ids:
            self.set_setting("tab_session_ids", json.dumps(current_ids))

        return valid_sessions

    def get_tab_session_id(self, tab_index: int) -> str:
        """Returns the session ID for the given tab index."""
        tabs = self.get_tab_sessions(3)
        if 0 <= tab_index < len(tabs):
            return tabs[tab_index]["id"]
        return tabs[0]["id"] if tabs else ""

    def add_tab_session(self, title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Adds a new session tab (up to 3 max)."""
        tabs = self.get_tab_sessions(3)
        if len(tabs) >= 3:
            return None
        new_title = title or f"세션 {len(tabs) + 1}"
        new_s = self.create_session(new_title)
        new_ids = [s["id"] for s in tabs] + [new_s["id"]]
        self.set_setting("tab_session_ids", json.dumps(new_ids))
        return new_s

    def delete_tab_session(self, tab_index: int) -> Tuple[bool, str]:
        """Deletes session tab. If only 1 tab left, clears conversation instead."""
        tabs = self.get_tab_sessions(3)
        if not (0 <= tab_index < len(tabs)):
            return False, ""

        target = tabs[tab_index]
        if len(tabs) <= 1:
            # Clear chat history of the only session
            self.delete_session(target["id"])
            fresh_s = self.create_session("세션 1")
            self.set_setting("tab_session_ids", json.dumps([fresh_s["id"]]))
            return True, fresh_s["id"]
        else:
            self.delete_session(target["id"])
            remaining_ids = [s["id"] for i, s in enumerate(tabs) if i != tab_index]
            self.set_setting("tab_session_ids", json.dumps(remaining_ids))
            next_idx = max(0, tab_index - 1)
            next_sid = remaining_ids[next_idx]
            return True, next_sid

    def rename_tab_session(self, tab_index: int, new_title: str) -> bool:
        """Renames the session associated with the tab_index."""
        sid = self.get_tab_session_id(tab_index)
        if sid:
            self.update_session_title(sid, new_title)
            return True
        return False

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
                INSERT INTO task_queue (id, title, task_type, payload, status, created_at, position)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """, (task_id, title, task_type, payload_str, now, now))
            conn.commit()

        return self.get_task(task_id)

    def enqueue_batch_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        created = []
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for i, t in enumerate(tasks):
                t_id = str(uuid.uuid4())
                payload_str = json.dumps(t.get("payload", {}), ensure_ascii=False)
                cursor.execute("""
                    INSERT INTO task_queue (id, title, task_type, payload, status, created_at, position)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """, (t_id, t.get("title", "Queued Task"), t.get("task_type", "code"), payload_str, now, now + i * 0.001))
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
                "SELECT * FROM task_queue WHERE status = 'pending' ORDER BY position ASC, created_at ASC LIMIT 1"
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
                           error: Optional[str] = None,
                           output_glb: Optional[str] = None):
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status == "running":
                cursor.execute("UPDATE task_queue SET status = ?, started_at = ? WHERE id = ?", (status, now, task_id))
            elif status in ("completed", "failed", "cancelled"):
                cursor.execute("""
                    UPDATE task_queue 
                    SET status = ?, output_blend = ?, output_image = ?, output_glb = ?, result_text = ?, error = ?, completed_at = ?
                    WHERE id = ?
                """, (status, output_blend, output_image, output_glb, result_text, error, now, task_id))
            else:
                cursor.execute("UPDATE task_queue SET status = ? WHERE id = ?", (status, task_id))
            conn.commit()

    def list_queue_tasks(self, limit: int = 50, light: bool = False) -> List[Dict[str, Any]]:
        """light=True: payload(이미지 base64 포함)와 result_text를 읽지 않는다 (패널 draw 용)."""
        cols = ("id, title, task_type, status, output_blend, output_image, output_glb, error, "
                "created_at, started_at, completed_at, position") if light else "*"
        with self._get_connection() as conn:
            rows = conn.cursor().execute(
                f"SELECT {cols} FROM task_queue ORDER BY position ASC, created_at ASC LIMIT ?", (limit,)
            ).fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if not light:
                    try:
                        item["payload"] = json.loads(item["payload"])
                    except Exception:
                        pass
                result.append(item)
            return result

    def queue_counts(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            rows = conn.cursor().execute("SELECT status, COUNT(*) AS n FROM task_queue GROUP BY status").fetchall()
        counts = {r["status"]: r["n"] for r in rows}
        counts["total"] = sum(counts.values())
        return counts

    def recover_interrupted_tasks(self) -> int:
        """Blender 종료 등으로 'running'에 멈춘 작업을 실패 처리한다."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE task_queue SET status = 'failed', error = '중단됨 (이전 세션에서 종료)' WHERE status = 'running'")
            conn.commit()
            return cur.rowcount

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

    def delete_task(self, task_id: str):
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM task_queue WHERE id = ?", (task_id,))
            conn.commit()

    def update_task_payload(self, task_id: str, title: str, text: str):
        task = self.get_task(task_id)
        if not task:
            return
        payload = task.get("payload", {})
        if task.get("task_type") == "prompt":
            payload["prompt"] = text
        else:
            payload["code"] = text
        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE task_queue SET title = ?, payload = ? WHERE id = ?",
                (title, json.dumps(payload, ensure_ascii=False), task_id)
            )
            conn.commit()

    def retry_task(self, task_id: str):
        """Re-queues a failed/cancelled/completed task at the end of the queue."""
        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE task_queue SET status = 'pending', error = NULL, position = ?, "
                "started_at = NULL, completed_at = NULL WHERE id = ? AND status != 'running'",
                (time.time(), task_id)
            )
            conn.commit()

    def duplicate_task(self, task_id: str):
        task = self.get_task(task_id)
        if task:
            return self.enqueue_task(task["title"] + " (복제)", task["task_type"], task.get("payload", {}))

    def move_task(self, task_id: str, direction: int):
        """Moves a pending task up (-1) or down (+1) among pending tasks by swapping positions."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT id, position FROM task_queue WHERE status = 'pending' ORDER BY position ASC, created_at ASC"
            ).fetchall()
            ids = [r["id"] for r in rows]
            if task_id not in ids:
                return False
            i = ids.index(task_id)
            j = i + (-1 if direction < 0 else 1)
            if j < 0 or j >= len(ids):
                return False
            pi, pj = rows[i]["position"], rows[j]["position"]
            if pi == pj:
                pj = pi + (0.0005 if direction > 0 else -0.0005)
                cur.execute("UPDATE task_queue SET position = ? WHERE id = ?", (pj, ids[i]))
            else:
                cur.execute("UPDATE task_queue SET position = ? WHERE id = ?", (pj, ids[i]))
                cur.execute("UPDATE task_queue SET position = ? WHERE id = ?", (pi, ids[j]))
            conn.commit()
            return True


# Global session manager instance
session_mgr = SessionManager()
_g.set_custom_provider(lambda: session_mgr.get_setting("custom_guidelines", ""))


