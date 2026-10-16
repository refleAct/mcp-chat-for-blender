"""
Packaging script for MCP Chat for Blender.
Creates a compliant Blender addon ZIP archive with enclosing directory structure:
  mcp-chat-for-blender/
    __init__.py
    ...
Excludes .git, __pycache__, .pyc, and scratch files.
"""

import os
import shutil
import zipfile

def package():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    addon_name = "mcp-chat-for-blender"
    
    dist_dir = r"Z:\App"
    dist_addon_dir = os.path.join(dist_dir, addon_name)
    dist_zip_path = os.path.join(dist_dir, f"{addon_name}.zip")
    portable_addon_dir = r"D:\blender-5.2.2-windows-x64\portable\scripts\addons\mcp-chat-for-blender"

    print(f"Packaging {addon_name} from: {base_dir}")

    # Files and folders to package
    include_files = [
        "__init__.py",
        "blender_bridge.py",
        "cli_runner.py",
        "guidelines.py",
        "i18n.py",
        "secrets_store.py",
        "termux_agent.py",
        "llm_client.py",
        "mcp_bridge.py",
        "mcp_handler.py",
        "server.py",
        "session_manager.py",
        "task_queue.py",
        "README.md",
        "install_termux.sh",
    ]
    include_dirs = ["static"]

    # 1. Update Portable Blender directory cleanly
    addons_parent = os.path.dirname(portable_addon_dir)
    if os.path.exists(addons_parent):
        for item in os.listdir(addons_parent):
            if item.startswith(".~stale~"):
                stale_path = os.path.join(addons_parent, item)
                try:
                    if os.path.isdir(stale_path):
                        shutil.rmtree(stale_path, ignore_errors=True)
                    else:
                        os.remove(stale_path)
                except Exception:
                    pass

    os.makedirs(portable_addon_dir, exist_ok=True)
    stray_git = os.path.join(portable_addon_dir, ".git")
    if os.path.exists(stray_git):
        shutil.rmtree(stray_git, ignore_errors=True)

    for fname in include_files:
        src = os.path.join(base_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(portable_addon_dir, fname))

    for dname in include_dirs:
        src = os.path.join(base_dir, dname)
        dst = os.path.join(portable_addon_dir, dname)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".*"))

    # 2. Update Z:\App\mcp-chat-for-blender cleanly (NO .git or __pycache__)
    os.makedirs(dist_dir, exist_ok=True)
    if os.path.exists(dist_addon_dir):
        shutil.rmtree(dist_addon_dir, ignore_errors=True)
    os.makedirs(dist_addon_dir, exist_ok=True)

    for fname in include_files:
        src = os.path.join(base_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dist_addon_dir, fname))

    for dname in include_dirs:
        src = os.path.join(base_dir, dname)
        dst = os.path.join(dist_addon_dir, dname)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".*"))

    # 3. Create ZIP archive with enclosing directory
    # Structure inside zip MUST be:
    # mcp-chat-for-blender/__init__.py
    # mcp-chat-for-blender/static/...
    if os.path.exists(dist_zip_path):
        os.remove(dist_zip_path)

    with zipfile.ZipFile(dist_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in include_files:
            src = os.path.join(base_dir, fname)
            if os.path.exists(src):
                arcname = f"{addon_name}/{fname}"
                zf.write(src, arcname)

        for dname in include_dirs:
            src_d = os.path.join(base_dir, dname)
            if os.path.exists(src_d):
                for root, dirs, files in os.walk(src_d):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
                    for f in files:
                        if f.startswith(".") or f.endswith((".pyc", ".pyo")):
                            continue
                        fpath = os.path.join(root, f)
                        rel = os.path.relpath(fpath, base_dir).replace("\\", "/")
                        arcname = f"{addon_name}/{rel}"
                        zf.write(fpath, arcname)

    print(f"Created ZIP: {dist_zip_path}")
    with zipfile.ZipFile(dist_zip_path, "r") as zf:
        entries = zf.namelist()
        print(f"Verified ZIP contents ({len(entries)} items):")
        for e in entries:
            print(f"  {e}")

if __name__ == "__main__":
    package()
