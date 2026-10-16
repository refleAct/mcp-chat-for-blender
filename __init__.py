bl_info = {
    "name": "MCP Chat for Blender (Android & Termux)",
    "author": "Antigravity & Blender Community",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > MCP Chat",
    "description": "AI Chat Assistant with MCP, Multi-session, Vision, Termux Claude Code / agy CLI & Mobile Web UI",
    "category": "3D View",
}

import os
import sys
import webbrowser
import bpy
from bpy.props import IntProperty, BoolProperty, StringProperty
from bpy.types import Panel, Operator, AddonPreferences

# Ensure current addon directory is in sys.path
addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.append(addon_dir)

from server import server_mgr
from session_manager import session_mgr
from blender_bridge import bridge


class MCPChatPreferences(AddonPreferences):
    bl_idname = __name__

    default_port: IntProperty(
        name="Server Port",
        description="Port for the embedded Web & MCP HTTP Server",
        default=8000,
        min=1024,
        max=65535
    )

    autostart: BoolProperty(
        name="Auto-start Server",
        description="Automatically start the MCP Chat server when Blender launches",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "default_port")
        layout.prop(self, "autostart")
        layout.label(text="Local Web UI: http://127.0.0.1:<port>", icon='URL')
        layout.label(text="Termux MCP Endpoint: http://127.0.0.1:<port>/mcp", icon='CONSOLE')


class MCPCHAT_OT_start_server(Operator):
    """Start the Blender MCP & Web Chat Server"""
    bl_idname = "mcpchat.start_server"
    bl_label = "Start MCP Chat Server"
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
    bl_label = "Stop MCP Chat Server"
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
    bl_icon = 'URL'

    def execute(self, context):
        port = server_mgr.port
        url = f"http://127.0.0.1:{port}"
        try:
            webbrowser.open(url)
            self.report({'INFO'}, f"Opening {url}")
        except Exception as e:
            self.report({'WARNING'}, f"Could not auto-open browser: {e}. Please visit {url} manually.")
        return {'FINISHED'}


class MCPCHAT_PT_main_panel(Panel):
    """Sidebar Panel in 3D Viewport"""
    bl_label = "MCP Chat Assistant"
    bl_idname = "MCPCHAT_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP Chat"

    def draw(self, context):
        layout = self.layout
        is_running = server_mgr.is_running
        port = server_mgr.port

        # Status Box
        box = layout.box()
        row = box.row(align=True)
        if is_running:
            row.label(text=f"Server: Online (Port {port})", icon='RADIOBUT_ON')
            sub = box.row()
            sub.operator("mcpchat.stop_server", text="Stop Server", icon='PAUSE')
            
            box.separator()
            btn_row = box.row()
            btn_row.scale_y = 1.4
            btn_row.operator("mcpchat.open_browser", text="Open Mobile Chat UI", icon='WINDOW')
        else:
            row.label(text="Server: Offline", icon='RADIOBUT_OFF')
            sub = box.row()
            sub.operator("mcpchat.start_server", text="Start Server", icon='PLAY')

        # Termux & MCP Integration Helper
        box_termux = layout.box()
        box_termux.label(text="Termux & MCP Info:", icon='CONSOLE')
        box_termux.label(text=f"Localhost: 127.0.0.1:{port}")
        box_termux.label(text="Claude Code / agy CLI ready")


classes = (
    MCPChatPreferences,
    MCPCHAT_OT_start_server,
    MCPCHAT_OT_stop_server,
    MCPCHAT_OT_open_browser,
    MCPCHAT_PT_main_panel,
)


def auto_start_timer():
    """Starts server after Blender fully loads if enabled in preferences."""
    try:
        addon = bpy.context.preferences.addons.get(__name__)
        if addon and addon.preferences.autostart:
            server_mgr.start(port=addon.preferences.default_port)
    except Exception:
        pass
    return None  # run once


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Register auto-start timer
    bpy.app.timers.register(auto_start_timer, first_interval=1.5)


def unregister():
    server_mgr.stop()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
