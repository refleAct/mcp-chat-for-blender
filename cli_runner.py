"""
Cross-Platform CLI Runner & Auto-Detector (Windows & Android Termux & Linux)
Intelligently detects OS environment, locates claude and agy binaries,
and automatically configures ~/.claude.json and agy mcp_config.json.
"""

import os
import sys
import json
import shutil
import platform
import subprocess
import threading
from typing import Dict, Any, Optional, Tuple


class CLIRunner:
    def __init__(self):
        self.addon_dir = os.path.dirname(os.path.abspath(__file__))
        self.bridge_path = os.path.join(self.addon_dir, "mcp_bridge.py").replace("\\", "/")
        if platform.system() != "Windows":
            try:
                os.chmod(self.bridge_path, 0o755)
            except Exception:
                pass

    def check_android_storage_permission(self) -> Tuple[bool, str]:
        """Checks if Android shared storage is accessible from Termux."""
        if not (os.path.exists("/data/data/com.termux") or "TERMUX_VERSION" in os.environ):
            return True, "Not running in Termux"

        shared_paths = ["/sdcard", "/storage/emulated/0", os.path.expanduser("~/storage/shared")]
        for p in shared_paths:
            if os.path.exists(p) and os.access(p, os.R_OK):
                return True, f"Storage accessible at {p}"

        return False, "Termux 저장소 권한이 필요합니다. Termux 터미널에서 'termux-setup-storage'를 실행해 주세요."

    def detect_environment(self) -> Dict[str, Any]:
        """
        Detects current operating system, host environment (PC vs Termux),
        CLI binary paths, and Android storage permissions.
        """
        sys_name = platform.system()
        is_windows = (sys_name == "Windows")
        is_termux = os.path.exists("/data/data/com.termux") or "TERMUX_VERSION" in os.environ
        is_proot = False

        if not is_windows:
            try:
                with open("/proc/version", "r", errors="ignore") as f:
                    ver_text = f.read().lower()
                    if "android" in ver_text or "proot" in ver_text:
                        is_proot = True
            except Exception:
                pass

        if is_windows:
            env_name = "Windows PC"
        elif is_termux:
            env_name = "Android (Termux Native)"
        elif is_proot:
            env_name = "Android (Termux PRoot Linux)"
        elif sys_name == "Darwin":
            env_name = "macOS"
        else:
            env_name = f"Linux ({platform.release()})"

        claude_bin = self.find_claude_cli()
        agy_bin = self.find_agy_cli()
        storage_ok, storage_msg = self.check_android_storage_permission()

        return {
            "os_name": env_name,
            "system": sys_name,
            "is_windows": is_windows,
            "is_termux": is_termux or is_proot,
            "claude_bin": claude_bin,
            "agy_bin": agy_bin,
            "claude_detected": claude_bin is not None,
            "agy_detected": agy_bin is not None,
            "python_executable": self.get_python_executable(),
            "android_storage_ok": storage_ok,
            "android_storage_msg": storage_msg
        }

    def get_python_executable(self) -> str:
        """Returns clean path or command for python interpreter."""
        if platform.system() == "Windows":
            # Blender bundled python or system python
            if sys.executable and os.path.exists(sys.executable):
                return sys.executable.replace("\\", "/")
            return "python"
        else:
            if sys.executable and os.path.exists(sys.executable):
                return sys.executable
            return "python3"

    def find_claude_cli(self) -> Optional[str]:
        """Locates 'claude' CLI binary across Windows and Linux/Termux."""
        # 1. Search PATH with extensions
        for ext in (["", ".exe", ".cmd", ".bat"] if platform.system() == "Windows" else [""]):
            found = shutil.which("claude" + ext)
            if found:
                return found.replace("\\", "/")

        home = os.path.expanduser("~")
        candidates = []

        if platform.system() == "Windows":
            # Windows Candidates
            appdata = os.environ.get("APPDATA", "")
            localappdata = os.environ.get("LOCALAPPDATA", "")
            userprofile = os.environ.get("USERPROFILE", home)

            candidates.extend([
                os.path.join(userprofile, ".local", "bin", "claude.exe"),
                os.path.join(userprofile, ".local", "bin", "claude.cmd"),
                os.path.join(appdata, "npm", "claude.cmd"),
                os.path.join(localappdata, "npm", "claude.cmd"),
                os.path.join(localappdata, "Programs", "claude", "claude.exe"),
            ])
        else:
            # Termux & Linux Candidates
            candidates.extend([
                "/data/data/com.termux/files/usr/bin/claude",
                os.path.join(home, ".local", "bin", "claude"),
                os.path.join(home, ".npm-global", "bin", "claude"),
                os.path.join(home, ".nvm", "versions", "node", "default", "bin", "claude"),
                "/usr/local/bin/claude",
                "/usr/bin/claude"
            ])

        for c in candidates:
            if c and os.path.exists(c):
                return c.replace("\\", "/")

        return None

    def find_agy_cli(self) -> Optional[str]:
        """Locates 'agy' CLI binary across Windows and Linux/Termux."""
        for ext in (["", ".exe", ".cmd", ".bat"] if platform.system() == "Windows" else [""]):
            found = shutil.which("agy" + ext)
            if found:
                return found.replace("\\", "/")

        home = os.path.expanduser("~")
        candidates = []

        if platform.system() == "Windows":
            localappdata = os.environ.get("LOCALAPPDATA", "")
            userprofile = os.environ.get("USERPROFILE", home)
            candidates.extend([
                os.path.join(localappdata, "agy", "bin", "agy.exe"),
                os.path.join(localappdata, "Programs", "agy", "bin", "agy.exe"),
                os.path.join(userprofile, ".local", "bin", "agy.exe"),
                os.path.join(userprofile, ".local", "bin", "agy.cmd"),
            ])
        else:
            candidates.extend([
                "/data/data/com.termux/files/usr/bin/agy",
                os.path.join(home, ".local", "bin", "agy"),
                "/usr/local/bin/agy",
                "/usr/bin/agy"
            ])

        for c in candidates:
            if c and os.path.exists(c):
                return c.replace("\\", "/")

        return None

    def configure_claude_code_mcp(self) -> Tuple[bool, str]:
        """
        Auto-configures ~/.claude.json so Claude Code knows about the Blender MCP server.
        Works seamlessly on Windows, Linux, and Termux.
        """
        home = os.path.expanduser("~")
        claude_config_path = os.path.join(home, ".claude.json")

        config = {}
        if os.path.exists(claude_config_path):
            try:
                with open(claude_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                config = {}

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        python_cmd = self.get_python_executable()

        # Write clean forward-slash arguments to avoid escape issues on Windows
        config["mcpServers"]["blender"] = {
            "command": python_cmd,
            "args": [self.bridge_path]
        }

        try:
            with open(claude_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True, f"Blender MCP configured in {claude_config_path}"
        except Exception as e:
            return False, f"Failed to write ~/.claude.json: {str(e)}"

    def configure_agy_cli_mcp(self) -> Tuple[bool, str]:
        """
        Auto-configures agy MCP configuration in ~/.gemini/config/mcp_config.json.
        Works seamlessly on Windows, Linux, and Termux.
        """
        home = os.path.expanduser("~")
        agy_dir = os.path.join(home, ".gemini", "config")
        os.makedirs(agy_dir, exist_ok=True)
        agy_config_path = os.path.join(agy_dir, "mcp_config.json")

        config = {}
        if os.path.exists(agy_config_path):
            try:
                with open(agy_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                config = {}

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        python_cmd = self.get_python_executable()

        # agy supports command/args stdio or serverUrl
        config["mcpServers"]["blender"] = {
            "command": python_cmd,
            "args": [self.bridge_path],
            "serverUrl": "http://127.0.0.1:8000/mcp"
        }

        try:
            with open(agy_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True, f"Blender MCP configured in {agy_config_path}"
        except Exception as e:
            return False, f"Failed to write agy mcp_config.json: {str(e)}"

    def run_cli_command_async(self, cli_type: str, prompt: str, mode: str = "CHAT", on_complete=None):
        """
        Executes claude or agy with the given prompt in a background thread,
        handling Windows cmd extensions, bypass permissions, and Plan/Auto modes.
        """
        def _target():
            bin_path = self.find_claude_cli() if cli_type == "claude" else self.find_agy_cli()
            cmd_name = "claude" if cli_type == "claude" else "agy"

            if not bin_path:
                if on_complete:
                    on_complete(False, f"{cmd_name} CLI binary not found in system or Termux.")
                return

            try:
                is_win = (platform.system() == "Windows")
                use_shell = is_win and bin_path.lower().endswith((".cmd", ".bat"))

                if cli_type == "claude":
                    # Place bypass permissions flags BEFORE -p prompt
                    # --permission-mode bypassPermissions and --dangerously-skip-permissions
                    # ensure Claude Code never blocks waiting for permissions on Termux / Android or Windows
                    bypass_flags = [
                        "--permission-mode", "bypassPermissions",
                        "--dangerously-skip-permissions"
                    ]

                    if mode == "AUTO":
                        full_prompt = (
                            "AUTONOMOUS EXECUTION MODE: You MUST directly use the Blender MCP tools "
                            "(execute_blender_code, get_scene_info, capture_viewport) to execute code in Blender now. "
                            "Do NOT stop in Plan mode or ask for confirmation. Execute the Python code in Blender to complete this task.\n\nTask: "
                            + prompt
                        )
                        cmd = [bin_path] + bypass_flags + ["-p", full_prompt]
                    elif mode == "PLAN":
                        full_prompt = (
                            "PLAN MODE: Provide a structured step-by-step 3D modeling plan for Blender for: "
                            + prompt
                            + "\nDo NOT execute tools yet. Explain each step with the Python bpy code to be run."
                        )
                        cmd = [bin_path, "--permission-mode", "plan", "-p", full_prompt]
                    else: # CHAT
                        cmd = [bin_path] + bypass_flags + ["-p", prompt]

                else: # agy
                    bypass_flags = ["--dangerously-skip-permissions"]
                    if mode == "AUTO":
                        cmd = [bin_path] + bypass_flags + ["--mode", "auto", "-p", prompt]
                    elif mode == "PLAN":
                        cmd = [bin_path, "--mode", "plan", "-p", prompt]
                    else: # CHAT
                        cmd = [bin_path] + bypass_flags + ["-p", prompt]

                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=use_shell,
                    encoding="utf-8",
                    errors="replace"
                )
                stdout, stderr = proc.communicate(timeout=180)
                output = stdout or stderr or f"Executed {cmd_name}."
                if on_complete:
                    on_complete(proc.returncode == 0, output)
            except Exception as e:
                if on_complete:
                    on_complete(False, f"Execution failed: {str(e)}")

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()


# Global CLI runner singleton
cli_runner = CLIRunner()
