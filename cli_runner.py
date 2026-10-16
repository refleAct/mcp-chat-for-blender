"""
Claude Code CLI & agy CLI Integration Module
Detects CLI availability, auto-configures MCP server in ~/.claude.json / agy configs,
and provides subprocess execution bridges.
"""

import os
import sys
import json
import shutil
import subprocess
import threading
from typing import Dict, Any, Optional, Tuple

class CLIRunner:
    def __init__(self):
        self.addon_dir = os.path.dirname(os.path.abspath(__file__))
        self.bridge_path = os.path.join(self.addon_dir, "mcp_bridge.py")

    def find_claude_cli(self) -> Optional[str]:
        """Locates the 'claude' CLI binary in PATH or Termux paths."""
        found = shutil.which("claude")
        if found:
            return found
        
        # Check Termux / Linux common paths
        termux_paths = [
            "/data/data/com.termux/files/usr/bin/claude",
            os.path.expanduser("~/.npm-global/bin/claude"),
            os.path.expanduser("~/.nvm/versions/node/default/bin/claude"),
            "/usr/local/bin/claude",
            "/usr/bin/claude"
        ]
        for p in termux_paths:
            if os.path.exists(p) and os.access(p, os.X_OK):
                return p
        return None

    def find_agy_cli(self) -> Optional[str]:
        """Locates the 'agy' CLI binary in PATH or Termux paths."""
        found = shutil.which("agy")
        if found:
            return found
        termux_paths = [
            "/data/data/com.termux/files/usr/bin/agy",
            os.path.expanduser("~/.local/bin/agy"),
            "/usr/local/bin/agy",
            "/usr/bin/agy"
        ]
        for p in termux_paths:
            if os.path.exists(p) and os.access(p, os.X_OK):
                return p
        return None

    def configure_claude_code_mcp(self) -> Tuple[bool, str]:
        """
        Auto-configures ~/.claude.json so Claude Code knows about the Blender MCP server.
        """
        home = os.path.expanduser("~")
        claude_config_path = os.path.join(home, ".claude.json")

        config = {}
        if os.path.exists(claude_config_path):
            try:
                with open(claude_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception as e:
                config = {}

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        # Add or update blender MCP configuration
        config["mcpServers"]["blender"] = {
            "command": sys.executable if sys.executable else "python3",
            "args": [self.bridge_path]
        }

        try:
            with open(claude_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True, f"Successfully registered Blender MCP in {claude_config_path}"
        except Exception as e:
            return False, f"Failed to write ~/.claude.json: {str(e)}"

    def configure_agy_cli_mcp(self) -> Tuple[bool, str]:
        """
        Auto-configures agy MCP configuration in ~/.gemini/config/mcp_config.json.
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

        config["mcpServers"]["blender"] = {
            "command": sys.executable if sys.executable else "python3",
            "args": [self.bridge_path]
        }

        try:
            with open(agy_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True, f"Successfully registered Blender MCP in {agy_config_path}"
        except Exception as e:
            return False, f"Failed to write agy mcp_config.json: {str(e)}"

    def run_cli_command_async(self, cli_type: str, prompt: str, on_complete=None):
        """
        Executes claude or agy with the given prompt in a background thread.
        """
        def _target():
            bin_path = self.find_claude_cli() if cli_type == "claude" else self.find_agy_cli()
            cmd_name = "claude" if cli_type == "claude" else "agy"

            if not bin_path:
                if on_complete:
                    on_complete(False, f"{cmd_name} CLI binary not found in PATH or Termux.")
                return

            try:
                # Run CLI with non-interactive prompt flag
                cmd = [bin_path, "-p", prompt]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
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
