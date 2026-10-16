bl_info = {
    "name": "MCP Chat for Blender (Android & Termux & PC)",
    "author": "Antigravity & Blender Community",
    "version": (1, 2, 0),
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
import bpy
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

server_mgr = server.server_mgr
session_mgr = session_manager.session_mgr
bridge = blender_bridge.bridge
task_queue = tq_mod.task_queue
cli_runner = cli_runner.cli_runner
LLMClient = llm_client.LLMClient


# ==============================================================================
# Property Groups for Messages and Image Attachments
# ==============================================================================

class MCPChatMessageItem(PropertyGroup):
    role: StringProperty() # 'user' | 'assistant'
    content: StringProperty() # Single line summary for UIList
    full_text: StringProperty() # Full multi-line content


class MCPChatAttachedImage(PropertyGroup):
    name: StringProperty()
    path: StringProperty()
    is_viewport: BoolProperty(default=False)
    data_b64: StringProperty()


# ==============================================================================
# Preferences
# ==============================================================================

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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "default_port")
        layout.prop(self, "autostart")
        layout.label(text="Local Web Chat: http://127.0.0.1:<port>", icon='URL')
        layout.label(text="Termux / PC MCP Endpoint: http://127.0.0.1:<port>/mcp", icon='CONSOLE')


# ==============================================================================
# UIList: 8-Row Scrollable Chat History (Narrow line spacing, Left/Right Align)
# ==============================================================================

class MCPCHAT_UL_messages(UIList):
    """Scrollable Chat History UIList with 8 visible lines"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.scale_y = 0.82  # Narrower vertical line spacing

            if item.role == 'user':
                # User Chat: Right-aligned, formatted as 'You : content'
                row.alignment = 'RIGHT'
                row.label(text=f"You : {item.content}", icon='USER')
            else:
                # AI Chat: Left-aligned, formatted as 'AI : content'
                row.alignment = 'LEFT'
                row.label(text=f"AI : {item.content}", icon='RESTRICT_RENDER_OFF')


# ==============================================================================
# Session Helpers
# ==============================================================================

def sync_messages_to_ui(scene, session_id):
    """Loads session messages into Blender UIList collection."""
    session = session_mgr.get_session(session_id)
    scene.mcpchat_messages.clear()
    if not session:
        return

    for m in session.get("messages", []):
        item = scene.mcpchat_messages.add()
        item.role = m["role"]
        # Format content for 1-row display
        content_text = m["content"].replace("\n", " ").strip()
        item.content = content_text[:120]
        item.full_text = m["content"]

    # Scroll to bottom
    if len(scene.mcpchat_messages) > 0:
        scene.mcpchat_active_msg_index = len(scene.mcpchat_messages) - 1


# ==============================================================================
# Operators: 3-Session Tabs (Stable Slots & Renaming)
# ==============================================================================

class MCPCHAT_OT_switch_tab(Operator):
    """Switch active session tab (0, 1, or 2)"""
    bl_idname = "mcpchat.switch_tab"
    bl_label = "Switch Tab"

    tab_index: IntProperty(default=0)

    def execute(self, context):
        context.scene.mcpchat_active_tab = self.tab_index
        sid = session_mgr.get_tab_session_id(self.tab_index)
        sync_messages_to_ui(context.scene, sid)
        return {'FINISHED'}


class MCPCHAT_OT_rename_session_tab(Operator):
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
        self.tab_index = context.scene.mcpchat_active_tab
        tabs = session_mgr.get_tab_sessions(3)
        if 0 <= self.tab_index < len(tabs):
            self.new_title = tabs[self.tab_index]["title"]
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"탭 {self.tab_index + 1} 새 이름:", icon='GREASEPENCIL')
        layout.prop(self, "new_title", text="")

    def execute(self, context):
        title = self.new_title.strip()
        if not title:
            self.report({'WARNING'}, "세션 이름을 입력해 주세요.")
            return {'CANCELLED'}
        session_mgr.rename_tab_session(self.tab_index, title)
        self.report({'INFO'}, f"세션 이름이 '{title}'(으)로 변경되었습니다.")
        return {'FINISHED'}


class MCPCHAT_OT_clear_tab_session(Operator):
    """Clear chat history in active tab session"""
    bl_idname = "mcpchat.clear_tab_session"
    bl_label = "Clear Active Tab"
    bl_icon = 'TRASH'

    def execute(self, context):
        tab_idx = context.scene.mcpchat_active_tab
        sid = session_mgr.get_tab_session_id(tab_idx)
        # Delete old session
        session_mgr.delete_session(sid)
        # Recreate fresh session with default slot name
        new_s = session_mgr.create_session(f"세션 {tab_idx + 1}")
        session_mgr.set_tab_session(tab_idx, new_s["id"])
        sync_messages_to_ui(context.scene, new_s["id"])
        self.report({'INFO'}, f"세션 {tab_idx + 1} 대화가 초기화되었습니다.")
class MCPCHAT_OT_reload_addon(Operator):
    """Reload MCP Chat UI and synchronize active session messages"""
    bl_idname = "mcpchat.reload_addon"
    bl_label = "새로고침"
    bl_icon = 'FILE_REFRESH'

    def execute(self, context):
        try:
            import importlib
            for _mod in ["session_manager", "blender_bridge", "task_queue", "cli_runner", "llm_client", "server", "mcp_handler"]:
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


class MCPCHAT_OT_open_prompt_dialog(Operator):
    """멀티라인 프롬프트 작성 창 열기 (한글 띄어쓰기 및 긴 텍스트 입력 최적화)"""
    bl_idname = "mcpchat.open_prompt_dialog"
    bl_label = "멀티라인 프롬프트 작성"
    bl_options = {'REGISTER', 'UNDO'}

    prompt: StringProperty(
        name="프롬프트",
        description="입력할 프롬프트 (한글 띄어쓰기 및 멀티라인 지원)",
        default=""
    )

    def invoke(self, context, event):
        self.prompt = context.scene.mcpchat_prompt
        return context.window_manager.invoke_props_dialog(self, width=480)

    def draw(self, context):
        layout = self.layout
        layout.label(text="프롬프트를 작성하세요 (Enter/OK 누르면 전송):", icon='EDITMODE_HLT')
        if hasattr(layout, "textbox"):
            layout.textbox(self, "prompt", initial_visible_lines=5, placeholder="블렌더에 요청할 상세 작업을 입력하세요...")
        else:
            layout.prop(self, "prompt", text="")

    def execute(self, context):
        context.scene.mcpchat_prompt = self.prompt
        if self.prompt.strip():
            bpy.ops.mcpchat.send_message()
        return {'FINISHED'}


# ==============================================================================
# Operators & Menus: Image Attachments (Max 3 Total, in front of input)
# ==============================================================================

class MCPCHAT_MT_attach_menu(Menu):
    """Attachment Menu in front of input box"""
    bl_label = "Attach"
    bl_idname = "MCPCHAT_MT_attach_menu"

    def draw(self, context):
        layout = self.layout
        count = len(context.scene.mcpchat_attached_images)
        if count >= 3:
            layout.label(text="최대 3개 첨부 완료 (3/3)", icon='INFO')
            return

        layout.operator("mcpchat.select_local_image", text="📁 로컬 이미지 첨부...", icon='FILE_IMAGE')
        layout.operator("mcpchat.attach_viewport_snapshot", text="📸 뷰포트 스냅샷 첨부", icon='RESTRICT_RENDER_OFF')


class MCPCHAT_OT_select_local_image(Operator, ImportHelper):
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
                self.report({'INFO'}, f"첨부됨: {fname} ({len(scene.mcpchat_attached_images)}/3)")
            except PermissionError:
                self.report({'ERROR'}, "안드로이드 저장소 권한 오류: Termux 터미널에서 'termux-setup-storage'를 실행하거나 브라우저 웹 UI(http://127.0.0.1:8000)에서 첨부하세요.")
            except Exception as e:
                self.report({'ERROR'}, f"이미지 읽기 실패: {e}")
        return {'FINISHED'}


class MCPCHAT_OT_attach_viewport_snapshot(Operator):
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
            self.report({'INFO'}, f"뷰포트 스냅샷 첨부됨 ({len(scene.mcpchat_attached_images)}/3)")
        else:
            self.report({'ERROR'}, f"스냅샷 캡처 실패: {res.get('error')}")
        return {'FINISHED'}


class MCPCHAT_OT_remove_attached_image(Operator):
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

class MCPCHAT_OT_send_message(Operator):
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

        # -------------------------------------------------------------
        # 1. CLAUDE CODE CLI / AGY CLI BACKEND
        # -------------------------------------------------------------
        if backend in ('CLAUDE', 'AGY'):
            cli_type = "claude" if backend == 'CLAUDE' else "agy"
            cli_label = "Claude Code" if backend == 'CLAUDE' else "agy CLI"
            
            session_mgr.add_message(session_id, "user", prompt, images=images)
            sync_messages_to_ui(scene, session_id)
            self.report({'INFO'}, f"[{cli_label}] {mode} 모드로 프롬프트 실행 중...")

            def _on_cli_done(success, output):
                # Strip ANSI escape codes if any
                clean_output = re.sub(r'\x1b\[[0-9;]*m', '', output).strip()
                session_mgr.add_message(session_id, "assistant", clean_output)
                # Redraw in main thread
                def _refresh():
                    sync_messages_to_ui(bpy.context.scene, session_id)
                    return None
                bpy.app.timers.register(_refresh, first_interval=0.1)

            cli_runner.run_cli_command_async(cli_type, prompt, mode=mode, on_complete=_on_cli_done)
            return {'FINISHED'}

        # -------------------------------------------------------------
        # 2. DIRECT API BACKEND (OpenRouter / NVIDIA NIM / Ollama)
        # -------------------------------------------------------------
        else:
            settings = session_mgr.get_all_settings()
            provider = settings.get("active_provider", "openrouter")
            client = LLMClient({
                "provider": provider,
                "api_key": settings.get(f"{provider}_api_key", ""),
                "base_url": settings.get(f"{provider}_base_url", ""),
                "model": settings.get(f"{provider}_model", "anthropic/claude-3.5-sonnet"),
                "reasoning_effort": settings.get("reasoning_effort", "medium"),
                "thinking_budget": settings.get("thinking_budget", "2048")
            })

            # PLAN MODE
            if mode == 'PLAN':
                session_mgr.add_message(session_id, "user", f"[PLAN] {prompt}", images=images)
                sync_messages_to_ui(scene, session_id)
                self.report({'INFO'}, "단계별 Plan 계획 수립 중...")

                def _run_plan():
                    try:
                        plan = client.generate_plan(prompt)
                        summary = plan.get("summary", "")
                        steps = plan.get("steps", [])
                        lines = [f"📋 **{plan.get('plan_title', '계획서')}**", summary, ""]
                        for s in steps:
                            lines.append(f"• Step {s.get('step_number')}: {s.get('title')}\n{s.get('description')}\n```python\n{s.get('code')}\n```")
                        session_mgr.add_message(session_id, "assistant", "\n".join(lines))
                    except Exception as e:
                        session_mgr.add_message(session_id, "assistant", f"⚠️ Plan 오류: {e}")
                    
                    def _refresh():
                        sync_messages_to_ui(bpy.context.scene, session_id)
                        return None
                    bpy.app.timers.register(_refresh, first_interval=0.1)

                threading.Thread(target=_run_plan, daemon=True).start()
                return {'FINISHED'}

            # AUTO MODE
            elif mode == 'AUTO':
                session_mgr.add_message(session_id, "user", f"[AUTO] {prompt}", images=images)
                sync_messages_to_ui(scene, session_id)
                self.report({'INFO'}, "오토 모드: 계획 생성 후 작업큐 자동 실행...")

                def _run_auto():
                    try:
                        plan = client.generate_plan(prompt)
                        steps = plan.get("steps", [])
                        batch = []
                        for s in steps:
                            raw_code = s.get("code", "")
                            # Clean code from markdown code fences
                            match = re.search(r"```(?:python)?\s*([\s\S]*?)```", raw_code)
                            clean_code = match.group(1).strip() if match else raw_code.strip()
                            
                            batch.append({
                                "title": s.get("title", f"Step {s.get('step_number')}"),
                                "task_type": s.get("task_type", "code"),
                                "payload": {"code": clean_code}
                            })

                        task_queue.start()
                        enqueued = session_mgr.enqueue_batch_tasks(batch)
                        delay = task_queue.get_status().get('delay_seconds', 2.0)
                        session_mgr.add_message(
                            session_id, 
                            "assistant", 
                            f"⚡ Auto Mode 가동: 총 {len(enqueued)}개 작업이 등록되었습니다. 전역 딜레이({delay}s) 간격으로 자동 실행 및 저장됩니다."
                        )
                    except Exception as e:
                        session_mgr.add_message(session_id, "assistant", f"⚠️ Auto Mode 오류: {e}")

                    def _refresh():
                        sync_messages_to_ui(bpy.context.scene, session_id)
                        return None
                    bpy.app.timers.register(_refresh, first_interval=0.1)

                threading.Thread(target=_run_auto, daemon=True).start()
                return {'FINISHED'}

            # CHAT MODE
            else:
                session_mgr.add_message(session_id, "user", prompt, images=images)
                sync_messages_to_ui(scene, session_id)
                self.report({'INFO'}, "AI 추론 및 실행 중...")

                def _run_chat():
                    current_session = session_mgr.get_session(session_id)
                    try:
                        res = client.run_agent_loop(
                            system_prompt=current_session.get("system_prompt", ""),
                            messages=current_session.get("messages", [])
                        )
                        session_mgr.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=res["content"],
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

                threading.Thread(target=_run_chat, daemon=True).start()
                return {'FINISHED'}


# ==============================================================================
# Operators: Task Queue Controls & Server
# ==============================================================================

class MCPCHAT_OT_toggle_queue(Operator):
    """Pause or Resume Task Queue Worker"""
    bl_idname = "mcpchat.toggle_queue"
    bl_label = "Pause/Resume Queue"
    bl_icon = 'PLAY_PAUSE'

    def execute(self, context):
        if task_queue.is_paused:
            task_queue.resume()
            task_queue.start()
            self.report({'INFO'}, "Task Queue resumed")
        else:
            task_queue.pause()
            self.report({'INFO'}, "Task Queue paused")
        return {'FINISHED'}


class MCPCHAT_OT_clear_queue(Operator):
    """Clear all tasks in the Task Queue"""
    bl_idname = "mcpchat.clear_queue"
    bl_label = "Clear Queue"
    bl_icon = 'CANCEL'

    def execute(self, context):
        session_mgr.clear_queue()
        self.report({'INFO'}, "Task Queue cleared")
        return {'FINISHED'}


class MCPCHAT_OT_setup_claude_cli(Operator):
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


class MCPCHAT_OT_setup_agy_cli(Operator):
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


class MCPCHAT_OT_start_server(Operator):
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


class MCPCHAT_OT_stop_server(Operator):
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


class MCPCHAT_OT_open_browser(Operator):
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
    """Main In-Blender Chat Console with 3 Tabs, 8-line History, Input in front"""
    bl_label = "MCP Chat & AI Console"
    bl_idname = "MCPCHAT_PT_chat_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        try:
            # -------------------------------------------------------------
            # 1. 3 Session Tabs Bar: [ 세션 1: 이름 ] [ 세션 2: 이름 ] [ 세션 3: 이름 ]
            # -------------------------------------------------------------
            mgr = session_manager.session_mgr
            if not hasattr(mgr, "get_tab_sessions"):
                try:
                    import importlib
                    importlib.reload(session_manager)
                    mgr = session_manager.session_mgr
                except Exception:
                    pass

            tab_sessions = mgr.get_tab_sessions(3) if hasattr(mgr, "get_tab_sessions") else [{"title": f"세션 {i+1}"} for i in range(3)]
            raw_idx = getattr(scene, "mcpchat_active_tab", 0)
            active_idx = max(0, min(2, raw_idx))

            row_tabs = layout.row(align=True)
            for i in range(3):
                is_active = (active_idx == i)
                s_title = tab_sessions[i]["title"] if i < len(tab_sessions) else f"세션 {i + 1}"
                disp_title = (s_title[:7] + "..") if len(s_title) > 8 else s_title
                sub = row_tabs.row(align=True)
                op = sub.operator("mcpchat.switch_tab", text=disp_title, depress=is_active)
                op.tab_index = i

            # Mode and Engine Pickers
            col_ctrl = layout.column(align=True)
            if hasattr(scene, "mcpchat_mode"):
                col_ctrl.prop(scene, "mcpchat_mode", expand=True)
            row_eng = col_ctrl.row(align=True)
            if hasattr(scene, "mcpchat_backend"):
                row_eng.prop(scene, "mcpchat_backend", text="Engine")

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
            row_h_head.operator("mcpchat.clear_tab_session", text="", icon='TRASH')

            # Native UIList with 8 visible rows & scrollbar
            if hasattr(scene, "mcpchat_messages") and len(scene.mcpchat_messages) > 0:
                box_history.template_list(
                    "MCPCHAT_UL_messages", "", scene, "mcpchat_messages", scene, "mcpchat_active_msg_index",
                    rows=8, maxrows=8
                )
            else:
                box_history.label(text="대화 기록이 없습니다. 프롬프트를 입력하세요.", icon='INFO')

            # Multi-line Selected Message Detail Box (Preserves newlines!)
            if 0 <= scene.mcpchat_active_msg_index < len(scene.mcpchat_messages):
                active_item = scene.mcpchat_messages[scene.mcpchat_active_msg_index]
                if "\n" in active_item.full_text or len(active_item.full_text) > 80:
                    box_detail = layout.box()
                    icon = 'USER' if active_item.role == 'user' else 'RESTRICT_RENDER_OFF'
                    name = "You" if active_item.role == 'user' else "AI"
                    box_detail.label(text=f"[{name} 상세 내용]", icon=icon)
                    col_text = box_detail.column(align=True)
                    col_text.scale_y = 0.82
                    for line in active_item.full_text.splitlines():
                        if line.strip():
                            col_text.label(text=line)

            layout.separator(factor=0.5)

            # -------------------------------------------------------------
            # 3. Attached Images Strip (Max 3 Total)
            # -------------------------------------------------------------
            attached_count = len(scene.mcpchat_attached_images)
            if attached_count > 0:
                box_imgs = layout.box()
                row_chips = box_imgs.row(align=True)
                for idx, img in enumerate(scene.mcpchat_attached_images):
                    sub = row_chips.row(align=True)
                    icon = 'RESTRICT_RENDER_OFF' if img.is_viewport else 'FILE_IMAGE'
                    sub.label(text=img.name[:12], icon=icon)
                    del_op = sub.operator("mcpchat.remove_attached_image", text="", icon='X')
                    del_op.index = idx
                row_chips.label(text=f"({attached_count}/3)")

            # -------------------------------------------------------------
            # 4. Input Row: [ ➕ 첨부 ] [ 프롬프트 입력창 ] [ 📝 ] [ 전송 ]
            # -------------------------------------------------------------
            row_input = layout.row(align=True)
            # Attachment Menu in front of input field
            row_input.menu("MCPCHAT_MT_attach_menu", text="", icon='ADD')
            if hasattr(row_input, "textbox"):
                row_input.textbox(scene, "mcpchat_prompt", initial_visible_lines=2, placeholder="프롬프트 입력 (Shift+Enter 줄바꿈)...")
            else:
                row_input.prop(scene, "mcpchat_prompt", text="")
            row_input.operator("mcpchat.open_prompt_dialog", text="", icon='TEXT')

            # Send Button
            send_icon = 'PLAY'
            if scene.mcpchat_mode == 'PLAN':
                send_icon = 'TEXT'
            elif scene.mcpchat_mode == 'AUTO':
                send_icon = 'AUTO'
            row_input.operator("mcpchat.send_message", text="전송", icon=send_icon)

        except Exception as e:
            layout.label(text=f"채팅 콘솔 로딩 오류: {e}", icon='ERROR')


class MCPCHAT_PT_queue_panel(Panel):
    """Task Queue & Global Delay Panel"""
    bl_label = "Task Queue & Auto-Save"
    bl_idname = "MCPCHAT_PT_queue_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        try:
            status = task_queue.get_status()
            counts = status.get("counts", {})
            is_paused = status.get("is_paused", False)

            box = layout.box()
            state_icon = 'PAUSE' if is_paused else 'PLAY'
            state_str = "PAUSED" if is_paused else "RUNNING"
            box.label(text=f"Queue Worker: {state_str}", icon=state_icon)
            
            row = box.row(align=True)
            row.label(text=f"대기: {counts.get('pending', 0)}")
            row.label(text=f"실행중: {counts.get('running', 0)}")
            row.label(text=f"완료: {counts.get('completed', 0)}")

            if hasattr(scene, "mcpchat_queue_delay"):
                col_delay = layout.column()
                col_delay.prop(scene, "mcpchat_queue_delay", text="전역 딜레이(초)")

            box_save = layout.box()
            box_save.label(text="자동 저장: .blend & Render 활성화", icon='FILE_TICK')

            row_actions = layout.row(align=True)
            row_actions.operator("mcpchat.toggle_queue", text="Resume" if is_paused else "Pause", icon='PLAY_PAUSE')
            row_actions.operator("mcpchat.clear_queue", text="Clear", icon='CANCEL')
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
        layout = self.layout

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
        layout = self.layout
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
    MCPChatAttachedImage,
    MCPChatPreferences,
    MCPCHAT_UL_messages,
    MCPCHAT_MT_attach_menu,
    MCPCHAT_OT_switch_tab,
    MCPCHAT_OT_rename_session_tab,
    MCPCHAT_OT_clear_tab_session,
    MCPCHAT_OT_reload_addon,
    MCPCHAT_OT_open_prompt_dialog,
    MCPCHAT_OT_select_local_image,
    MCPCHAT_OT_attach_viewport_snapshot,
    MCPCHAT_OT_remove_attached_image,
    MCPCHAT_OT_send_message,
    MCPCHAT_OT_toggle_queue,
    MCPCHAT_OT_clear_queue,
    MCPCHAT_OT_setup_claude_cli,
    MCPCHAT_OT_setup_agy_cli,
    MCPCHAT_OT_start_server,
    MCPCHAT_OT_stop_server,
    MCPCHAT_OT_open_browser,
    MCPCHAT_PT_chat_panel,
    MCPCHAT_PT_queue_panel,
    MCPCHAT_PT_cli_panel,
    MCPCHAT_PT_server_panel,
)


def on_delay_change(self, context):
    try:
        val = str(round(self.mcpchat_queue_delay, 1))
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
    bpy.types.Scene.mcpchat_active_msg_index = IntProperty(default=0)

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
        default='CHAT'
    )
    bpy.types.Scene.mcpchat_backend = EnumProperty(
        name="Backend",
        items=[
            ('API', "Direct API", "OpenRouter / NVIDIA NIM / Local Ollama", 'WORLD', 0),
            ('CLAUDE', "Claude Code", "Termux / PC Claude Code CLI Agent", 'CONSOLE', 1),
            ('AGY', "agy CLI", "Antigravity agy CLI Agent", 'SETTINGS', 2),
        ],
        default='API'
    )
    bpy.types.Scene.mcpchat_queue_delay = FloatProperty(
        name="Queue Delay (s)",
        default=2.0,
        min=0.1,
        max=30.0,
        step=50,
        precision=1,
        update=on_delay_change
    )

    bpy.app.timers.register(auto_start_timer, first_interval=1.5)
    bpy.app.timers.register(init_ui_timer, first_interval=0.5)


def unregister():
    server_mgr.stop()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    for prop in [
        'mcpchat_active_tab', 'mcpchat_messages', 'mcpchat_active_msg_index',
        'mcpchat_attached_images', 'mcpchat_prompt', 'mcpchat_mode',
        'mcpchat_backend', 'mcpchat_queue_delay'
    ]:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)


if __name__ == "__main__":
    register()
