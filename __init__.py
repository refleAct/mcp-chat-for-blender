bl_info = {
    "name": "MCP Chat for Blender (Android & Termux & PC)",
    "author": "refleaction",
    "version": (0, 8, 3),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > MCP Chat",
    "description": "Embedded In-Blender Chat with 3 Session Tabs, Up to 3 Images, 8-row Scroll, Plan/Auto Mode, Claude Code & agy CLI Integration",
    "category": "3D View",
}

import os
import sys
import webbrowser
import threading
import mimetypes
import base64
import json
import re
import textwrap
import unicodedata
import uuid
import tempfile
import bpy
import bpy.utils.previews
from bpy.props import (
    IntProperty, BoolProperty, StringProperty, EnumProperty, FloatProperty, CollectionProperty
)
from bpy.types import Panel, Operator, AddonPreferences, UIList, PropertyGroup, Menu
from bpy_extras.io_utils import ImportHelper

import importlib

# Ensure current addon directory is in sys.path
addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.append(addon_dir)

# Forcibly reload submodules on Blender 'Reload Scripts' (bpy.ops.script.reload)
_submodules = [
    "updater",
    "secrets_store",
    "i18n",
    "guidelines",
    "session_manager",
    "blender_bridge",
    "task_queue",
    "cli_runner",
    "llm_client",
    "server",
    "mcp_handler",
]
for _mod in _submodules:
    if _mod in sys.modules:
        try:
            importlib.reload(sys.modules[_mod])
        except Exception:
            pass

import server
import session_manager
import blender_bridge
import task_queue as tq_mod
import cli_runner
import llm_client
import i18n
import secrets_store
import updater
import guidelines
import shutil
from i18n import tr

server_mgr = server.server_mgr
session_mgr = session_manager.session_mgr
bridge = blender_bridge.bridge
task_queue = tq_mod.task_queue
cli_runner = cli_runner.cli_runner
LLMClient = llm_client.LLMClient

MAX_HISTORY_ITEMS = 200
DETAIL_WRAP_WIDTH = 46
SUMMARY_MAX_LEN = 220
SUMMARY_WRAP_WIDTH = 42
SUMMARY_MAX_LINES = 5
HISTORY_ROWS = 5   # 채팅 히스토리에 한 번에 보이는 줄 수 (넘치면 스크롤)
LINE_WRAP_WIDTH = 36
MAX_EXPANDED_LINES = 80
CLI_ENGINES = {
    'CLAUDE': ('claude', 'Claude Code'),
    'AGY': ('agy', 'agy CLI'),
    'CODEX': ('codex', 'Codex CLI'),
}


# ==============================================================================
# i18n: 레이아웃 프록시(text 자동 번역) + 번역되는 report()
# ==============================================================================

_TL_CHILD = {"row", "column", "box", "split", "column_flow", "grid_flow"}
_TL_TEXT = {"label", "operator", "prop", "menu", "popover"}


class TL:
    """UILayout 프록시: label/operator/prop/menu 의 text를 현재 언어로 번역한다."""
    __slots__ = ("_l",)

    def __init__(self, layout):
        object.__setattr__(self, "_l", layout)

    def __getattr__(self, name):
        attr = getattr(self._l, name)
        if name in _TL_CHILD:
            return lambda *a, **k: TL(attr(*a, **k))
        if name in _TL_TEXT:
            def _wrapped(*a, **k):
                if "text" in k:
                    k["text"] = tr(k["text"])
                elif name == "prop" and len(a) >= 2:
                    try:
                        pname = a[0].bl_rna.properties[a[1]].name
                        tname = tr(pname)
                        if tname != pname:
                            k["text"] = tname
                    except Exception:
                        pass
                return attr(*a, **k)
            return _wrapped
        return attr

    def __setattr__(self, name, value):
        setattr(self._l, name, value)


def tl(layout):
    return layout if isinstance(layout, TL) else TL(layout)


class TOp(Operator):
    """report() 메시지를 현재 언어로 번역하는 Operator 베이스 (직접 등록되지 않음)."""

    def report(self, type, message):
        super().report(type, tr(message))


# ==============================================================================
# Property Groups for Messages and Image Attachments
# ==============================================================================

class MCPChatMessageItem(PropertyGroup):
    role: StringProperty() # 'user' | 'assistant'
    content: StringProperty() # Single line summary for UIList
    full_text: StringProperty() # Full multi-line content
    img_count: IntProperty(default=0)
    expanded: BoolProperty(default=False)
    msg_id: StringProperty()
    has_prompt: BoolProperty(default=False)


class MCPChatLineItem(PropertyGroup):
    """채팅 히스토리의 표시용 한 줄 (메시지를 줄바꿈하여 UIList 행으로 펼친 것)"""
    role: StringProperty()
    text: StringProperty()
    msg_index: IntProperty(default=-1)
    first: BoolProperty(default=False)       # 메시지의 첫 줄 (아이콘/버튼 표시)
    expandable: BoolProperty(default=False)
    expanded: BoolProperty(default=False)
    msg_id: StringProperty()
    has_prompt: BoolProperty(default=False)


class MCPChatAttachedImage(PropertyGroup):
    name: StringProperty()
    path: StringProperty()
    is_viewport: BoolProperty(default=False)
    data_b64: StringProperty()
    preview_key: StringProperty()


# ==============================================================================
# Preferences
# ==============================================================================

def _sync_pref(key):
    def _updater(self, context):
        try:
            val = getattr(self, key)
            if key in secrets_store.SECRET_KEYS:
                # 비밀값: 암호화 금고에 저장하고 Blender 사용자 설정에는 남기지 않는다 (쓰기 전용 입력칸)
                if val:
                    session_mgr.set_setting(key, val)
                    setattr(self, key, "")
                return
            session_mgr.set_setting(key, val)
        except Exception:
            pass
    return _updater


def _secret_row(layout, prefs, prop):
    """저장된 비밀값은 '저장됨 (암호화)' + 삭제 버튼, 없으면 입력칸을 표시."""
    if secrets_store.has(prop):
        name = prefs.bl_rna.properties[prop].name
        row = layout.row(align=True)
        row.label(text=f"{name}: 저장됨 (암호화)", icon='LOCKED')
        op = row.operator("mcpchat.delete_secret", text="", icon='TRASH')
        op.name = prop
    else:
        layout.prop(prefs, prop)


# 엔진별 지원 모델 (드롭다운). 목록에 없는 모델은 '직접 입력'으로 지정.
CLI_MODEL_ITEMS = {
    "claude": [
        ("opus", "Opus", "claude --model opus (latest alias)"),
        ("sonnet", "Sonnet", "claude --model sonnet (latest alias)"),
        ("haiku", "Haiku", "claude --model haiku (latest alias)"),
        ("claude-opus-5-5", "Opus 5.5", "claude-opus-5-5"),
        ("claude-sonnet-5-5", "Sonnet 5.5", "claude-sonnet-5-5"),
        ("claude-haiku-5-5", "Haiku 5.5", "claude-haiku-5-5"),
        ("claude-fable-5-1", "Fable 5.1", "claude-fable-5-1"),
        ("CUSTOM", "Custom...", "Model ID not in the list"),
    ],
    "codex": [
        ("DEFAULT", "Codex default", "Use the default model from the Codex CLI config"),
        ("gpt-5-codex", "gpt-5-codex", "gpt-5-codex"),
        ("gpt-5", "gpt-5", "gpt-5"),
        ("o3", "o3", "o3"),
        ("o4-mini", "o4-mini", "o4-mini"),
        ("CUSTOM", "Custom...", "Model ID not in the list"),
    ],
    "agy": [
        ("gemini-3.8-flash-low", "Gemini 3.8 Flash (Low)", "gemini-3.8-flash-low"),
        ("gemini-3.8-flash", "Gemini 3.8 Flash", "gemini-3.8-flash"),
        ("gemini-3.8-pro", "Gemini 3.8 Pro", "gemini-3.8-pro"),
        ("CUSTOM", "Custom...", "Model ID not in the list"),
    ],
}


def _scene_value(scene, key):
    """settings 키에 대응하는 씬 값 (모델은 드롭다운/직접입력을 합산한 실제 모델 ID)."""
    for cli in CLI_MODEL_ITEMS:
        if key == f"cli_{cli}_model":
            sel = getattr(scene, f"mcpchat_{cli}_model_sel", "")
            if sel == "CUSTOM":
                return (getattr(scene, f"mcpchat_{cli}_model", "") or "").strip()
            return "" if sel == "DEFAULT" else sel
    val = getattr(scene, _SCENE_KEYS[key])
    if isinstance(val, bool):
        val = "true" if val else "false"
    return val


def _apply_language(prefs):
    """언어 설정 적용 + 모든 영역 다시 그리기."""
    try:
        i18n.set_language(prefs.ui_language, getattr(bpy.app.translations, "locale", "") or "")
        i18n._cache.clear()
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()
    except Exception:
        pass


def _sync_scene_setting(key):
    """씬(N패널) 속성 변경 -> settings DB 반영 (cli_runner가 읽음)."""
    def _updater(self, context):
        try:
            session_mgr.set_setting(key, _scene_value(self, key))
        except Exception:
            pass
    return _updater


# settings key -> scene property name
_SCENE_KEYS = {
    "cli_claude_model": "mcpchat_claude_model",
    "cli_claude_effort": "mcpchat_claude_effort",
    "cli_agy_model": "mcpchat_agy_model",
    "cli_agy_effort": "mcpchat_agy_effort",
    "cli_codex_model": "mcpchat_codex_model",
    "cli_codex_effort": "mcpchat_codex_effort",
    "auto_save_blend": "mcpchat_auto_save_blend",
    "auto_save_image": "mcpchat_auto_save_image",
    "auto_save_pack": "mcpchat_auto_save_pack",
    "auto_save_glb": "mcpchat_auto_save_glb",
    "output_dir": "mcpchat_output_dir",
}


class MCPChatPreferences(AddonPreferences):
    bl_idname = __name__

    default_port: IntProperty(
        name="Server Port",
        description="Port for embedded Web & MCP Server",
        default=8000,
        min=1024,
        max=65535
    )

    autostart: BoolProperty(
        name="Auto-start Server",
        description="Automatically start server on Blender launch",
        default=True
    )

    # Direct API Configuration
    active_provider: EnumProperty(
        name="API Provider",
        description="Direct API 서비스 제공자 선택",
        items=[
            ('openrouter', "OpenRouter", "OpenRouter AI (Claude, GPT-4, Llama 3, DeepSeek)"),
            ('nvidia_nim', "NVIDIA NIM", "NVIDIA NIM Cloud API (Nemotron, Llama 3)"),
            ('local', "Local / Ollama", "Local Ollama or LM Studio OpenAI API"),
            ('custom', "Custom Endpoint", "사용자 정의 OpenAI 호환 엔드포인트"),
        ],
        default='openrouter',
        update=_sync_pref("active_provider")
    )

    openrouter_api_key: StringProperty(
        name="OpenRouter API Key",
        description="sk-or-v1-...",
        subtype='PASSWORD',
        default="",
        update=_sync_pref("openrouter_api_key")
    )
    openrouter_model: StringProperty(
        name="OpenRouter Model",
        description="모델 ID (예: anthropic/claude-3.5-sonnet)",
        default="anthropic/claude-3.5-sonnet",
        update=_sync_pref("openrouter_model")
    )

    nvidia_nim_api_key: StringProperty(
        name="NVIDIA NIM API Key",
        description="nvapi-...",
        subtype='PASSWORD',
        default="",
        update=_sync_pref("nvidia_nim_api_key")
    )
    nvidia_nim_model: StringProperty(
        name="NVIDIA NIM Model",
        description="모델 ID (예: meta/llama-3.3-70b-instruct, nvidia/nemotron-3-super-120b-a12b)",
        default="meta/llama-3.3-70b-instruct",
        update=_sync_pref("nvidia_nim_model")
    )

    local_base_url: StringProperty(
        name="Local Base URL",
        description="Ollama 기본 URL (예: http://127.0.0.1:11434/v1)",
        default="http://127.0.0.1:11434/v1",
        update=_sync_pref("local_base_url")
    )
    local_model: StringProperty(
        name="Local Model",
        description="로컬 모델 이름 (예: qwen2.5-coder:latest)",
        default="qwen2.5-coder:latest",
        update=_sync_pref("local_model")
    )

    custom_base_url: StringProperty(
        name="Custom Base URL",
        default="",
        update=_sync_pref("custom_base_url")
    )
    custom_api_key: StringProperty(
        name="Custom API Key",
        subtype='PASSWORD',
        default="",
        update=_sync_pref("custom_api_key")
    )
    custom_model: StringProperty(
        name="Custom Model",
        default="",
        update=_sync_pref("custom_model")
    )

    reasoning_effort: EnumProperty(
        name="Reasoning Effort",
        items=[
            ('low', "Low", "낮은 추론 강도"),
            ('medium', "Medium", "보통 추론 강도"),
            ('high', "High", "높은 추론 강도"),
        ],
        default='medium',
        update=_sync_pref("reasoning_effort")
    )

    thinking_budget: IntProperty(
        name="Thinking Budget",
        description="추론 토큰 예산",
        default=2048,
        min=0,
        max=32768,
        update=_sync_pref("thinking_budget")
    )

    ui_language: EnumProperty(
        name="Language / 언어 / 言語 / 语言",
        description="Add-on UI language",
        items=[
            ('AUTO', "Auto (Blender)", "Follow Blender's interface language"),
            ('ko', "한국어", "Korean"),
            ('en', "English", "English"),
            ('zh', "中文", "Chinese (Simplified)"),
            ('ja', "日本語", "Japanese"),
        ],
        default='AUTO',
        update=lambda self, ctx: _apply_language(self)
    )

    cli_remote_url: StringProperty(
        name="Agent URL",
        description="Termux Agent 주소. Blender가 Android APK일 때 설정 (비우면 PC처럼 로컬 실행 우선). 예: http://127.0.0.1:8787",
        default="",
        update=_sync_pref("cli_remote_url")
    )
    cli_remote_token: StringProperty(
        name="Agent 토큰",
        description="Termux에서 설치 스크립트가 출력한 토큰",
        subtype='PASSWORD',
        default="",
        update=_sync_pref("cli_remote_token")
    )

    allow_lan: BoolProperty(
        name="LAN 접속 허용 (Termux/모바일)",
        description="같은 네트워크의 기기(안드로이드 Termux 등)가 이 PC의 Blender에 접속하도록 허용. 토큰 인증 필수. 변경 후 서버 재시작 필요",
        default=False,
        update=_sync_pref("allow_lan")
    )

    user_rules: StringProperty(
        name="사용자 작업 지침",
        description="모든 작업에 적용할 지침. 여러 개는 ; 로 구분 (예: 베벨은 2단계; 베벨 면에 검은색 버텍스 컬러 적용)",
        default="",
        update=_sync_pref("user_rules")
    )

    def draw(self, context):
        layout = tl(self.layout)

        layout.prop(self, "ui_language")

        # 업데이트 (GitHub Releases)
        box_up = layout.box()
        box_up.label(text=f"버전: v{_current_version_str()}  (GitHub Releases)", icon='URL')
        ust = updater.state
        row_up = box_up.row(align=True)
        row_up.enabled = not (ust["checking"] or ust["installing"])
        row_up.operator("mcpchat.check_update", text="업데이트 확인", icon='FILE_REFRESH')
        info = ust.get("info")
        if ust["checking"]:
            box_up.label(text="확인 중…", icon='TIME')
        elif ust["installing"]:
            box_up.label(text="설치 중…", icon='TIME')
        elif info:
            if not info.get("ok"):
                box_up.label(text=info.get("error", ""), icon='ERROR')
            elif info.get("newer"):
                box_up.label(text=f"새 버전 v{info['latest']} 이(가) 있습니다", icon='CHECKMARK')
                row_in = box_up.row(align=True)
                row_in.scale_y = 1.2
                row_in.operator("mcpchat.install_update", text="업데이트 설치", icon='IMPORT')
            else:
                box_up.label(text="최신 버전입니다", icon='CHECKMARK')
        if ust.get("message"):
            box_up.label(text=ust["message"], icon='INFO')

        # AI 실행 규칙 (Blender Execution Rules) 편집
        box_rules = layout.box()
        is_custom = bool((session_mgr.get_setting("custom_guidelines", "") or "").strip())
        box_rules.label(text="AI 실행 규칙 (Blender Execution Rules)", icon='TEXT')
        box_rules.label(text="사용자 수정 규칙 사용 중" if is_custom else "기본 규칙 사용 중",
                        icon='CHECKMARK' if is_custom else 'DOT')
        row_ru = box_rules.row(align=True)
        row_ru.operator("mcpchat.edit_rules", text="규칙 편집", icon='GREASEPENCIL')
        row_ru.operator("mcpchat.save_rules", text="편집 내용 저장", icon='FILE_TICK')
        row_ru.operator("mcpchat.reset_rules", text="기본값 복원", icon='LOOP_BACK')
        box_rules.label(text="Text Editor에서 수정한 뒤 '편집 내용 저장'을 누르세요. AI에 그대로 전달되므로 영어 권장", icon='INFO')

        box_sec = layout.box()
        enc = {"DPAPI1": "Windows DPAPI", "OSSL1": "AES-256 (openssl)", "OBF1": "난독화 (약함)"}.get(secrets_store.backend_name(), "?")
        box_sec.label(text=f"API 키/토큰 보안 저장소: {enc}", icon='LOCKED' if not secrets_store.is_weak() else 'ERROR')
        if secrets_store.is_weak():
            box_sec.label(text="이 환경에는 시스템 암호화가 없어 키가 약하게만 보호됩니다 (openssl 설치 권장)", icon='INFO')
        box_sec.label(text="키는 애드온 폴더 안에 암호화되어 저장되며, 애드온을 삭제하면 함께 삭제됩니다", icon='INFO')
        box_sec.operator("mcpchat.wipe_all_data", text="모든 데이터 삭제 (대화/키/출력)", icon='TRASH')
        layout.separator()

        # 1. Direct API Settings Section
        box_api = layout.box()
        box_api.label(text="Direct API 설정 (OpenRouter / NVIDIA NIM / Local Ollama)", icon='WORLD')
        box_api.prop(self, "active_provider")

        if self.active_provider == 'openrouter':
            col = box_api.column(align=True)
            _secret_row(col, self, "openrouter_api_key")
            col.prop(self, "openrouter_model")
            col.label(text="OpenRouter API Key 발급: https://openrouter.ai/keys", icon='INFO')
        elif self.active_provider == 'nvidia_nim':
            col = box_api.column(align=True)
            _secret_row(col, self, "nvidia_nim_api_key")
            col.prop(self, "nvidia_nim_model")
            col.label(text="NVIDIA NIM API Key 발급: https://build.nvidia.com", icon='INFO')
        elif self.active_provider == 'local':
            col = box_api.column(align=True)
            col.prop(self, "local_base_url")
            col.prop(self, "local_model")
            col.label(text="Ollama 기본 URL: http://127.0.0.1:11434/v1", icon='INFO')
        elif self.active_provider == 'custom':
            col = box_api.column(align=True)
            col.prop(self, "custom_base_url")
            _secret_row(col, self, "custom_api_key")
            col.prop(self, "custom_model")

        row_think = box_api.row(align=True)
        row_think.prop(self, "reasoning_effort")
        row_think.prop(self, "thinking_budget")

        layout.separator()

        # 2. Server Settings Section
        box_server = layout.box()
        box_server.label(text="Server & Mobile Web UI", icon='URL')
        box_server.prop(self, "default_port")
        box_server.prop(self, "autostart")
        box_server.label(text="Local Web Chat: http://127.0.0.1:<port>", icon='URL')
        box_server.label(text="Termux / PC MCP Endpoint: http://127.0.0.1:<port>/mcp", icon='CONSOLE')

        box_server.prop(self, "allow_lan")
        if self.allow_lan:
            box_lan = box_server.box()
            token = session_mgr.get_or_create_token()
            ips = server.get_lan_ips()
            port = self.default_port
            box_lan.label(text="Termux 접속 정보 (서버 재시작 후 적용)", icon='WORLD')
            for ip in ips[:3]:
                box_lan.label(text=f"  http://{ip}:{port}/mcp")
            box_lan.label(text=f"  Token: {token[:6]}…{token[-4:]}  (복사 버튼으로 전체 사용)")
            row_lan = box_lan.row(align=True)
            row_lan.operator("mcpchat.copy_termux_command", text="Termux 설치 명령 복사", icon='COPYDOWN')
            row_lan.operator("mcpchat.regenerate_token", text="토큰 재발급", icon='FILE_REFRESH')
            box_lan.label(text="폰 Termux에서 복사한 명령을 붙여넣어 실행. Windows 방화벽 TCP 포트 허용 필요", icon='INFO')
        else:
            box_server.label(text="현재 로컬 전용 (PC 내부에서만 접속 가능)", icon='LOCKED')

        row_srv = box_server.row(align=True)
        if server_mgr.is_running:
            row_srv.label(text=f"Server: Online (Port {server_mgr.port})", icon='RADIOBUT_ON')
            row_srv.operator("mcpchat.stop_server", text="Stop Server", icon='PAUSE')
            box_server.operator("mcpchat.open_browser", text="Open Web Chat UI", icon='WINDOW')
        else:
            row_srv.label(text="Server: Offline", icon='RADIOBUT_OFF')
            row_srv.operator("mcpchat.start_server", text="Start Server", icon='PLAY')

        layout.separator()

        # 3. Termux Agent (Android APK Blender + Termux CLI)
        box_agent = layout.box()
        box_agent.label(text="Termux Agent (Android Blender APK + Termux의 claude/agy/codex)", icon='COMMUNITY')
        box_agent.prop(self, "cli_remote_url")
        _secret_row(box_agent, self, "cli_remote_token")
        box_agent.operator("mcpchat.test_agent", text="Agent 연결 테스트", icon='PLUGIN')
        box_agent.label(text="Termux에서 설치 명령 실행 후 출력되는 URL/토큰을 입력하세요 (아래 로컬 서버 설정 참고)", icon='INFO')

        layout.separator()

        # 4. Claude Code & agy CLI Section
        box_cli = layout.box()
        box_cli.label(text="Claude Code & agy CLI", icon='CONSOLE')
        try:
            env = cli_runner.detect_environment()
            box_cli.label(text=f"환경 감지: {env['os_name']}", icon='DESKTOP' if env["is_windows"] else 'COMMUNITY')
            for label, path in (("Claude Code", env["claude_bin"]), ("Codex CLI", env["codex_bin"]), ("agy CLI", env["agy_bin"])):
                if path:
                    box_cli.label(text=f"{label}: 감지됨 ({os.path.basename(path)})", icon='CHECKMARK')
                else:
                    box_cli.label(text=f"{label}: 미감지", icon='X')
        except Exception as e:
            box_cli.label(text=f"환경 감지 오류: {e}", icon='ERROR')
        col = box_cli.column(align=True)
        col.operator("mcpchat.setup_claude_cli", text="Claude Code MCP 자동 등록", icon='CONSOLE')
        col.operator("mcpchat.setup_codex_cli", text="Codex CLI MCP 자동 등록", icon='CONSOLE')
        col.operator("mcpchat.setup_agy_cli", text="agy CLI MCP 자동 등록", icon='SETTINGS')

        layout.separator()

        # 5. 출처 / 참조 (Credits)
        box_cr = layout.box()
        box_cr.label(text="출처 / 참조", icon='INFO')
        box_cr.label(text="MCP (Model Context Protocol): Anthropic 공개 사양, 이 애드온에서 직접 구현")
        box_cr.label(text="CLI: Claude Code (Anthropic) · Codex (OpenAI) · agy (Google)")
        box_cr.label(text="Blender API (bpy) · glTF-Blender-IO (Khronos) · ambientCG (CC0)")
        row_cr = box_cr.row(align=True)
        o1 = row_cr.operator("mcpchat.open_url", text="MCP 사양", icon='URL')
        o1.url = "https://modelcontextprotocol.io"
        o2 = row_cr.operator("mcpchat.open_url", text="전체 출처 (README)", icon='URL')
        o2.url = "https://github.com/refleAct/mcp-chat-for-blender#11-출처-및-참조-credits"


# ==============================================================================
# Image Attachment Previews (bpy.utils.previews)
# ==============================================================================

_preview_coll = None


def ensure_preview(item):
    """첨부 이미지 썸네일을 로드한다 (operator 컨텍스트에서만 호출, draw 금지)."""
    global _preview_coll
    if _preview_coll is None:
        _preview_coll = bpy.utils.previews.new()
    try:
        key = item.preview_key or uuid.uuid4().hex
        item.preview_key = key
        if key in _preview_coll:
            return
        path = item.path if item.path and os.path.exists(item.path) else ""
        if not path and item.data_b64:
            raw = item.data_b64.split(",", 1)[-1]
            path = os.path.join(tempfile.gettempdir(), f"mcpchat_prev_{key}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(raw))
        if path:
            _preview_coll.load(key, path, 'IMAGE')
    except Exception:
        pass


def get_preview_icon(item):
    try:
        p = _preview_coll.get(item.preview_key) if _preview_coll else None
        return p.icon_id if p else 0
    except Exception:
        return 0


_busy_state = {}   # {session_id: [라벨, ...]}  요청 처리 중 표시용 (채팅 안에 '작업 중' 줄로 표시)
_busy_lock = threading.Lock()


def begin_busy(session_id, label):
    with _busy_lock:
        _busy_state.setdefault(session_id, []).append(label)


def end_busy(session_id, label):
    with _busy_lock:
        lst = _busy_state.get(session_id, [])
        if label in lst:
            lst.remove(label)


def _end_after(fn, session_id, label):
    """백그라운드 스레드 함수를 감싸 종료 시 '작업 중' 표시를 제거한다."""
    def _run():
        try:
            fn()
        finally:
            end_busy(session_id, label)
    return _run


def tag_redraw_all():
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass


def _redraw_hook():
    """큐 워커가 진행 상황이 바뀔 때 호출: 진행 줄 갱신 + 화면 다시 그리기."""
    try:
        scene = bpy.context.scene
        rebuild_lines(scene, scroll_to_end=True)
        tag_redraw_all()
    except Exception:
        pass


class MCPCHAT_UL_lines(UIList):
    """멀티라인 채팅 히스토리: 줄 단위 행 + 네이티브 스크롤바/마우스휠"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout = tl(layout)
        row = layout.row(align=True)
        if item.first:
            row.label(text="", icon='USER' if item.role == 'user' else 'RESTRICT_RENDER_OFF')
        else:
            row.label(text="", icon='BLANK1')
        row.label(text=item.text)
        if item.first:
            if item.expandable:
                tg = row.operator("mcpchat.toggle_message", text="", emboss=False,
                                  icon='TRIA_UP' if item.expanded else 'TRIA_DOWN')
                tg.index = item.msg_index
            if item.has_prompt:
                vp = row.operator("mcpchat.view_sent_prompt", text="", emboss=False, icon='TEXT')
                vp.key = item.msg_id
            if item.msg_index >= 0:
                cp = row.operator("mcpchat.copy_message", text="", emboss=False, icon='COPYDOWN')
                cp.index = item.msg_index


# ==============================================================================
# Session Helpers
# ==============================================================================

def sync_messages_to_ui(scene, session_id):
    """Loads session messages into Blender UIList collection."""
    session = session_mgr.get_session(session_id)
    scene.mcpchat_messages.clear()
    if not session:
        return

    prompt_keys = session_mgr.sent_prompt_keys()
    for m in session.get("messages", [])[-MAX_HISTORY_ITEMS:]:
        if m["role"] not in ("user", "assistant"):
            continue
        item = scene.mcpchat_messages.add()
        item.msg_id = m["id"]
        item.has_prompt = m["id"] in prompt_keys
        item.role = m["role"]
        item.content = summarize_message(m["content"], m["role"])
        item.full_text = m["content"]
        item.img_count = len(m.get("images") or [])

    rebuild_lines(scene, scroll_to_end=True, sid=session_id)
    tag_redraw_all()


def _cell_width(ch):
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def wrap_cells(text, cells):
    """표시 폭 기준 줄바꿈: 한글/한자/전각은 2칸, 영문/숫자는 1칸. 가능하면 공백에서 줄을 나눈다.
    라벨이 레이아웃보다 넓어 Blender가 중간을 '...'로 줄이는 것을 막는다."""
    lines, cur, cur_w, last_space = [], "", 0, -1
    for ch in text:
        w = _cell_width(ch)
        if cur_w + w > cells and cur:
            if last_space > 0:
                lines.append(cur[:last_space].rstrip())
                cur = cur[last_space:].lstrip() + ch
                cur_w = sum(_cell_width(c) for c in cur)
            else:
                lines.append(cur)
                cur, cur_w = ch, w
            last_space = -1
            continue
        if ch == " ":
            last_space = len(cur)
        cur += ch
        cur_w += w
    if cur:
        lines.append(cur)
    return lines or [""]


def rebuild_lines(scene, scroll_to_end=False, sid=None):
    """메시지 -> 줄 단위 행으로 변환. UIList 네이티브 스크롤바/휠 스크롤을 사용하기 위함."""
    lines = scene.mcpchat_lines
    lines.clear()
    cells = max(12, getattr(scene, "mcpchat_wrap_cells", 26))
    for idx, m in enumerate(scene.mcpchat_messages):
        suffix = f" [img {m.img_count}]" if m.img_count else ""
        expandable = len(m.full_text) > len(m.content) + 3
        if m.expanded:
            chunks = []
            for ln in m.full_text.splitlines():
                if ln.strip():
                    chunks.extend(wrap_cells(ln, cells))
            chunks = chunks[:MAX_EXPANDED_LINES] + (["…"] if len(chunks) > MAX_EXPANDED_LINES else [])
        else:
            chunks = wrap_cells(m.content + suffix, cells)
            if len(chunks) > SUMMARY_MAX_LINES:
                chunks = chunks[:SUMMARY_MAX_LINES]
                chunks[-1] = chunks[-1].rstrip() + " …"
        for n, chunk in enumerate(chunks):
            it = lines.add()
            it.role = m.role
            it.text = chunk
            it.msg_index = idx
            it.first = (n == 0)
            it.expandable = expandable
            it.expanded = m.expanded
            it.msg_id = m.msg_id
            it.has_prompt = m.has_prompt
    # 진행 중 표시 (저장되지 않는 임시 줄): 요청 처리 중 / 큐 작업 진행 중
    try:
        sid = sid or session_mgr.get_tab_session_id(scene.mcpchat_active_tab)
    except Exception:
        sid = None
    transient = [tr(f"⏳ {lab}") for lab in list(_busy_state.get(sid, []))]
    active = task_queue.active_task
    if active:
        transient.append(tr(f"⏳ 작업 진행중: {active.get('title', '')} - {task_queue.progress or '실행 중'}"))
    for text in transient:
        for n, chunk in enumerate(wrap_cells(text, cells)):
            it = lines.add()
            it.role = 'assistant'
            it.text = chunk
            it.msg_index = -1
            it.first = (n == 0)
    if scroll_to_end and len(lines) > 0:
        scene.mcpchat_active_line = len(lines) - 1


_DONE_TAG = "✅ 생성이 완료되었습니다."


def summarize_message(text, role, max_len=SUMMARY_MAX_LEN):
    """채팅 히스토리용 초단문 요약: 첫 문장 + 항목 수 + 완료 표시."""
    done = _DONE_TAG in text or "✅" in text
    body = text.replace(_DONE_TAG, "")
    body = re.sub(r"```[\s\S]*?```", " ", body)          # 코드블록 제거
    bullets = len(re.findall(r"^\s*[-•*]\s+", body, re.M))
    body = re.sub(r"[*`#>_]+", "", body)                 # 마크다운 기호 제거
    body = re.sub(r"^\s*[-•]\s+", "", body, flags=re.M)
    body = " ".join(body.split())
    if role == "user":
        out = body
    else:
        m = re.search(r"^(.+?(?:다|요|\.|!|\?))(?:\s|$)", body)   # 첫 문장
        out = m.group(1) if m else body
        if bullets:
            out += f" (+{bullets}항목)"
    if len(out) > max_len:
        out = out[:max_len - 1].rstrip() + "…"
    return (out or "(내용 없음)") + (" ✅" if done and role != "user" else "")


# ==============================================================================
# Operators: 3-Session Tabs (Stable Slots & Renaming)
# ==============================================================================

class MCPCHAT_OT_switch_tab(TOp):
    """Switch active session tab"""
    bl_idname = "mcpchat.switch_tab"
    bl_label = "Switch Tab"

    tab_index: IntProperty(default=0)

    def execute(self, context):
        context.scene.mcpchat_active_tab = self.tab_index
        sid = session_manager.session_mgr.get_tab_session_id(self.tab_index)
        sync_messages_to_ui(context.scene, sid)
        return {'FINISHED'}


class MCPCHAT_OT_add_session_tab(TOp):
    """새 세션 탭 추가 (최대 3개)"""
    bl_idname = "mcpchat.add_session_tab"
    bl_label = "세션 추가"
    bl_icon = 'ADD'

    def execute(self, context):
        new_s = session_manager.session_mgr.add_tab_session()
        if new_s:
            tabs = session_manager.session_mgr.get_tab_sessions(3)
            new_idx = len(tabs) - 1
            context.scene.mcpchat_active_tab = new_idx
            sync_messages_to_ui(context.scene, new_s["id"])
            self.report({'INFO'}, f"새 세션 '{new_s['title']}'(이)가 추가되었습니다.")
        else:
            self.report({'WARNING'}, "세션은 최대 3개까지만 추가할 수 있습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_delete_session_tab(TOp):
    """현재 세션 탭 삭제 (1개만 남은 경우 대화 초기화)"""
    bl_idname = "mcpchat.delete_session_tab"
    bl_label = "세션 삭제"
    bl_icon = 'TRASH'

    def execute(self, context):
        tab_idx = getattr(context.scene, "mcpchat_active_tab", 0)
        ok, next_sid = session_manager.session_mgr.delete_tab_session(tab_idx)
        tabs = session_manager.session_mgr.get_tab_sessions(3)
        new_idx = max(0, min(len(tabs) - 1, tab_idx - 1))
        context.scene.mcpchat_active_tab = new_idx
        if next_sid:
            sync_messages_to_ui(context.scene, next_sid)
        self.report({'INFO'}, "세션이 삭제되었습니다." if len(tabs) > 1 or tab_idx > 0 else "마지막 세션이 삭제되어 새 '세션 1'이 만들어졌습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_rename_session_tab(TOp):
    """세션 탭 이름 변경 (Rename Active Chat Session Tab)"""
    bl_idname = "mcpchat.rename_session_tab"
    bl_label = "세션 이름 변경"
    bl_options = {'REGISTER', 'UNDO'}

    tab_index: IntProperty(default=0)
    new_title: StringProperty(
        name="새 이름",
        description="세션 탭에 표시할 새 이름을 입력하세요",
        default=""
    )

    def invoke(self, context, event):
        self.tab_index = getattr(context.scene, "mcpchat_active_tab", 0)
        tabs = session_manager.session_mgr.get_tab_sessions(3)
        if 0 <= self.tab_index < len(tabs):
            self.new_title = tabs[self.tab_index]["title"]
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = tl(self.layout)
        layout.label(text=f"세션 {self.tab_index + 1} 새 이름:", icon='GREASEPENCIL')
        layout.prop(self, "new_title", text="")

    def execute(self, context):
        title = self.new_title.strip()
        if not title:
            self.report({'WARNING'}, "세션 이름을 입력해 주세요.")
            return {'CANCELLED'}
        session_manager.session_mgr.rename_tab_session(self.tab_index, title)
        self.report({'INFO'}, f"세션 이름이 '{title}'(으)로 변경되었습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_copy_message(TOp):
    """선택한 메시지 전체를 클립보드에 복사"""
    bl_idname = "mcpchat.copy_message"
    bl_label = "메시지 복사"

    index: IntProperty(default=-1)

    def execute(self, context):
        scene = context.scene
        idx = self.index
        if 0 <= idx < len(scene.mcpchat_messages):
            context.window_manager.clipboard = scene.mcpchat_messages[idx].full_text
            self.report({'INFO'}, "메시지가 복사되었습니다.")
            return {'FINISHED'}
        return {'CANCELLED'}


class MCPCHAT_OT_toggle_message(TOp):
    """메시지 요약/전체 펼치기 전환"""
    bl_idname = "mcpchat.toggle_message"
    bl_label = "펼치기/접기"

    index: IntProperty(default=-1)

    def execute(self, context):
        msgs = context.scene.mcpchat_messages
        if 0 <= self.index < len(msgs):
            msgs[self.index].expanded = not msgs[self.index].expanded
            rebuild_lines(context.scene)
            # 펼친 메시지의 첫 줄로 이동
            for n, it in enumerate(context.scene.mcpchat_lines):
                if it.msg_index == self.index and it.first:
                    context.scene.mcpchat_active_line = n
                    break
        return {'FINISHED'}


class MCPCHAT_OT_scroll_history(TOp):
    """채팅 히스토리 스크롤"""
    bl_idname = "mcpchat.scroll_history"
    bl_label = "히스토리 스크롤"

    delta: IntProperty(default=0)

    def execute(self, context):
        scene = context.scene
        scene.mcpchat_scroll = max(0, min(len(scene.mcpchat_messages) - 1, scene.mcpchat_scroll + self.delta))
        return {'FINISHED'}


class MCPCHAT_OT_clear_history(TOp):
    """현재 세션의 대화 기록 초기화"""
    bl_idname = "mcpchat.clear_history"
    bl_label = "대화 초기화"

    def execute(self, context):
        sid = session_mgr.get_tab_session_id(context.scene.mcpchat_active_tab)
        try:
            with session_mgr._get_connection() as conn:
                conn.cursor().execute("DELETE FROM messages WHERE session_id = ?", (sid,))
                conn.commit()
        except Exception as e:
            self.report({'ERROR'}, f"초기화 실패: {e}")
            return {'CANCELLED'}
        sync_messages_to_ui(context.scene, sid)
        return {'FINISHED'}


def compose_final_prompt(scene, prompt, mode=None, n_images=0):
    """현재 엔진/모드/설정으로 실제 전송될 최종 프롬프트 텍스트 (헤더 포함)."""
    mode = mode or scene.mcpchat_mode
    backend = scene.mcpchat_backend
    nl = chr(10)
    if backend in CLI_ENGINES:
        cli_type, label = CLI_ENGINES[backend]
        opts = cli_runner.collect_opts()
        model = opts.get(f"{cli_type}_model") or "(기본)"
        effort = opts.get(f"{cli_type}_effort")
        head = f"[엔진] {label}  [모델] {model}  [추론] {effort}  [모드] {mode}"
        placeholders = [f"<첨부이미지 {k + 1}: 실행 시 임시 파일 경로로 대체>" for k in range(n_images)]
        body = cli_runner.compose_prompt(cli_type, mode, prompt, cli_runner.build_guidelines(), placeholders)
        return head + nl + "=" * 60 + nl + body
    # Direct API
    head = f"[엔진] Direct API  [모드] {mode}"
    if mode in ('PLAN', 'AUTO'):
        msgs = llm_client.compose_plan_messages(prompt)
        img_note = (nl + f"[첨부 이미지 {n_images}장 포함]") if n_images else ""
        return (head + nl + "=" * 60 + nl + "== system ==" + nl + msgs[0]["content"]
                + nl + nl + "== user ==" + nl + msgs[1]["content"] + img_note)
    sid = session_mgr.get_tab_session_id(scene.mcpchat_active_tab)
    sess = session_mgr.get_session(sid, with_messages=False) or {}
    img_note = (nl + f"[첨부 이미지 {n_images}장 포함]") if n_images else ""
    return (head + nl + "=" * 60 + nl + "== system ==" + nl + (sess.get("system_prompt") or "")
            + nl + nl + "== user ==" + nl + prompt + img_note)


PREVIEW_TEXT_NAME = "MCP Prompt Preview"


def show_text_block(context, name, text):
    """텍스트 데이터블록으로 만들고 텍스트 에디터에 표시 (스크롤/복사 가능). 표시 성공 여부 반환."""
    txt = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    txt.clear()
    txt.write(text)
    txt.cursor_set(0)
    try:
        for win in context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'TEXT_EDITOR':
                    area.spaces.active.text = txt
                    area.tag_redraw()
                    return True
        bpy.ops.wm.window_new()
        win = context.window_manager.windows[-1]
        area = win.screen.areas[0]
        area.type = 'TEXT_EDITOR'
        area.spaces.active.text = txt
        return True
    except Exception:
        return False


class MCPCHAT_OT_preview_prompt(TOp):
    """전송 전 미리보기: 지금 보내면 AI에게 실제로 전달될 최종 프롬프트 확인"""
    bl_idname = "mcpchat.preview_prompt"
    bl_label = "전송 프롬프트 미리보기"

    def execute(self, context):
        scene = context.scene
        prompt = scene.mcpchat_prompt.strip() or "(여기에 입력한 프롬프트가 들어갑니다)"
        text = compose_final_prompt(scene, prompt, n_images=len(scene.mcpchat_attached_images))
        if show_text_block(context, PREVIEW_TEXT_NAME, text):
            self.report({'INFO'}, "전송 프롬프트를 텍스트 창에 표시했습니다.")
        else:
            self.report({'WARNING'}, f"텍스트 에디터를 열 수 없습니다. Text Editor에서 '{PREVIEW_TEXT_NAME}'를 선택해 확인하세요.")
        return {'FINISHED'}


class MCPCHAT_OT_view_sent_prompt(TOp):
    """이 메시지/작업에 대해 실제 전송된 프롬프트 (Auto는 AI 계획 포함) 보기"""
    bl_idname = "mcpchat.view_sent_prompt"
    bl_label = "전송된 프롬프트 보기"

    key: StringProperty()

    def execute(self, context):
        text = session_mgr.get_sent_prompt(self.key)
        if not text:
            self.report({'WARNING'}, "저장된 프롬프트가 없습니다.")
            return {'CANCELLED'}
        if show_text_block(context, "MCP Sent Prompt", text):
            self.report({'INFO'}, "전송된 프롬프트를 텍스트 창에 표시했습니다.")
        else:
            self.report({'WARNING'}, "텍스트 에디터를 열 수 없습니다. Text Editor에서 'MCP Sent Prompt'를 선택하세요.")
        return {'FINISHED'}


def build_refine_prompt(pending, new_request):
    nl = chr(10)
    return (
        f"{pending.get('prompt', '')}" + nl + nl
        + "[Previously proposed plan]" + nl + f"{pending.get('plan_text', '')}" + nl + nl
        + "[User change/addition request - rewrite the plan to reflect it]" + nl + new_request
    )


class MCPCHAT_OT_plan_execute(TOp):
    """검토한 Plan을 실행 (작업 큐 1건으로 등록)"""
    bl_idname = "mcpchat.plan_execute"
    bl_label = "계획 실행"

    def execute(self, context):
        scene = context.scene
        sid = session_mgr.get_tab_session_id(scene.mcpchat_active_tab)
        pend = session_mgr.get_pending_plan(sid)
        if not pend:
            self.report({'WARNING'}, "실행할 계획이 없습니다.")
            return {'CANCELLED'}

        title = (pend.get("title") or "계획")[:24] + " (실행)"
        if pend.get("backend") == "API":
            payload = {"prompt": pend.get("prompt", ""), "backend": "API", "plan": pend.get("plan")}
            task_type = "auto_plan"
        else:
            nl = chr(10)
            payload = {
                "prompt": pend.get("prompt", "") + nl + nl + "[Approved plan - execute exactly this plan]" + nl + pend.get("plan_text", ""),
                "backend": pend.get("backend", "CLAUDE"),
                "images": pend.get("images") or [],
            }
            task_type = "prompt"

        task = session_mgr.enqueue_task(title=title, task_type=task_type, payload=payload)
        session_mgr.clear_pending_plan(sid)
        scene.mcpchat_plan_refine = False
        task_queue.resume()
        task_queue.start()
        session_mgr.add_message(sid, "assistant", f"▶ 계획이 작업 큐 1건으로 등록되어 실행됩니다 ('{task['title']}').")
        sync_messages_to_ui(scene, sid)
        return {'FINISHED'}


class MCPCHAT_OT_plan_refine(TOp):
    """계획을 계속 수정/보완 (다음 전송이 Plan 수정 요청으로 처리됨)"""
    bl_idname = "mcpchat.plan_refine"
    bl_label = "계속 계획"

    def execute(self, context):
        scene = context.scene
        scene.mcpchat_plan_refine = not scene.mcpchat_plan_refine
        if scene.mcpchat_plan_refine:
            scene.mcpchat_mode = 'PLAN'
            self.report({'INFO'}, "수정/추가 요청을 입력하고 전송하세요.")
        return {'FINISHED'}


class MCPCHAT_OT_plan_cancel(TOp):
    """검토 중인 계획 취소"""
    bl_idname = "mcpchat.plan_cancel"
    bl_label = "계획 취소"

    def execute(self, context):
        scene = context.scene
        sid = session_mgr.get_tab_session_id(scene.mcpchat_active_tab)
        session_mgr.clear_pending_plan(sid)
        scene.mcpchat_plan_refine = False
        return {'FINISHED'}


class MCPCHAT_OT_paste_prompt(TOp):
    """클립보드 텍스트를 프롬프트 입력창에 붙여넣기"""
    bl_idname = "mcpchat.paste_prompt"
    bl_label = "클립보드 붙여넣기"

    def execute(self, context):
        text = context.window_manager.clipboard
        if not text or not text.strip():
            self.report({'WARNING'}, "클립보드에 텍스트가 없습니다.")
            return {'CANCELLED'}
        scene = context.scene
        current = scene.mcpchat_prompt
        scene.mcpchat_prompt = (current + (" " if current and not current.endswith((" ", chr(10))) else "") + text.strip())
        return {'FINISHED'}


class MCPCHAT_OT_compact_history(TOp):
    """오래된 대화를 하나의 요약 메시지로 압축 (최근 4개 메시지 유지)"""
    bl_idname = "mcpchat.compact_history"
    bl_label = "대화 압축"

    def execute(self, context):
        sid = session_mgr.get_tab_session_id(context.scene.mcpchat_active_tab)
        n = session_mgr.compact_session(sid, summarize_message, keep_last=4)
        sync_messages_to_ui(context.scene, sid)
        if n:
            self.report({'INFO'}, f"{n}개 메시지를 요약으로 압축했습니다.")
        else:
            self.report({'INFO'}, "압축할 이전 대화가 충분하지 않습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_move_queue_task(TOp):
    """큐 작업 순서 변경 (위/아래)"""
    bl_idname = "mcpchat.move_queue_task"
    bl_label = "순서 변경"

    task_id: StringProperty()
    direction: IntProperty(default=-1)

    def execute(self, context):
        session_mgr.move_task(self.task_id, self.direction)
        return {'FINISHED'}


class MCPCHAT_OT_queue_task_action(TOp):
    """큐 작업 재시도 / 복제 / 완료 항목 정리"""
    bl_idname = "mcpchat.queue_task_action"
    bl_label = "큐 작업 동작"

    task_id: StringProperty()
    action: StringProperty()  # retry | duplicate | clear_done

    def execute(self, context):
        if self.action == "retry":
            session_mgr.retry_task(self.task_id)
            task_queue.resume()
            task_queue.start()
        elif self.action == "duplicate":
            session_mgr.duplicate_task(self.task_id)
        elif self.action == "clear_done":
            for st in ("completed", "failed", "cancelled"):
                session_mgr.clear_queue(st)
        return {'FINISHED'}


class MCPCHAT_OT_reload_addon(TOp):
    """Reload MCP Chat UI and synchronize active session messages"""
    bl_idname = "mcpchat.reload_addon"
    bl_label = "새로고침"
    bl_icon = 'FILE_REFRESH'

    def execute(self, context):
        try:
            import importlib
            for _mod in ["updater", "secrets_store", "i18n", "guidelines", "session_manager", "blender_bridge", "task_queue", "cli_runner", "llm_client", "server", "mcp_handler"]:
                if _mod in sys.modules:
                    try:
                        importlib.reload(sys.modules[_mod])
                    except Exception:
                        pass
            tab_idx = getattr(context.scene, "mcpchat_active_tab", 0)
            sid = session_manager.session_mgr.get_tab_session_id(tab_idx)
            sync_messages_to_ui(context.scene, sid)
            self.report({'INFO'}, "MCP Chat 세션 및 모듈이 새로고침되었습니다.")
        except Exception as e:
            self.report({'ERROR'}, f"새로고침 실패: {e}")
        return {'FINISHED'}


# ==============================================================================
# Operators & Menus: Image Attachments (Max 3 Total, in front of input)
# ==============================================================================

class MCPCHAT_MT_attach_menu(Menu):
    """Attachment Menu in front of input box"""
    bl_label = "Attach"
    bl_idname = "MCPCHAT_MT_attach_menu"

    def draw(self, context):
        layout = tl(self.layout)
        count = len(context.scene.mcpchat_attached_images)
        if count >= 3:
            layout.label(text="최대 3개 첨부 완료 (3/3)", icon='INFO')
            return

        layout.operator("mcpchat.select_local_image", text="📁 로컬 이미지 첨부...", icon='FILE_IMAGE')
        layout.operator("mcpchat.attach_viewport_snapshot", text="📸 뷰포트 스냅샷 첨부", icon='RESTRICT_RENDER_OFF')


class MCPCHAT_OT_select_local_image(TOp, ImportHelper):
    """Select a local image from disk (Max 3)"""
    bl_idname = "mcpchat.select_local_image"
    bl_label = "Select Local Image"
    bl_icon = 'FILE_IMAGE'

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif",
        options={'HIDDEN'}
    )

    def execute(self, context):
        scene = context.scene
        if len(scene.mcpchat_attached_images) >= 3:
            self.report({'WARNING'}, "이미지는 최대 3개까지만 첨부할 수 있습니다.")
            return {'CANCELLED'}

        if self.filepath and os.path.exists(self.filepath):
            fname = os.path.basename(self.filepath)
            mime, _ = mimetypes.guess_type(self.filepath)
            mime = mime or "image/png"
            try:
                with open(self.filepath, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                
                item = scene.mcpchat_attached_images.add()
                item.name = fname
                item.path = self.filepath
                item.is_viewport = False
                item.data_b64 = f"data:{mime};base64,{b64}"
                ensure_preview(item)
                self.report({'INFO'}, f"첨부됨: {fname} ({len(scene.mcpchat_attached_images)}/3)")
            except PermissionError:
                self.report({'ERROR'}, "안드로이드 저장소 권한 오류: Termux 터미널에서 'termux-setup-storage'를 실행하거나 브라우저 웹 UI(http://127.0.0.1:8000)에서 첨부하세요.")
            except Exception as e:
                self.report({'ERROR'}, f"이미지 읽기 실패: {e}")
        return {'FINISHED'}


class MCPCHAT_OT_attach_viewport_snapshot(TOp):
    """Capture 3D Viewport snapshot and attach (Max 3)"""
    bl_idname = "mcpchat.attach_viewport_snapshot"
    bl_label = "Attach Viewport Snapshot"
    bl_icon = 'RESTRICT_RENDER_OFF'

    def execute(self, context):
        scene = context.scene
        if len(scene.mcpchat_attached_images) >= 3:
            self.report({'WARNING'}, "이미지는 최대 3개까지만 첨부할 수 있습니다.")
            return {'CANCELLED'}

        res = bridge.capture_viewport()
        if "image_base64" in res:
            item = scene.mcpchat_attached_images.add()
            item.name = "Viewport Snapshot"
            item.path = res.get("filepath", "")
            item.is_viewport = True
            item.data_b64 = res["image_base64"]
            ensure_preview(item)
            self.report({'INFO'}, f"뷰포트 스냅샷 첨부됨 ({len(scene.mcpchat_attached_images)}/3)")
        else:
            self.report({'ERROR'}, f"스냅샷 캡처 실패: {res.get('error')}")
        return {'FINISHED'}


class MCPCHAT_OT_remove_attached_image(TOp):
    """Remove attached image by index"""
    bl_idname = "mcpchat.remove_attached_image"
    bl_label = "Remove"
    bl_icon = 'X'

    index: IntProperty(default=0)

    def execute(self, context):
        scene = context.scene
        if 0 <= self.index < len(scene.mcpchat_attached_images):
            scene.mcpchat_attached_images.remove(self.index)
        return {'FINISHED'}


# ==============================================================================
# Operators: Send Message (Chat / Plan / Auto with Claude/agy CLI & API)
# ==============================================================================

class MCPCHAT_OT_send_message(TOp):
    """Send prompt using current mode (Chat, Plan, Auto) and engine"""
    bl_idname = "mcpchat.send_message"
    bl_label = "Send"
    bl_icon = 'PLAY'

    def execute(self, context):
        scene = context.scene
        prompt = scene.mcpchat_prompt.strip()
        if not prompt and len(scene.mcpchat_attached_images) == 0:
            self.report({'WARNING'}, "프롬프트 또는 이미지를 입력하세요")
            return {'CANCELLED'}

        mode = scene.mcpchat_mode
        backend = scene.mcpchat_backend

        # Collect up to 3 attached images
        images = [img.data_b64 for img in scene.mcpchat_attached_images if img.data_b64]

        # Clear input field and attachments after taking them
        scene.mcpchat_prompt = ""
        scene.mcpchat_attached_images.clear()

        # Get active session from tab
        tab_idx = scene.mcpchat_active_tab
        session_id = session_mgr.get_tab_session_id(tab_idx)

        # Plan 검토 중 '계속 계획'이면: 이전 계획 + 수정 요청을 합쳐 Plan 모드로 다시 계획한다
        display_prompt = prompt
        orig_prompt = prompt
        pending = session_mgr.get_pending_plan(session_id)
        if pending and scene.mcpchat_plan_refine:
            mode = 'PLAN'
            orig_prompt = pending.get("prompt", prompt)
            prompt = build_refine_prompt(pending, prompt)
            scene.mcpchat_plan_refine = False

        # 실제 전송될 최종 프롬프트 (전송 후 히스토리에서 확인 가능)
        try:
            final_text = compose_final_prompt(scene, prompt, mode, n_images=len(images))
        except Exception as _e:
            final_text = f"(프롬프트 기록 실패: {_e})"

        # -------------------------------------------------------------
        # 1. CLAUDE CODE CLI / AGY CLI BACKEND
        # -------------------------------------------------------------
        if backend in CLI_ENGINES:
            cli_type, cli_label = CLI_ENGINES[backend]
            
            user_msg = session_mgr.add_message(session_id, "user", display_prompt, images=images)
            try:
                session_mgr.set_sent_prompt(user_msg["id"], final_text)
            except Exception:
                pass
            busy_label = f"{cli_label} 작업 중…"
            begin_busy(session_id, busy_label)
            sync_messages_to_ui(scene, session_id)
            self.report({'INFO'}, f"[{cli_label}] {mode} 모드로 프롬프트 실행 중...")

            def _on_cli_done(success, output):
                end_busy(session_id, busy_label)
                # Strip ANSI escape codes if any
                clean_output = re.sub(r'\x1b\[[0-9;]*m', '', output).strip()
                completion_tag = "✅ 생성이 완료되었습니다."
                if clean_output:
                    full_text = f"{clean_output}\n\n{completion_tag}"
                else:
                    full_text = completion_tag
                session_mgr.add_message(session_id, "assistant", full_text)
                if mode == 'PLAN' and success and clean_output:
                    session_mgr.set_pending_plan(session_id, {
                        "backend": backend, "prompt": orig_prompt, "plan_text": clean_output,
                        "images": images, "plan": None, "title": orig_prompt.splitlines()[0][:30] if orig_prompt else "계획"
                    })
                # Redraw in main thread
                def _refresh():
                    sync_messages_to_ui(bpy.context.scene, session_id)
                    return None
                bpy.app.timers.register(_refresh, first_interval=0.1)

            cli_runner.run_cli_command_async(cli_type, prompt, mode=mode, on_complete=_on_cli_done, images=images)
            return {'FINISHED'}

        # -------------------------------------------------------------
        # 2. DIRECT API BACKEND (OpenRouter / NVIDIA NIM / Ollama)
        # -------------------------------------------------------------
        else:
            pref = context.preferences.addons.get(__name__)
            p = pref.preferences if pref else None
            provider = (p.active_provider if p else "") or session_mgr.get_setting("active_provider", "openrouter")

            if provider == 'openrouter':
                api_key = (p.openrouter_api_key if p else "") or session_mgr.get_setting("openrouter_api_key", "")
                model = (p.openrouter_model if p else "") or session_mgr.get_setting("openrouter_model", "anthropic/claude-3.5-sonnet")
                base_url = ""
            elif provider == 'nvidia_nim':
                api_key = (p.nvidia_nim_api_key if p else "") or session_mgr.get_setting("nvidia_nim_api_key", "")
                model = (p.nvidia_nim_model if p else "") or session_mgr.get_setting("nvidia_nim_model", "meta/llama-3.3-70b-instruct")
                base_url = ""
            elif provider == 'local':
                api_key = ""
                model = (p.local_model if p else "") or session_mgr.get_setting("local_model", "qwen2.5-coder:latest")
                base_url = (p.local_base_url if p else "") or session_mgr.get_setting("local_base_url", "http://127.0.0.1:11434/v1")
            else:
                api_key = (p.custom_api_key if p else "") or session_mgr.get_setting("custom_api_key", "")
                model = (p.custom_model if p else "") or session_mgr.get_setting("custom_model", "")
                base_url = (p.custom_base_url if p else "") or session_mgr.get_setting("custom_base_url", "")

            effort = (p.reasoning_effort if p else "") or session_mgr.get_setting("reasoning_effort", "medium")
            budget = str(p.thinking_budget if p else "") or session_mgr.get_setting("thinking_budget", "2048")

            client = LLMClient({
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "reasoning_effort": effort,
                "thinking_budget": budget
            })

            # PLAN MODE
            if mode == 'PLAN':
                _pm = session_mgr.add_message(session_id, "user", f"[PLAN] {display_prompt}", images=images)
                session_mgr.set_sent_prompt(_pm["id"], final_text)
                begin_busy(session_id, "Plan 수립 중…")
                sync_messages_to_ui(scene, session_id)
                self.report({'INFO'}, "단계별 Plan 계획 수립 중...")

                def _run_plan():
                    try:
                        plan = client.generate_plan(prompt, images=images)
                        summary = plan.get("summary", "")
                        steps = plan.get("steps", [])
                        lines = [f"📋 **{plan.get('plan_title', '계획서')}**", summary, ""]
                        for s in steps:
                            lines.append(f"• Step {s.get('step_number')}: {s.get('title')}\n{s.get('description')}\n```python\n{s.get('code')}\n```")
                        lines.append("\n✅ 계획 생성이 완료되었습니다. 아래 버튼으로 '실행' 또는 '계속 계획'을 선택하세요.")
                        plan_text = "\n".join(lines)
                        session_mgr.add_message(session_id, "assistant", plan_text)
                        if steps:
                            session_mgr.set_pending_plan(session_id, {
                                "backend": "API", "prompt": orig_prompt, "plan_text": plan_text,
                                "images": images, "plan": plan, "title": plan.get("plan_title", "계획")
                            })
                    except Exception as e:
                        session_mgr.add_message(session_id, "assistant", f"⚠️ Plan 오류: {e}")
                    
                    def _refresh():
                        sync_messages_to_ui(bpy.context.scene, session_id)
                        return None
                    bpy.app.timers.register(_refresh, first_interval=0.1)

                threading.Thread(target=_end_after(_run_plan, session_id, "Plan 수립 중…"), daemon=True).start()
                return {'FINISHED'}

            # AUTO MODE
            elif mode == 'AUTO':
                _am = session_mgr.add_message(session_id, "user", f"[AUTO] {prompt}", images=images)
                session_mgr.set_sent_prompt(_am["id"], final_text)
                sync_messages_to_ui(scene, session_id)
                self.report({'INFO'}, "오토 모드: 계획 생성 후 작업큐 자동 실행...")

                # 하나의 지시 = 하나의 큐 작업. 계획 생성과 단계 실행은 작업 내부에서 처리된다.
                task = session_mgr.enqueue_task(
                    title=prompt.splitlines()[0][:30] if prompt else "오토 작업",
                    task_type="auto_plan",
                    payload={"prompt": prompt, "backend": "API", "images": images}
                )
                task_queue.resume()
                task_queue.start()
                session_mgr.add_message(
                    session_id,
                    "assistant",
                    f"⚡ Auto Mode: 지시가 작업 큐 1건으로 등록되었습니다 ('{task['title']}'). 계획 수립과 단계 실행은 이 작업 안에서 순차 처리됩니다."
                )
                sync_messages_to_ui(scene, session_id)
                return {'FINISHED'}

            # CHAT MODE
            else:
                _cm = session_mgr.add_message(session_id, "user", prompt, images=images)
                session_mgr.set_sent_prompt(_cm["id"], final_text)
                begin_busy(session_id, "AI 응답 생성 중…")
                sync_messages_to_ui(scene, session_id)
                self.report({'INFO'}, "AI 추론 및 실행 중...")

                def _run_chat():
                    current_session = session_mgr.get_session(session_id)
                    try:
                        res = client.run_agent_loop(
                            system_prompt=current_session.get("system_prompt", ""),
                            messages=current_session.get("messages", [])
                        )
                        content = (res.get("content") or "").strip()
                        completion_tag = "✅ 생성이 완료되었습니다."
                        full_msg = f"{content}\n\n{completion_tag}" if content else completion_tag
                        session_mgr.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=full_msg,
                            thought=res.get("thought"),
                            images=res.get("captured_images"),
                            tool_calls=res.get("tool_events")
                        )
                    except Exception as e:
                        session_mgr.add_message(session_id, "assistant", f"⚠️ 통신 오류: {e}")

                    def _refresh():
                        sync_messages_to_ui(bpy.context.scene, session_id)
                        return None
                    bpy.app.timers.register(_refresh, first_interval=0.1)

                threading.Thread(target=_end_after(_run_chat, session_id, "AI 응답 생성 중…"), daemon=True).start()
                return {'FINISHED'}


# ==============================================================================
# Operators: Direct API Setup Dialog & Open Preferences
# ==============================================================================

class MCPCHAT_OT_api_settings_dialog(TOp):
    """Direct API 설정 (Provider, API Key, Model 변경)"""
    bl_idname = "mcpchat.api_settings_dialog"
    bl_label = "Direct API 설정"
    bl_options = {'REGISTER', 'UNDO'}

    provider: EnumProperty(
        name="Provider",
        items=[
            ('openrouter', "OpenRouter", "OpenRouter AI"),
            ('nvidia_nim', "NVIDIA NIM", "NVIDIA NIM Cloud API"),
            ('local', "Local / Ollama", "Local Ollama or LM Studio"),
            ('custom', "Custom Endpoint", "Custom OpenAI-compatible"),
        ],
        default='openrouter'
    )
    api_key: StringProperty(name="API Key", subtype='PASSWORD', default="")
    model_name: StringProperty(name="Model", default="")
    base_url: StringProperty(name="Base URL", default="")

    def invoke(self, context, event):
        prefs = context.preferences.addons.get(__name__)
        if prefs:
            p = prefs.preferences
            self.provider = p.active_provider
            if self.provider == 'openrouter':
                self.api_key = p.openrouter_api_key
                self.model_name = p.openrouter_model
                self.base_url = ""
            elif self.provider == 'nvidia_nim':
                self.api_key = p.nvidia_nim_api_key
                self.model_name = p.nvidia_nim_model
                self.base_url = ""
            elif self.provider == 'local':
                self.api_key = ""
                self.model_name = p.local_model
                self.base_url = p.local_base_url
            else:
                self.api_key = p.custom_api_key
                self.model_name = p.custom_model
                self.base_url = p.custom_base_url
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = tl(self.layout)
        layout.prop(self, "provider")
        if self.provider in ('openrouter', 'nvidia_nim', 'custom'):
            layout.prop(self, "api_key")
            if secrets_store.has(f"{self.provider}_api_key"):
                layout.label(text="저장된 키가 있습니다 (비워 두면 유지)", icon='LOCKED')
        layout.prop(self, "model_name")
        if self.provider in ('local', 'custom'):
            layout.prop(self, "base_url")

    def execute(self, context):
        prefs = context.preferences.addons.get(__name__)
        if prefs:
            p = prefs.preferences
            p.active_provider = self.provider
            if self.provider == 'openrouter':
                p.openrouter_api_key = self.api_key
                p.openrouter_model = self.model_name
            elif self.provider == 'nvidia_nim':
                p.nvidia_nim_api_key = self.api_key
                p.nvidia_nim_model = self.model_name
            elif self.provider == 'local':
                p.local_base_url = self.base_url
                p.local_model = self.model_name
            else:
                p.custom_api_key = self.api_key
                p.custom_model = self.model_name
                p.custom_base_url = self.base_url

        session_mgr.set_setting("active_provider", self.provider)
        if self.provider == 'openrouter':
            if self.api_key:
                session_mgr.set_setting("openrouter_api_key", self.api_key)
            session_mgr.set_setting("openrouter_model", self.model_name)
        elif self.provider == 'nvidia_nim':
            if self.api_key:
                session_mgr.set_setting("nvidia_nim_api_key", self.api_key)
            session_mgr.set_setting("nvidia_nim_model", self.model_name)
        elif self.provider == 'local':
            session_mgr.set_setting("local_base_url", self.base_url)
            session_mgr.set_setting("local_model", self.model_name)
        else:
            if self.api_key:
                session_mgr.set_setting("custom_api_key", self.api_key)
            session_mgr.set_setting("custom_model", self.model_name)
            session_mgr.set_setting("custom_base_url", self.base_url)

        self.report({'INFO'}, f"Direct API 설정 저장됨 ({self.provider}: {self.model_name})")
        return {'FINISHED'}


class MCPCHAT_OT_edit_user_rules(TOp):
    """사용자 작업 지침 편집 (모든 AI 작업에 적용)"""
    bl_idname = "mcpchat.edit_user_rules"
    bl_label = "사용자 작업 지침"

    rules: StringProperty(name="지침", description="여러 개는 ; 로 구분", default="")

    def invoke(self, context, event):
        pref = context.preferences.addons.get(__name__)
        self.rules = pref.preferences.user_rules if pref else session_mgr.get_setting("user_rules", "")
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        col = tl(self.layout).column()
        col.label(text="모든 작업에 적용할 지침 (여러 개는 ; 로 구분)", icon='TEXT')
        col.prop(self, "rules", text="")
        col.label(text="예) 베벨은 2단계; 베벨 면에 검은색 버텍스 컬러 적용")

    def execute(self, context):
        pref = context.preferences.addons.get(__name__)
        if pref:
            pref.preferences.user_rules = self.rules
        session_mgr.set_setting("user_rules", self.rules)
        self.report({'INFO'}, "사용자 작업 지침이 저장되었습니다." if self.rules.strip() else "사용자 작업 지침이 비워졌습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_copy_termux_command(TOp):
    """Termux에서 실행할 원라인 설치 명령을 클립보드에 복사"""
    bl_idname = "mcpchat.copy_termux_command"
    bl_label = "Termux 설치 명령 복사"

    def execute(self, context):
        ips = server.get_lan_ips()
        if not ips:
            self.report({'ERROR'}, "LAN IP를 찾지 못했습니다. 네트워크 연결을 확인하세요.")
            return {'CANCELLED'}
        port = server_mgr.port if server_mgr.is_running else context.preferences.addons[__name__].preferences.default_port
        token = session_mgr.get_or_create_token()
        cmd = f'curl -fsS -H "Authorization: Bearer {token}" http://{ips[0]}:{port}/termux/setup.sh | bash'
        context.window_manager.clipboard = cmd
        self.report({'INFO'}, f"복사됨: Termux에 붙여넣기 ({ips[0]}:{port})")
        return {'FINISHED'}


class MCPCHAT_OT_regenerate_token(TOp):
    """LAN 접속 토큰 재발급 (기존 Termux 연결은 재설정 필요)"""
    bl_idname = "mcpchat.regenerate_token"
    bl_label = "토큰 재발급"

    def execute(self, context):
        session_mgr.regenerate_token()
        self.report({'INFO'}, "토큰이 재발급되었습니다. Termux에서 설치 명령을 다시 실행하세요.")
        return {'FINISHED'}


def _current_version() -> tuple:
    return tuple(bl_info["version"])


def _current_version_str() -> str:
    return updater.format_version(_current_version())


def _tag_prefs_redraw():
    def _t():
        try:
            for win in bpy.context.window_manager.windows:
                for area in win.screen.areas:
                    area.tag_redraw()
        except Exception:
            pass
        return None
    try:
        bpy.app.timers.register(_t, first_interval=0.1)
    except Exception:
        pass


RULES_TEXT_NAME = "MCP Execution Rules"


class MCPCHAT_OT_edit_rules(TOp):
    """현재 적용 중인 Blender Execution Rules를 텍스트 창에서 편집"""
    bl_idname = "mcpchat.edit_rules"
    bl_label = "규칙 편집"

    def execute(self, context):
        current = guidelines.get_guidelines().rstrip(chr(10))
        if show_text_block(context, RULES_TEXT_NAME, current):
            self.report({'INFO'}, "텍스트 창에서 규칙을 수정한 뒤 '편집 내용 저장'을 누르세요.")
        else:
            self.report({'WARNING'}, f"텍스트 에디터를 열 수 없습니다. Text Editor에서 '{RULES_TEXT_NAME}'를 선택해 수정하세요.")
        return {'FINISHED'}


class MCPCHAT_OT_save_rules(TOp):
    """텍스트 창에서 수정한 규칙을 저장 (기본 규칙과 같으면 기본값으로 되돌림)"""
    bl_idname = "mcpchat.save_rules"
    bl_label = "편집 내용 저장"

    def execute(self, context):
        txt = bpy.data.texts.get(RULES_TEXT_NAME)
        if txt is None:
            self.report({'WARNING'}, "먼저 '규칙 편집'을 눌러 규칙을 불러오세요.")
            return {'CANCELLED'}
        body = txt.as_string().strip()
        if not body or body == guidelines.GUIDELINES.strip():
            session_mgr.set_setting("custom_guidelines", "")
            self.report({'INFO'}, "기본 규칙을 사용합니다.")
        else:
            session_mgr.set_setting("custom_guidelines", body)
            self.report({'INFO'}, "수정한 규칙이 저장되었습니다. 이후 모든 요청에 적용됩니다.")
        return {'FINISHED'}


class MCPCHAT_OT_reset_rules(TOp):
    """수정한 규칙을 버리고 기본 규칙으로 복원"""
    bl_idname = "mcpchat.reset_rules"
    bl_label = "기본값 복원"

    def execute(self, context):
        session_mgr.set_setting("custom_guidelines", "")
        txt = bpy.data.texts.get(RULES_TEXT_NAME)
        if txt is not None:
            txt.clear()
            txt.write(guidelines.GUIDELINES.rstrip(chr(10)))
        self.report({'INFO'}, "기본 규칙으로 복원했습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_check_update(TOp):
    """GitHub Releases에서 최신 버전 확인"""
    bl_idname = "mcpchat.check_update"
    bl_label = "업데이트 확인"

    def execute(self, context):
        if updater.state["checking"]:
            return {'CANCELLED'}
        updater.state.update({"checking": True, "message": "", "installed": False})

        def _work():
            try:
                updater.state["info"] = updater.check_latest(_current_version())
            finally:
                updater.state["checking"] = False
                _tag_prefs_redraw()

        threading.Thread(target=_work, daemon=True).start()
        return {'FINISHED'}


class MCPCHAT_OT_install_update(TOp):
    """최신 릴리즈를 내려받아 설치 (설치 후 Blender 재시작 필요)"""
    bl_idname = "mcpchat.install_update"
    bl_label = "업데이트 설치"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        info = updater.state.get("info") or {}
        if not info.get("newer") or updater.state["installing"]:
            return {'CANCELLED'}
        updater.state.update({"installing": True, "message": ""})
        url = info.get("asset_url", "")

        def _work():
            try:
                ok, msg = updater.install(url, _current_version())
                updater.state["message"] = msg
                updater.state["installed"] = ok
                if ok:
                    updater.state["info"] = None
            finally:
                updater.state["installing"] = False
                _tag_prefs_redraw()

        threading.Thread(target=_work, daemon=True).start()
        self.report({'INFO'}, "업데이트를 내려받는 중입니다.")
        return {'FINISHED'}


class MCPCHAT_OT_open_url(TOp):
    """웹 브라우저에서 주소 열기 (https만 허용)"""
    bl_idname = "mcpchat.open_url"
    bl_label = "열기"

    url: StringProperty()

    def execute(self, context):
        if self.url.startswith("https://"):
            webbrowser.open(self.url)
        return {'FINISHED'}


class MCPCHAT_OT_delete_secret(TOp):
    """저장된 키/토큰 삭제"""
    bl_idname = "mcpchat.delete_secret"
    bl_label = "저장된 키 삭제"

    name: StringProperty()

    def execute(self, context):
        if self.name in secrets_store.SECRET_KEYS:
            secrets_store.delete(self.name)
            self.report({'INFO'}, "저장된 키가 삭제되었습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_wipe_all_data(TOp):
    """대화 기록, 설정, 출력 파일, 암호화된 키를 모두 삭제 (애드온 삭제 전 정리용)"""
    bl_idname = "mcpchat.wipe_all_data"
    bl_label = "모든 데이터 삭제"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            secrets_store.wipe()
            data_dir = session_manager.get_safe_data_dir()
            for fname in ("chat_data.db", "chat_data.db-wal", "chat_data.db-shm"):
                try:
                    os.remove(os.path.join(data_dir, fname))
                except FileNotFoundError:
                    pass
            shutil.rmtree(os.path.join(data_dir, "output"), ignore_errors=True)
            session_mgr._init_db()
            sid = session_mgr.get_tab_session_id(0)
            context.scene.mcpchat_active_tab = 0
            sync_messages_to_ui(context.scene, sid)
        except Exception as e:
            self.report({'ERROR'}, f"삭제 실패: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, "모든 데이터가 삭제되었습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_open_preferences(TOp):
    """Open MCP Chat Preferences in Blender"""
    bl_idname = "mcpchat.open_preferences"
    bl_label = "Direct API 설정 열기"
    bl_icon = 'PREFERENCES'

    def execute(self, context):
        try:
            bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
            context.preferences.active_section = 'ADDONS'
        except Exception:
            pass
        return {'FINISHED'}


# ==============================================================================
# Operators: Task Queue Controls & Management
# ==============================================================================

class MCPCHAT_OT_start_queue(TOp):
    """Start sequential execution of the Task Queue"""
    bl_idname = "mcpchat.start_queue"
    bl_label = "작업 개시"
    bl_icon = 'PLAY'

    def execute(self, context):
        task_queue.resume()
        task_queue.start()
        self.report({'INFO'}, "작업 큐를 개시했습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_add_task_to_queue(TOp):
    """현재 프롬프트와 이미지를 작업 큐에 등록"""
    bl_idname = "mcpchat.add_task_to_queue"
    bl_label = "큐 등록"
    bl_icon = 'DUPLICATE'

    def execute(self, context):
        scene = context.scene
        prompt = scene.mcpchat_prompt.strip()
        if not prompt and len(scene.mcpchat_attached_images) == 0:
            self.report({'WARNING'}, "큐에 등록할 프롬프트 또는 이미지를 입력하세요.")
            return {'CANCELLED'}

        images = [img.data_b64 for img in scene.mcpchat_attached_images if img.data_b64]
        title = prompt.splitlines()[0][:30] if prompt else "이미지 기반 큐 작업"
        payload = {
            "prompt": prompt,
            "images": images,
            "backend": scene.mcpchat_backend
        }
        # Direct API 엔진은 CLI가 아니라 API로 계획/실행 (이전에는 API 선택 시에도 claude CLI로 실행되던 버그)
        task_type = "auto_plan" if scene.mcpchat_backend == 'API' else "prompt"

        scene.mcpchat_prompt = ""
        scene.mcpchat_attached_images.clear()

        session_mgr.enqueue_task(
            title=title,
            task_type=task_type,
            payload=payload
        )
        self.report({'INFO'}, f"작업 '{title}'(이)가 큐에 등록되었습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_delete_queue_task(TOp):
    """선택한 큐 작업 삭제"""
    bl_idname = "mcpchat.delete_queue_task"
    bl_label = "작업 삭제"
    bl_icon = 'TRASH'

    task_id: StringProperty()

    def execute(self, context):
        if self.task_id:
            session_mgr.delete_task(self.task_id)
            self.report({'INFO'}, "큐 작업이 삭제되었습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_edit_queue_task(TOp):
    """큐 작업 수정 (제목 및 내용 수정)"""
    bl_idname = "mcpchat.edit_queue_task"
    bl_label = "작업 수정"
    bl_options = {'REGISTER', 'UNDO'}

    task_id: StringProperty()
    title: StringProperty(name="작업 제목", default="")
    content: StringProperty(name="프롬프트 / 코드", default="")

    def invoke(self, context, event):
        task = session_mgr.get_task(self.task_id)
        if task:
            self.title = task.get("title", "")
            payload = task.get("payload", {})
            if task.get("task_type") == "prompt":
                self.content = payload.get("prompt", "")
            else:
                self.content = payload.get("code", "")
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = tl(self.layout)
        layout.prop(self, "title")
        if hasattr(layout, "textbox"):
            layout.textbox(self, "content", initial_visible_lines=4)
        else:
            layout.prop(self, "content")

    def execute(self, context):
        if not self.task_id:
            return {'CANCELLED'}
        session_mgr.update_task_payload(self.task_id, self.title.strip(), self.content.strip())
        self.report({'INFO'}, f"작업 '{self.title}'(이)가 수정되었습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_toggle_queue(TOp):
    """Pause or Resume Task Queue Worker"""
    bl_idname = "mcpchat.toggle_queue"
    bl_label = "Pause/Resume Queue"
    bl_icon = 'PLAY'

    def execute(self, context):
        if task_queue.is_paused:
            task_queue.resume()
            task_queue.start()
            self.report({'INFO'}, "Task Queue resumed")
        else:
            task_queue.pause()
            self.report({'INFO'}, "Task Queue paused")
        return {'FINISHED'}


class MCPCHAT_OT_clear_queue(TOp):
    """Clear all tasks in the Task Queue"""
    bl_idname = "mcpchat.clear_queue"
    bl_label = "Clear Queue"
    bl_icon = 'CANCEL'

    def execute(self, context):
        session_mgr.clear_queue()
        self.report({'INFO'}, "Task Queue cleared")
        return {'FINISHED'}


class MCPCHAT_OT_setup_claude_cli(TOp):
    """Register Blender MCP in Claude Code ~/.claude.json"""
    bl_idname = "mcpchat.setup_claude_cli"
    bl_label = "Setup Claude Code MCP"
    bl_icon = 'CONSOLE'

    def execute(self, context):
        ok, msg = cli_runner.configure_claude_code_mcp()
        if ok:
            self.report({'INFO'}, msg)
        else:
            self.report({'ERROR'}, msg)
        return {'FINISHED'}


class MCPCHAT_OT_test_agent(TOp):
    """Termux Agent 연결 및 CLI 감지 테스트"""
    bl_idname = "mcpchat.test_agent"
    bl_label = "Agent 연결 테스트"

    def execute(self, context):
        p = context.preferences.addons[__name__].preferences
        session_mgr.set_setting("cli_remote_url", p.cli_remote_url)
        if p.cli_remote_token:
            session_mgr.set_setting("cli_remote_token", p.cli_remote_token)
            p.cli_remote_token = ""
        ok, msg = cli_runner.agent_health()
        self.report({'INFO'} if ok else {'ERROR'}, msg)
        return {'FINISHED'}


class MCPCHAT_OT_setup_codex_cli(TOp):
    """Register Blender MCP in ~/.codex/config.toml"""
    bl_idname = "mcpchat.setup_codex_cli"
    bl_label = "Setup Codex CLI MCP"
    bl_icon = 'CONSOLE'

    def execute(self, context):
        ok, msg = cli_runner.configure_codex_mcp()
        self.report({'INFO'} if ok else {'ERROR'}, msg)
        return {'FINISHED'}


class MCPCHAT_OT_setup_agy_cli(TOp):
    """Register Blender MCP in agy mcp_config.json"""
    bl_idname = "mcpchat.setup_agy_cli"
    bl_label = "Setup agy CLI MCP"
    bl_icon = 'SETTINGS'

    def execute(self, context):
        ok, msg = cli_runner.configure_agy_cli_mcp()
        if ok:
            self.report({'INFO'}, msg)
        else:
            self.report({'ERROR'}, msg)
        return {'FINISHED'}


class MCPCHAT_OT_start_server(TOp):
    """Start the Blender MCP & Web Chat Server"""
    bl_idname = "mcpchat.start_server"
    bl_label = "Start Server"
    bl_icon = 'PLAY'

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        port = prefs.default_port
        success, msg = server_mgr.start(port=port)
        if success:
            self.report({'INFO'}, msg)
        else:
            self.report({'ERROR'}, msg)
        return {'FINISHED'}


class MCPCHAT_OT_stop_server(TOp):
    """Stop the Blender MCP & Web Chat Server"""
    bl_idname = "mcpchat.stop_server"
    bl_label = "Stop Server"
    bl_icon = 'PAUSE'

    def execute(self, context):
        success, msg = server_mgr.stop()
        if success:
            self.report({'INFO'}, msg)
        else:
            self.report({'ERROR'}, msg)
        return {'FINISHED'}


class MCPCHAT_OT_open_browser(TOp):
    """Open the Web Chat UI in browser"""
    bl_idname = "mcpchat.open_browser"
    bl_label = "Open Web Chat UI"
    bl_icon = 'WINDOW'

    def execute(self, context):
        port = server_mgr.port
        url = f"http://127.0.0.1:{port}"
        try:
            webbrowser.open(url)
            self.report({'INFO'}, f"Opening {url}")
        except Exception as e:
            self.report({'WARNING'}, f"Please open {url} in your browser.")
        return {'FINISHED'}


# ==============================================================================
# Panels in 3D Viewport N-Panel
# ==============================================================================

class MCPCHAT_PT_chat_panel(Panel):
    """Main In-Blender Chat Console with 1-3 Tabs, 8-line History, Input Field & Send Button Below"""
    bl_label = "MCP Chat & AI Console"
    bl_idname = "MCPCHAT_PT_chat_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"
    bl_order = 0

    def draw(self, context):
        layout = tl(self.layout)
        scene = context.scene

        try:
            # -------------------------------------------------------------
            # 1. 1 to 3 Session Tabs: [ 세션 1: 이름 ] ... [ + ]
            # -------------------------------------------------------------
            mgr = session_manager.session_mgr
            tab_sessions = mgr.get_tab_sessions(3) if hasattr(mgr, "get_tab_sessions") else [{"title": "세션 1"}]
            raw_idx = getattr(scene, "mcpchat_active_tab", 0)
            # NOTE: draw() 중에는 씬 속성을 쓰면 안 됨 (읽기 전용 컨텍스트) -> 로컬 보정만 수행
            active_idx = max(0, min(len(tab_sessions) - 1, raw_idx))

            row_tabs = layout.row(align=True)
            for i, tab in enumerate(tab_sessions):
                is_active = (active_idx == i)
                s_title = tab.get("title") or f"세션 {i + 1}"
                disp_title = (s_title[:7] + "..") if len(s_title) > 8 else s_title
                sub = row_tabs.row(align=True)
                op = sub.operator("mcpchat.switch_tab", text=disp_title, depress=is_active)
                op.tab_index = i

            if len(tab_sessions) < 3:
                add_sub = row_tabs.row(align=True)
                add_sub.operator("mcpchat.add_session_tab", text="", icon='ADD')

            # Mode Switcher: Chat, Plan, Auto in 1 row with 3 columns
            row_mode = layout.row(align=True)
            if hasattr(scene, "mcpchat_mode"):
                row_mode.prop(scene, "mcpchat_mode", expand=True)

            # Engine Picker with Direct API Settings dialog button
            row_eng = layout.row(align=True)
            if hasattr(scene, "mcpchat_backend"):
                row_eng.prop(scene, "mcpchat_backend", text="Engine")
            row_eng.operator("mcpchat.api_settings_dialog", text="", icon='PREFERENCES')

            # 엔진별 모델 / 추론성능 (선택한 엔진만 표시)
            backend_now = scene.mcpchat_backend
            if backend_now in CLI_ENGINES:
                key = CLI_ENGINES[backend_now][0]
                row_set = layout.row(align=True)
                row_set.prop(scene, f"mcpchat_{key}_model_sel", text="모델")
                row_set.prop(scene, f"mcpchat_{key}_effort", text="")
                if getattr(scene, f"mcpchat_{key}_model_sel", "") == "CUSTOM":
                    layout.prop(scene, f"mcpchat_{key}_model", text="모델 ID")

            # 사용자 작업 지침 (모든 작업에 적용) - N패널에서 바로 입력
            prefs_obj = context.preferences.addons.get(__name__)
            if prefs_obj:
                row_rules = layout.row(align=True)
                row_rules.prop(prefs_obj.preferences, "user_rules", text="", icon='TEXT')

            # -------------------------------------------------------------
            # 2. 8-Row Scrollable Chat History (UIList)
            # -------------------------------------------------------------
            box_history = layout.box()
            active_s = tab_sessions[active_idx] if active_idx < len(tab_sessions) else None
            active_title = active_s["title"] if active_s else f"세션 {active_idx + 1}"

            row_h_head = box_history.row(align=True)
            row_h_head.label(text=f"{active_title}", icon='COMMUNITY')
            rename_op = row_h_head.operator("mcpchat.rename_session_tab", text="이름 변경", icon='GREASEPENCIL')
            rename_op.tab_index = active_idx
            row_h_head.operator("mcpchat.reload_addon", text="", icon='FILE_REFRESH')
            row_h_head.operator("mcpchat.compact_history", text="", icon='FULLSCREEN_EXIT')
            row_h_head.operator("mcpchat.clear_history", text="", icon='X')
            row_h_head.operator("mcpchat.delete_session_tab", text="", icon='TRASH')

            # 멀티라인 채팅 히스토리: 네이티브 스크롤바 / 마우스 휠 / 하단 핸들로 크기 조절
            if len(scene.mcpchat_lines) == 0:
                box_history.label(text="대화 기록이 없습니다. 프롬프트를 입력하세요.", icon='INFO')
            else:
                rows = HISTORY_ROWS
                box_history.template_list(
                    "MCPCHAT_UL_lines", "", scene, "mcpchat_lines", scene, "mcpchat_active_line",
                    rows=rows, maxrows=rows
                )
                row_rows = box_history.row(align=True)
                row_rows.alignment = 'RIGHT'
                row_rows.prop(scene, "mcpchat_wrap_cells")

            layout.separator(factor=0.5)

            # -------------------------------------------------------------
            # 3. Attached Images Strip (Max 3 Total)
            # -------------------------------------------------------------
            attached_count = len(scene.mcpchat_attached_images)
            if attached_count > 0:
                box_imgs = layout.box()
                box_imgs.label(text=f"첨부 이미지 ({attached_count}/3)", icon='IMAGE_DATA')
                grid = box_imgs.row(align=True)
                for idx, img in enumerate(scene.mcpchat_attached_images):
                    col = grid.column(align=True)
                    icon_id = get_preview_icon(img)
                    if icon_id:
                        col.template_icon(icon_value=icon_id, scale=2.2)
                    else:
                        col.label(text="", icon='IMAGE_DATA')
                    row_n = col.row(align=True)
                    row_n.label(text=img.name[:8], icon='RESTRICT_RENDER_OFF' if img.is_viewport else 'FILE_IMAGE')
                    del_op = row_n.operator("mcpchat.remove_attached_image", text="", icon='X')
                    del_op.index = idx

            # -------------------------------------------------------------
            # 4. Input Row: [ ➕ 첨부 ] [ 프롬프트 입력창 ] (Multiline button removed)
            # -------------------------------------------------------------
            pend_sid = tab_sessions[active_idx].get("id") if active_idx < len(tab_sessions) else None
            pend = session_mgr.get_pending_plan(pend_sid) if pend_sid else None
            if pend:
                box_plan = layout.box()
                box_plan.label(text=f"계획 검토: {str(pend.get('title', ''))[:26]}", icon='TEXT')
                row_pl = box_plan.row(align=True)
                row_pl.scale_y = 1.2
                row_pl.operator("mcpchat.plan_execute", text="실행", icon='PLAY')
                row_pl.operator("mcpchat.plan_refine", text="계속 계획", icon='GREASEPENCIL',
                                depress=scene.mcpchat_plan_refine)
                row_pl.operator("mcpchat.plan_cancel", text="", icon='X')
                if scene.mcpchat_plan_refine:
                    box_plan.label(text="수정/추가 요청을 입력하고 전송하세요", icon='INFO')

            row_input = layout.row(align=True)
            row_input.menu("MCPCHAT_MT_attach_menu", text="", icon='ADD')
            row_input.operator("mcpchat.paste_prompt", text="", icon='PASTEDOWN')
            if hasattr(row_input, "textbox"):
                row_input.textbox(scene, "mcpchat_prompt", initial_visible_lines=2)
            else:
                row_input.prop(scene, "mcpchat_prompt", text="")

            # -------------------------------------------------------------
            # 5. Buttons Row Below Input: [ 전송 ] [ 큐 등록 ]
            # -------------------------------------------------------------
            row_btn = layout.row(align=True)
            row_btn.scale_y = 1.3
            send_icon = 'PLAY'
            if scene.mcpchat_mode == 'PLAN':
                send_icon = 'TEXT'
            elif scene.mcpchat_mode == 'AUTO':
                send_icon = 'AUTO'
            row_btn.operator("mcpchat.send_message", text="전송", icon=send_icon)
            row_btn.operator("mcpchat.add_task_to_queue", text="큐 등록", icon='DUPLICATE')
            row_btn.operator("mcpchat.preview_prompt", text="", icon='VIEWZOOM')

        except Exception as e:
            layout.label(text=f"채팅 콘솔 로딩 오류: {e}", icon='ERROR')


class MCPCHAT_PT_queue_panel(Panel):
    """Task Queue & Auto-Save Panel"""
    bl_label = "Task Queue & Auto-Save"
    bl_idname = "MCPCHAT_PT_queue_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"
    bl_order = 1

    def draw(self, context):
        layout = tl(self.layout)
        scene = context.scene

        try:
            status = task_queue.get_status()
            counts = status.get("counts", {})
            is_paused = status.get("is_paused", False)

            box_status = layout.box()
            state_icon = 'PAUSE' if is_paused else 'PLAY'
            state_str = "PAUSED (일시정지)" if is_paused else "RUNNING (동작중)"
            box_status.label(text=f"Queue Worker: {tr(state_str)}", icon=state_icon)
            
            row_counts = box_status.row(align=True)
            row_counts.label(text=f"대기: {counts.get('pending', 0)}")
            row_counts.label(text=f"실행중: {counts.get('running', 0)}")
            row_counts.label(text=f"완료: {counts.get('completed', 0)}")

            # Play / Pause Controls
            row_ctrl = layout.row(align=True)
            row_ctrl.scale_y = 1.3
            row_ctrl.operator("mcpchat.start_queue", text="작업 개시", icon='PLAY')
            row_ctrl.operator("mcpchat.toggle_queue", text="일시정지" if not is_paused else "재개", icon='PAUSE' if not is_paused else 'PLAY')
            row_ctrl.operator("mcpchat.clear_queue", text="비우기", icon='CANCEL')
            done_op = layout.operator("mcpchat.queue_task_action", text="완료/실패 항목 정리", icon='BRUSH_DATA')
            done_op.action = "clear_done"

            # Global Delay
            if hasattr(scene, "mcpchat_queue_delay"):
                row_opt = layout.row(align=True)
                row_opt.prop(scene, "mcpchat_queue_delay", text="전역 딜레이(초)")

            # List of Tasks in Queue
            layout.separator(factor=0.5)
            tasks = session_mgr.list_queue_tasks(limit=30, light=True)
            prompt_keys_q = session_mgr.sent_prompt_keys()
            if tasks:
                box_tasks = layout.box()
                box_tasks.label(text=f"작업 큐 목록 ({len(tasks)}개):", icon='LINENUMBERS_ON')
                STATUS_UI = {
                    'pending':   ("대기", 'TIME'),
                    'running':   ("실행중", 'PLAY'),
                    'completed': ("완료", 'CHECKBOX_HLT'),
                    'failed':    ("실패", 'ERROR'),
                    'cancelled': ("취소", 'CANCEL'),
                }
                for n, t in enumerate(tasks, 1):
                    t_id = t["id"]
                    t_status = t.get("status", "pending")
                    t_title = t.get("title", "작업")
                    st_label, status_icon = STATUS_UI.get(t_status, (t_status, 'TIME'))

                    item_box = box_tasks.box()
                    row_h = item_box.row(align=True)
                    row_h.alert = (t_status == 'failed')
                    row_h.active = (t_status != 'completed')   # 완료 항목은 흐리게
                    row_h.label(text=f"{n}. {t_title[:22]}")

                    badge = row_h.row(align=True)
                    badge.alignment = 'RIGHT'
                    badge.label(text="", icon=status_icon)

                    row_t = item_box.row(align=True)
                    if t_status == 'pending':
                        up = row_t.operator("mcpchat.move_queue_task", text="", icon='TRIA_UP')
                        up.task_id, up.direction = t_id, -1
                        dn = row_t.operator("mcpchat.move_queue_task", text="", icon='TRIA_DOWN')
                        dn.task_id, dn.direction = t_id, 1
                        edit_op = row_t.operator("mcpchat.edit_queue_task", text="", icon='GREASEPENCIL')
                        edit_op.task_id = t_id
                    else:
                        if t_status != 'running':
                            rt = row_t.operator("mcpchat.queue_task_action", text="", icon='FILE_REFRESH')
                            rt.task_id, rt.action = t_id, "retry"
                        dp = row_t.operator("mcpchat.queue_task_action", text="", icon='DUPLICATE')
                        dp.task_id, dp.action = t_id, "duplicate"

                    if t_id in prompt_keys_q:
                        vp = row_t.operator("mcpchat.view_sent_prompt", text="", icon='TEXT')
                        vp.key = t_id

                    del_op = row_t.operator("mcpchat.delete_queue_task", text="", icon='TRASH')
                    del_op.task_id = t_id

                    if t_status == 'running' and status.get("progress"):
                        item_box.label(text=f"   {status['progress']}", icon='PLAY')
                    if t_status == 'completed':
                        outs = [os.path.basename(p) for p in (t.get("output_blend"), t.get("output_glb"), t.get("output_image")) if p]
                        if outs:
                            item_box.label(text="   " + " / ".join(outs)[:44], icon='FILE_TICK')
                    elif t_status == 'failed' and t.get("error"):
                        item_box.label(text=f"   {str(t['error'])[:44]}", icon='ERROR')
            else:
                layout.label(text="등록된 큐 작업이 없습니다.", icon='INFO')

            layout.separator(factor=0.5)
            box_out = layout.box()
            box_out.label(text="저장 위치", icon='FILE_FOLDER')
            box_out.prop(scene, "mcpchat_output_dir", text="")
            row_pk = box_out.row(align=True)
            row_pk.prop(scene, "mcpchat_auto_save_pack", toggle=True)
            row_pk.prop(scene, "mcpchat_auto_save_glb", toggle=True)
            box_out.label(text="자동 저장:", icon='FILE_TICK')
            row_save = box_out.row(align=True)
            row_save.prop(scene, "mcpchat_auto_save_blend", toggle=True)
            row_save.prop(scene, "mcpchat_auto_save_image", toggle=True)

        except Exception as e:
            layout.label(text=f"작업큐 로딩 오류: {e}", icon='ERROR')


class MCPCHAT_PT_cli_panel(Panel):
    """Claude Code CLI & agy CLI Integration Panel"""
    bl_label = "Claude Code & agy CLI"
    bl_idname = "MCPCHAT_PT_cli_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = tl(self.layout)

        env = cli_runner.detect_environment()
        os_name = env["os_name"]
        claude_path = env["claude_bin"]
        agy_path = env["agy_bin"]

        box_env = layout.box()
        env_icon = 'DESKTOP' if env["is_windows"] else ('COMMUNITY' if env["is_termux"] else 'HELP')
        box_env.label(text=f"환경 감지: {os_name}", icon=env_icon)

        box = layout.box()
        if claude_path:
            short_name = os.path.basename(claude_path)
            box.label(text=f"Claude Code: 감지됨 ({short_name})", icon='CHECKMARK')
        else:
            box.label(text="Claude Code: 미감지", icon='X')

        if agy_path:
            short_name = os.path.basename(agy_path)
            box.label(text=f"agy CLI: 감지됨 ({short_name})", icon='CHECKMARK')
        else:
            box.label(text="agy CLI: 미감지", icon='X')

        layout.separator()
        col = layout.column(align=True)
        col.operator("mcpchat.setup_claude_cli", text="Claude Code MCP 자동 등록", icon='CONSOLE')
        col.operator("mcpchat.setup_agy_cli", text="agy CLI MCP 자동 등록", icon='SETTINGS')


class MCPCHAT_PT_server_panel(Panel):
    """Server & Mobile Web UI Panel"""
    bl_label = "Server & Mobile Web UI"
    bl_idname = "MCPCHAT_PT_server_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = tl(self.layout)
        is_running = server_mgr.is_running
        port = server_mgr.port

        box = layout.box()
        if is_running:
            box.label(text=f"Server: Online (Port {port})", icon='RADIOBUT_ON')
            sub = box.row()
            sub.operator("mcpchat.stop_server", text="Stop Server", icon='PAUSE')
            box.separator()
            btn_row = box.row()
            btn_row.scale_y = 1.3
            btn_row.operator("mcpchat.open_browser", text="Open Web Chat UI", icon='WINDOW')
        else:
            box.label(text="Server: Offline", icon='RADIOBUT_OFF')
            sub = box.row()
            sub.operator("mcpchat.start_server", text="Start Server", icon='PLAY')


# ==============================================================================
# Registration
# ==============================================================================

classes = (
    MCPChatMessageItem,
    MCPChatLineItem,
    MCPChatAttachedImage,
    MCPChatPreferences,
    MCPCHAT_UL_lines,
    MCPCHAT_MT_attach_menu,
    MCPCHAT_OT_switch_tab,
    MCPCHAT_OT_add_session_tab,
    MCPCHAT_OT_delete_session_tab,
    MCPCHAT_OT_rename_session_tab,
    MCPCHAT_OT_reload_addon,
    MCPCHAT_OT_copy_message,
    MCPCHAT_OT_toggle_message,
    MCPCHAT_OT_scroll_history,
    MCPCHAT_OT_clear_history,
    MCPCHAT_OT_compact_history,
    MCPCHAT_OT_paste_prompt,
    MCPCHAT_OT_plan_execute,
    MCPCHAT_OT_plan_refine,
    MCPCHAT_OT_plan_cancel,
    MCPCHAT_OT_preview_prompt,
    MCPCHAT_OT_view_sent_prompt,
    MCPCHAT_OT_setup_codex_cli,
    MCPCHAT_OT_test_agent,
    MCPCHAT_OT_move_queue_task,
    MCPCHAT_OT_queue_task_action,
    MCPCHAT_OT_select_local_image,
    MCPCHAT_OT_attach_viewport_snapshot,
    MCPCHAT_OT_remove_attached_image,
    MCPCHAT_OT_send_message,
    MCPCHAT_OT_api_settings_dialog,
    MCPCHAT_OT_edit_user_rules,
    MCPCHAT_OT_copy_termux_command,
    MCPCHAT_OT_regenerate_token,
    MCPCHAT_OT_edit_rules,
    MCPCHAT_OT_save_rules,
    MCPCHAT_OT_reset_rules,
    MCPCHAT_OT_check_update,
    MCPCHAT_OT_install_update,
    MCPCHAT_OT_open_url,
    MCPCHAT_OT_delete_secret,
    MCPCHAT_OT_wipe_all_data,
    MCPCHAT_OT_open_preferences,
    MCPCHAT_OT_start_queue,
    MCPCHAT_OT_toggle_queue,
    MCPCHAT_OT_clear_queue,
    MCPCHAT_OT_add_task_to_queue,
    MCPCHAT_OT_delete_queue_task,
    MCPCHAT_OT_edit_queue_task,
    MCPCHAT_OT_setup_claude_cli,
    MCPCHAT_OT_setup_agy_cli,
    MCPCHAT_OT_start_server,
    MCPCHAT_OT_stop_server,
    MCPCHAT_OT_open_browser,
    MCPCHAT_PT_chat_panel,
    MCPCHAT_PT_queue_panel,
)


def on_delay_change(self, context):
    try:
        val = str(int(self.mcpchat_queue_delay))
        session_mgr.set_setting("queue_delay_seconds", val)
    except Exception:
        pass


def auto_start_timer():
    try:
        addon = bpy.context.preferences.addons.get(__name__)
        if addon and addon.preferences.autostart:
            server_mgr.start(port=addon.preferences.default_port)
    except Exception:
        pass
    return None


def init_ui_timer():
    """Initializes UIList with active session messages safely from outside draw()"""
    try:
        scene = bpy.context.scene
        pref = bpy.context.preferences.addons.get(__name__)
        if pref:
            _apply_language(pref.preferences)
            # 백그라운드 워커(auto_plan 등)가 읽는 API 설정을 settings DB에 동기화
            for _k in secrets_store.SECRET_KEYS:      # 이전 버전이 사용자 설정에 평문 저장한 값을 금고로 이전
                if hasattr(pref.preferences, _k) and getattr(pref.preferences, _k):
                    session_mgr.set_setting(_k, getattr(pref.preferences, _k))
                    setattr(pref.preferences, _k, "")
            for _k in ("active_provider", "openrouter_model", "nvidia_nim_model", "local_base_url",
                       "local_model", "custom_base_url", "custom_model", "reasoning_effort", "thinking_budget"):
                session_mgr.set_setting(_k, getattr(pref.preferences, _k))
            session_mgr.set_setting("user_rules", pref.preferences.user_rules)
            session_mgr.set_setting("cli_remote_url", pref.preferences.cli_remote_url)
            session_mgr.set_setting("allow_lan", "true" if pref.preferences.allow_lan else "false")
        if scene:
            if hasattr(scene, "mcpchat_queue_delay"):
                session_mgr.set_setting("queue_delay_seconds", int(scene.mcpchat_queue_delay))
            for skey, pname in _SCENE_KEYS.items():
                if hasattr(scene, pname):
                    session_mgr.set_setting(skey, _scene_value(scene, skey))
        if scene and hasattr(scene, "mcpchat_lines") and len(scene.mcpchat_messages) > 0 and len(scene.mcpchat_lines) == 0:
            rebuild_lines(scene, scroll_to_end=True)
        if scene and hasattr(scene, "mcpchat_messages") and len(scene.mcpchat_messages) == 0:
            active_idx = getattr(scene, "mcpchat_active_tab", 0)
            sid = session_mgr.get_tab_session_id(active_idx)
            sync_messages_to_ui(scene, sid)
    except Exception:
        pass
    return None


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # 3 Session Tabs (0, 1, 2)
    bpy.types.Scene.mcpchat_active_tab = IntProperty(default=0, min=0, max=2)

    # Message UIList Collection & Active Index
    bpy.types.Scene.mcpchat_messages = CollectionProperty(type=MCPChatMessageItem)
    bpy.types.Scene.mcpchat_lines = CollectionProperty(type=MCPChatLineItem)
    bpy.types.Scene.mcpchat_active_line = IntProperty(default=0)
    bpy.types.Scene.mcpchat_scroll = IntProperty(default=0, min=0)

    # Image Attachments Collection (Max 3)
    bpy.types.Scene.mcpchat_attached_images = CollectionProperty(type=MCPChatAttachedImage)

    # Inputs & Controls
    bpy.types.Scene.mcpchat_prompt = StringProperty(name="Prompt", default="")
    bpy.types.Scene.mcpchat_mode = EnumProperty(
        name="Mode",
        items=[
            ('CHAT', "Chat", "일반 대화 및 직접 실행", 'COMMUNITY', 0),
            ('PLAN', "Plan", "사전 작업 계획 수립", 'TEXT', 1),
            ('AUTO', "Auto", "계획 수립 후 작업큐 자동 순차 실행", 'AUTO', 2),
        ],
        default='AUTO'
    )
    bpy.types.Scene.mcpchat_backend = EnumProperty(
        name="Backend",
        items=[
            ('CLAUDE', "Claude Code", "Termux / PC Claude Code CLI Agent (기본)", 'CONSOLE', 1),
            ('CODEX', "Codex CLI", "OpenAI Codex CLI Agent", 'CONSOLE', 3),
            ('AGY', "agy CLI", "Antigravity agy CLI Agent", 'SETTINGS', 2),
            ('API', "Direct API", "OpenRouter / NVIDIA NIM / Local Ollama", 'WORLD', 0),
        ],
        default='CLAUDE'
    )

    _effort3 = [('low', "Low", "낮은 추론 강도"), ('medium', "Medium", "보통 추론 강도"), ('high', "High", "높은 추론 강도")]
    _effort5 = _effort3 + [('xhigh', "XHigh", "매우 높은 추론 강도"), ('max', "Max", "최대 추론 강도")]
    for _cli, _default in (("claude", "opus"), ("codex", "DEFAULT"), ("agy", "gemini-3.8-flash-low")):
        setattr(bpy.types.Scene, f"mcpchat_{_cli}_model_sel", EnumProperty(
            name=f"{_cli} 모델", description="해당 엔진이 지원하는 모델 선택 (목록에 없으면 '직접 입력')",
            items=CLI_MODEL_ITEMS[_cli], default=_default,
            update=_sync_scene_setting(f"cli_{_cli}_model")))
    bpy.types.Scene.mcpchat_claude_model = StringProperty(
        name="Claude 모델 ID", description="'직접 입력' 선택 시 사용할 모델 ID", default="",
        update=_sync_scene_setting("cli_claude_model"))
    bpy.types.Scene.mcpchat_claude_effort = EnumProperty(
        name="Claude 추론성능", items=_effort5, default='medium', update=_sync_scene_setting("cli_claude_effort"))
    bpy.types.Scene.mcpchat_agy_model = StringProperty(
        name="agy 모델 ID", description="'직접 입력' 선택 시 사용할 모델 ID", default="",
        update=_sync_scene_setting("cli_agy_model"))
    bpy.types.Scene.mcpchat_agy_effort = EnumProperty(
        name="agy 추론성능", items=_effort3, default='low', update=_sync_scene_setting("cli_agy_effort"))
    bpy.types.Scene.mcpchat_codex_model = StringProperty(
        name="Codex 모델 ID", description="'직접 입력' 선택 시 사용할 모델 ID", default="",
        update=_sync_scene_setting("cli_codex_model"))
    bpy.types.Scene.mcpchat_codex_effort = EnumProperty(
        name="Codex 추론성능", items=_effort3, default='medium', update=_sync_scene_setting("cli_codex_effort"))
    bpy.types.Scene.mcpchat_plan_refine = BoolProperty(
        name="계속 계획", description="다음 전송을 현재 계획의 수정/추가 요청으로 처리", default=False)
    bpy.types.Scene.mcpchat_auto_save_blend = BoolProperty(
        name=".blend 스냅샷", description="작업 성공 시마다 현재 씬을 .blend 사본으로 자동 저장 (현재 파일은 변경되지 않음)",
        default=True, update=_sync_scene_setting("auto_save_blend"))
    bpy.types.Scene.mcpchat_auto_save_image = BoolProperty(
        name="뷰포트 이미지", description="작업 성공 시마다 뷰포트 이미지를 PNG로 자동 저장",
        default=True, update=_sync_scene_setting("auto_save_image"))
    bpy.types.Scene.mcpchat_auto_save_pack = BoolProperty(
        name="리소스 패킹", description=".blend 저장 시 외부 텍스처/사운드/폰트를 파일 안에 포함(패킹)",
        default=True, update=_sync_scene_setting("auto_save_pack"))
    bpy.types.Scene.mcpchat_auto_save_glb = BoolProperty(
        name="GLB 내보내기", description="작업 성공 시마다 씬을 .glb로 함께 저장",
        default=True, update=_sync_scene_setting("auto_save_glb"))
    bpy.types.Scene.mcpchat_output_dir = StringProperty(
        name="저장 위치", subtype='DIR_PATH', default="",
        description="자동 저장 폴더 (비우면 기본 위치). 하위에 blends / glb / renders 폴더가 만들어집니다",
        update=_sync_scene_setting("output_dir"))
    bpy.types.Scene.mcpchat_wrap_cells = IntProperty(
        name="줄 너비", description="한 줄에 들어가는 글자 폭 (한글 2칸·영문 1칸). 말줄임(...)이 보이면 줄이세요",
        default=26, min=12, max=100,
        update=lambda self, ctx: rebuild_lines(self))
    bpy.types.Scene.mcpchat_queue_delay = IntProperty(
        name="Queue Delay (s)",
        description="작업과 작업 사이 대기 시간(초)",
        default=60,
        min=0,
        max=3600,
        update=on_delay_change
    )

    def _sync_hook(sid):
        try:
            sync_messages_to_ui(bpy.context.scene, sid)
        except Exception:
            pass
    bpy.app.driver_namespace["mcpchat_sync"] = _sync_hook
    bpy.app.driver_namespace["mcpchat_redraw"] = _redraw_hook

    bpy.app.timers.register(auto_start_timer, first_interval=1.5)
    bpy.app.timers.register(init_ui_timer, first_interval=0.5)


def unregister():
    global _preview_coll
    if _preview_coll is not None:
        bpy.utils.previews.remove(_preview_coll)
        _preview_coll = None
    server_mgr.stop()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    for prop in [
        'mcpchat_active_tab', 'mcpchat_messages', 'mcpchat_scroll', 'mcpchat_lines', 'mcpchat_active_line',
        'mcpchat_attached_images', 'mcpchat_prompt', 'mcpchat_mode',
        'mcpchat_backend', 'mcpchat_queue_delay',
        'mcpchat_claude_model', 'mcpchat_claude_effort', 'mcpchat_agy_model',
        'mcpchat_agy_effort', 'mcpchat_codex_model', 'mcpchat_codex_effort',
        'mcpchat_auto_save_blend', 'mcpchat_auto_save_image', 'mcpchat_plan_refine',
        'mcpchat_auto_save_pack', 'mcpchat_auto_save_glb', 'mcpchat_output_dir', 'mcpchat_wrap_cells',
        'mcpchat_claude_model_sel', 'mcpchat_codex_model_sel', 'mcpchat_agy_model_sel'
    ]:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)


if __name__ == "__main__":
    register()
