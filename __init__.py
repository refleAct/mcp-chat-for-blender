bl_info = {
    "name": "MCP Chat for Blender (Android & Termux)",
    "author": "Antigravity & Blender Community",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > MCP Chat",
    "description": "Embedded In-Blender Chat, Plan & Auto Mode, Task Queue with Global Delay, Claude Code & agy CLI Integration",
    "category": "3D View",
}

import os
import sys
import webbrowser
import threading
import mimetypes
import base64
import bpy
from bpy.props import IntProperty, BoolProperty, StringProperty, EnumProperty, FloatProperty
from bpy.types import Panel, Operator, AddonPreferences
from bpy_extras.io_utils import ImportHelper

# Ensure current addon directory is in sys.path
addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.append(addon_dir)

from server import server_mgr
from session_manager import session_mgr
from blender_bridge import bridge
from task_queue import task_queue
from cli_runner import cli_runner
from llm_client import LLMClient


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
        layout.label(text="Termux MCP Endpoint: http://127.0.0.1:<port>/mcp", icon='CONSOLE')


# ==============================================================================
# Operators: Server & Web UI
# ==============================================================================

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
    """Open the Web Chat UI in your browser or Android webview"""
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
# Operators: In-Blender Native Chat & Execution
# ==============================================================================

class MCPCHAT_OT_send_message(Operator):
    """Send prompt using current mode (Chat, Plan, or Auto) and backend"""
    bl_idname = "mcpchat.send_message"
    bl_label = "Send"
    bl_icon = 'PLAY'

    def execute(self, context):
        scene = context.scene
        prompt = scene.mcpchat_prompt.strip()
        if not prompt:
            self.report({'WARNING'}, "Please enter a prompt")
            return {'CANCELLED'}

        mode = scene.mcpchat_mode
        backend = scene.mcpchat_backend
        include_viewport = scene.mcpchat_include_viewport
        image_path = scene.mcpchat_image_path.strip()

        # Handle Viewport Snapshot
        images = []
        if include_viewport:
            res = bridge.capture_viewport()
            if "image_base64" in res:
                images.append(res["image_base64"])

        if image_path and os.path.exists(image_path):
            mime, _ = mimetypes.guess_type(image_path)
            if not mime:
                mime = "image/png"
            try:
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                images.append(f"data:{mime};base64,{b64}")
                # Clear after attaching to message so subsequent messages don't re-send unless selected
                scene.mcpchat_image_path = ""
            except Exception as e:
                self.report({'WARNING'}, f"Failed to attach image: {e}")

        # Clear input field
        scene.mcpchat_prompt = ""

        # Get or create active session
        sessions = session_mgr.list_sessions()
        session_id = sessions[0]["id"] if sessions else session_mgr.create_session("Blender Chat")["id"]

        # 1. CLAUDE CODE CLI Backend
        if backend == 'CLAUDE':
            session_mgr.add_message(session_id, "user", f"[Claude CLI] {prompt}", images=images)
            self.report({'INFO'}, "Sending prompt to Claude Code CLI...")

            def _on_claude_done(success, output):
                session_mgr.add_message(session_id, "assistant", output)

            cli_runner.run_cli_command_async("claude", prompt, on_complete=_on_claude_done)
            return {'FINISHED'}

        # 2. AGY CLI Backend
        elif backend == 'AGY':
            session_mgr.add_message(session_id, "user", f"[agy CLI] {prompt}", images=images)
            self.report({'INFO'}, "Sending prompt to agy CLI...")

            def _on_agy_done(success, output):
                session_mgr.add_message(session_id, "assistant", output)

            cli_runner.run_cli_command_async("agy", prompt, on_complete=_on_agy_done)
            return {'FINISHED'}

        # 3. DIRECT API Backend (Chat, Plan, or Auto Mode)
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
                session_mgr.add_message(session_id, "user", f"[PLAN MODE] {prompt}", images=images)
                self.report({'INFO'}, "Generating step-by-step Plan...")

                def _run_plan():
                    try:
                        plan = client.generate_plan(prompt)
                        summary = plan.get("summary", "")
                        steps = plan.get("steps", [])
                        text_parts = [f"📋 **{plan.get('plan_title', 'Execution Plan')}**\n{summary}\n"]
                        for s in steps:
                            text_parts.append(f"**Step {s.get('step_number')}: {s.get('title')}**\n{s.get('description')}\n```python\n{s.get('code')}\n```")
                        session_mgr.add_message(session_id, "assistant", "\n\n".join(text_parts))
                    except Exception as e:
                        session_mgr.add_message(session_id, "assistant", f"⚠️ Plan generation failed: {e}")

                threading.Thread(target=_run_plan, daemon=True).start()
                return {'FINISHED'}

            # AUTO MODE
            elif mode == 'AUTO':
                session_mgr.add_message(session_id, "user", f"[AUTO MODE] {prompt}", images=images)
                self.report({'INFO'}, "Generating plan and auto-enqueueing tasks...")

                def _run_auto():
                    try:
                        plan = client.generate_plan(prompt)
                        steps = plan.get("steps", [])
                        batch = []
                        for s in steps:
                            batch.append({
                                "title": s.get("title", f"Step {s.get('step_number')}"),
                                "task_type": s.get("task_type", "code"),
                                "payload": {"code": s.get("code", "")}
                            })
                        task_queue.start()
                        enqueued = session_mgr.enqueue_batch_tasks(batch)
                        session_mgr.add_message(
                            session_id, 
                            "assistant", 
                            f"⚡ **Auto Mode Started**\n{len(enqueued)}개 작업이 대기열에 등록되었습니다. 전역 딜레이({task_queue.get_status()['delay_seconds']}s)와 함께 순차 실행 및 자동 저장이 진행됩니다."
                        )
                    except Exception as e:
                        session_mgr.add_message(session_id, "assistant", f"⚠️ Auto Mode failed: {e}")

                threading.Thread(target=_run_auto, daemon=True).start()
                return {'FINISHED'}

            # STANDARD CHAT MODE
            else:
                session_mgr.add_message(session_id, "user", prompt, images=images)
                self.report({'INFO'}, "AI thinking and executing...")

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
                        session_mgr.add_message(session_id, "assistant", f"⚠️ Error: {e}")

                threading.Thread(target=_run_chat, daemon=True).start()
                return {'FINISHED'}


class MCPCHAT_OT_new_session(Operator):
    """Create a new chat session"""
    bl_idname = "mcpchat.new_session"
    bl_label = "New Chat"
    bl_icon = 'ADD'

    def execute(self, context):
        new_s = session_mgr.create_session("New Blender Chat")
        self.report({'INFO'}, f"Created session: {new_s['title']}")
        return {'FINISHED'}


class MCPCHAT_OT_clear_history(Operator):
    """Clear chat history in active session"""
    bl_idname = "mcpchat.clear_history"
    bl_label = "Clear History"
    bl_icon = 'TRASH'

    def execute(self, context):
        sessions = session_mgr.list_sessions()
        if sessions:
            session_mgr.delete_session(sessions[0]["id"])
            session_mgr.create_session("New Chat")
            self.report({'INFO'}, "Chat history cleared")
        return {'FINISHED'}


# ==============================================================================
# Operators: Local Image Selection
# ==============================================================================

class MCPCHAT_OT_select_local_image(Operator, ImportHelper):
    """Select a local image to attach to the chat prompt"""
    bl_idname = "mcpchat.select_local_image"
    bl_label = "Select Local Image"
    bl_icon = 'FILE_IMAGE'

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif",
        options={'HIDDEN'}
    )

    def execute(self, context):
        if self.filepath and os.path.exists(self.filepath):
            context.scene.mcpchat_image_path = self.filepath
            self.report({'INFO'}, f"Attached: {os.path.basename(self.filepath)}")
        return {'FINISHED'}


class MCPCHAT_OT_clear_image(Operator):
    """Remove attached local image"""
    bl_idname = "mcpchat.clear_image"
    bl_label = "Clear Image"
    bl_icon = 'CANCEL'

    def execute(self, context):
        context.scene.mcpchat_image_path = ""
        return {'FINISHED'}


# ==============================================================================
# Operators: Task Queue Controls
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


# ==============================================================================
# Operators: Claude Code & agy CLI Setup
# ==============================================================================

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


# ==============================================================================
# Panels in 3D Viewport N-Panel
# ==============================================================================

class MCPCHAT_PT_chat_panel(Panel):
    """In-Blender Native Chat Assistant Panel"""
    bl_label = "MCP Chat & AI Modes"
    bl_idname = "MCPCHAT_PT_chat_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 1. Mode & Backend Selectors
        col_mode = layout.column(align=True)
        col_mode.prop(scene, "mcpchat_mode", expand=True)

        row_backend = layout.row(align=True)
        row_backend.prop(scene, "mcpchat_backend", text="Engine")

        layout.separator()

        # 2. Session Header & Actions
        sessions = session_mgr.list_sessions()
        active_session = sessions[0] if sessions else None
        
        box_session = layout.box()
        row_sess = box_session.row(align=True)
        title_text = active_session["title"] if active_session else "No Active Session"
        row_sess.label(text=title_text, icon='COMMUNITY')
        row_sess.operator("mcpchat.new_session", text="", icon='ADD')
        row_sess.operator("mcpchat.clear_history", text="", icon='TRASH')

        # 3. Recent Message History Box
        if active_session:
            sess_details = session_mgr.get_session(active_session["id"])
            msgs = sess_details.get("messages", [])[-6:] if sess_details else []
            
            box_msgs = layout.box()
            if msgs:
                for m in msgs:
                    role_icon = 'USER' if m['role'] == 'user' else 'RESTRICT_RENDER_OFF'
                    role_name = "You" if m['role'] == 'user' else "AI"
                    row = box_msgs.row()
                    row.label(text=f"[{role_name}]", icon=role_icon)
                    # Short preview text
                    text = m['content'].replace("\n", " ")[:60]
                    box_msgs.label(text=text)
            else:
                box_msgs.label(text="대화를 시작해보세요.", icon='INFO')

        layout.separator()

        # 4. Input & Execution Area
        col_input = layout.column(align=True)
        col_input.prop(scene, "mcpchat_prompt", text="")
        
        # Local Image & Viewport Attachment Box
        box_attach = layout.box()
        if scene.mcpchat_image_path and os.path.exists(scene.mcpchat_image_path):
            row_file = box_attach.row(align=True)
            fname = os.path.basename(scene.mcpchat_image_path)
            row_file.label(text=f"첨부: {fname[:24]}", icon='IMAGE_DATA')
            row_file.operator("mcpchat.clear_image", text="", icon='X')
        else:
            row_file = box_attach.row(align=True)
            row_file.operator("mcpchat.select_local_image", text="로컬 이미지 첨부...", icon='FILE_IMAGE')

        row_vp = box_attach.row(align=True)
        row_vp.prop(scene, "mcpchat_include_viewport", text="뷰포트 스냅샷도 첨부", icon='RESTRICT_RENDER_OFF')

        # Send Button
        btn_label = "보내기 (Chat)"
        if scene.mcpchat_mode == 'PLAN':
            btn_label = "계획 수립 (Plan)"
        elif scene.mcpchat_mode == 'AUTO':
            btn_label = "오토 모드 실행 (Auto)"

        row_send = layout.row()
        row_send.scale_y = 1.3
        row_send.operator("mcpchat.send_message", text=btn_label, icon='PLAY')


class MCPCHAT_PT_queue_panel(Panel):
    """Task Queue & Global Delay Panel"""
    bl_label = "Task Queue & Auto-Save"
    bl_idname = "MCPCHAT_PT_queue_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        status = task_queue.get_status()
        counts = status.get("counts", {})
        is_paused = status.get("is_paused", False)

        # Queue Status Display
        box = layout.box()
        state_icon = 'PAUSE' if is_paused else 'PLAY'
        state_str = "PAUSED" if is_paused else "RUNNING"
        box.label(text=f"Queue Worker: {state_str}", icon=state_icon)
        
        row = box.row(align=True)
        row.label(text=f"대기: {counts.get('pending', 0)}")
        row.label(text=f"실행중: {counts.get('running', 0)}")
        row.label(text=f"완료: {counts.get('completed', 0)}")

        # Global Delay Setting
        col_delay = layout.column()
        col_delay.prop(scene, "mcpchat_queue_delay", text="전역 딜레이(초)")

        # Auto-save Indicators
        box_save = layout.box()
        box_save.label(text="자동 저장: .blend & Render 활성화", icon='FILE_TICK')

        # Queue Action Buttons
        row_actions = layout.row(align=True)
        row_actions.operator("mcpchat.toggle_queue", text="Resume" if is_paused else "Pause", icon='PLAY_PAUSE')
        row_actions.operator("mcpchat.clear_queue", text="Clear", icon='CANCEL')


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

        # Environment Auto-Detection Box
        box_env = layout.box()
        env_icon = 'DESKTOP' if env["is_windows"] else ('COMMUNITY' if env["is_termux"] else 'HELP')
        box_env.label(text=f"환경 감지: {os_name}", icon=env_icon)

        # CLI Detection Status Box
        box = layout.box()
        if claude_path:
            short_name = os.path.basename(claude_path)
            box.label(text=f"Claude Code: 감지됨 ({short_name})", icon='CHECKMARK')
        else:
            box.label(text="Claude Code: 미감지 (npm i -g @anthropic-ai/claude-code)", icon='X')

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
    MCPChatPreferences,
    MCPCHAT_OT_start_server,
    MCPCHAT_OT_stop_server,
    MCPCHAT_OT_open_browser,
    MCPCHAT_OT_send_message,
    MCPCHAT_OT_new_session,
    MCPCHAT_OT_clear_history,
    MCPCHAT_OT_select_local_image,
    MCPCHAT_OT_clear_image,
    MCPCHAT_OT_toggle_queue,
    MCPCHAT_OT_clear_queue,
    MCPCHAT_OT_setup_claude_cli,
    MCPCHAT_OT_setup_agy_cli,
    MCPCHAT_PT_chat_panel,
    MCPCHAT_PT_queue_panel,
    MCPCHAT_PT_cli_panel,
    MCPCHAT_PT_server_panel,
)


def on_delay_change(self, context):
    """Sync delay changes from Blender slider into session settings."""
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


def register():
    # Register scene properties
    bpy.types.Scene.mcpchat_prompt = StringProperty(
        name="Prompt",
        description="Prompt for Blender AI",
        default=""
    )

    bpy.types.Scene.mcpchat_mode = EnumProperty(
        name="Mode",
        description="Operating Mode",
        items=[
            ('CHAT', "Chat", "일반 대화 및 직접 실행", 'COMMUNITY', 0),
            ('PLAN', "Plan", "사전 작업 계획 수립", 'TEXT', 1),
            ('AUTO', "Auto", "계획 수립 후 작업큐 자동 순차 실행", 'AUTO', 2),
        ],
        default='CHAT'
    )

    bpy.types.Scene.mcpchat_backend = EnumProperty(
        name="Backend",
        description="AI Inference Engine",
        items=[
            ('API', "Direct API", "OpenRouter / NVIDIA NIM / Local Ollama", 'WORLD', 0),
            ('CLAUDE', "Claude Code", "Termux Claude Code CLI Agent", 'CONSOLE', 1),
            ('AGY', "agy CLI", "Antigravity agy CLI Agent", 'SETTINGS', 2),
        ],
        default='API'
    )

    bpy.types.Scene.mcpchat_include_viewport = BoolProperty(
        name="Include Viewport",
        description="Capture 3D Viewport snapshot and send with prompt",
        default=False
    )

    bpy.types.Scene.mcpchat_image_path = StringProperty(
        name="Image Path",
        description="Local image path to attach",
        subtype='FILE_PATH'
    )

    bpy.types.Scene.mcpchat_queue_delay = FloatProperty(
        name="Queue Delay (s)",
        description="Global delay in seconds between queued task executions",
        default=2.0,
        min=0.1,
        max=30.0,
        step=50,
        precision=1,
        update=on_delay_change
    )

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.app.timers.register(auto_start_timer, first_interval=1.5)


def unregister():
    server_mgr.stop()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.mcpchat_prompt
    del bpy.types.Scene.mcpchat_mode
    del bpy.types.Scene.mcpchat_backend
    del bpy.types.Scene.mcpchat_include_viewport
    del bpy.types.Scene.mcpchat_image_path
    del bpy.types.Scene.mcpchat_queue_delay


if __name__ == "__main__":
    register()
