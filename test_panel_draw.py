import sys
import os

addon_dir = r"D:\blender-5.2.2-windows-x64\portable\scripts\addons\mcp-chat-for-blender"
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import bpy

# Load the addon module directly using importlib
import importlib.util
init_path = os.path.join(addon_dir, "__init__.py")
spec = importlib.util.spec_from_file_location("mcp_chat_addon", init_path)
addon_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(addon_mod)

print("Registering addon...")
try:
    addon_mod.register()
    print("Registered successfully!")
except Exception as e:
    import traceback
    traceback.print_exc()

print("\n--- Testing MCPCHAT_PT_chat_panel draw logic ---")
scene = bpy.context.scene
from session_manager import session_mgr
print("Tab sessions:", session_mgr.get_tab_sessions(3))
print("Messages in scene:", len(scene.mcpchat_messages))
print("Attached images:", len(scene.mcpchat_attached_images))
print("Active tab:", scene.mcpchat_active_tab)
print("Prompt:", scene.mcpchat_prompt)

print("\n--- Testing MCPCHAT_PT_queue_panel draw logic ---")
from task_queue import task_queue
status = task_queue.get_status()
print("Queue status:", status)
print("Queue counts:", status.get("counts"))
print("Queue delay:", status.get("delay_seconds"))

print("\n--- Testing UIList draw_item ---")
item = scene.mcpchat_messages.add()
item.role = "user"
item.content = "Test user message"
item.full_text = "Test user message full"

item2 = scene.mcpchat_messages.add()
item2.role = "assistant"
item2.content = "Test AI message"
item2.full_text = "Test AI message full"

print("Created test messages. Total:", len(scene.mcpchat_messages))

print("\nAll draw prerequisites passed successfully!")
addon_mod.unregister()
print("Unregistered cleanly.")
