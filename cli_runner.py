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
import base64
import tempfile
import uuid
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
        codex_bin = self.find_codex_cli()
        storage_ok, storage_msg = self.check_android_storage_permission()

        return {
            "os_name": env_name,
            "system": sys_name,
            "is_windows": is_windows,
            "is_termux": is_termux or is_proot,
            "claude_bin": claude_bin,
            "agy_bin": agy_bin,
            "codex_bin": codex_bin,
            "codex_detected": codex_bin is not None,
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

    def find_codex_cli(self) -> Optional[str]:
        """Locates 'codex' CLI binary across Windows and Linux/Termux."""
        for ext in (["", ".exe", ".cmd", ".bat"] if platform.system() == "Windows" else [""]):
            found = shutil.which("codex" + ext)
            if found:
                return found.replace("\\", "/")

        home = os.path.expanduser("~")
        candidates = []
        if platform.system() == "Windows":
            appdata = os.environ.get("APPDATA", "")
            localappdata = os.environ.get("LOCALAPPDATA", "")
            candidates.extend([
                os.path.join(appdata, "npm", "codex.cmd"),
                os.path.join(localappdata, "npm", "codex.cmd"),
                os.path.join(home, ".local", "bin", "codex.exe"),
            ])
        else:
            candidates.extend([
                "/data/data/com.termux/files/usr/bin/codex",
                os.path.join(home, ".local", "bin", "codex"),
                os.path.join(home, ".npm-global", "bin", "codex"),
                "/usr/local/bin/codex",
                "/usr/bin/codex",
            ])
        for cand in candidates:
            if cand and os.path.exists(cand):
                return cand.replace("\\", "/")
        return None

    def configure_codex_mcp(self) -> Tuple[bool, str]:
        """Registers the Blender MCP bridge in ~/.codex/config.toml ([mcp_servers.blender])."""
        codex_dir = os.path.join(os.path.expanduser("~"), ".codex")
        cfg_path = os.path.join(codex_dir, "config.toml")
        try:
            os.makedirs(codex_dir, exist_ok=True)
            text = ""
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    text = f.read()
            if "[mcp_servers.blender]" in text:
                return True, f"이미 등록되어 있습니다: {cfg_path}"
            py = self.get_python_executable().replace("\\", "/")
            block = (
                "\n[mcp_servers.blender]\n"
                f'command = "{py}"\n'
                f'args = ["{self.bridge_path}"]\n'
            )
            with open(cfg_path, "a", encoding="utf-8") as f:
                f.write(block)
            return True, f"Blender MCP configured in {cfg_path}"
        except Exception as e:
            return False, f"Failed to write codex config: {e}"

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

    # -------------------------------------------------------------
    # Settings (N-panel / Preferences -> settings DB)
    # -------------------------------------------------------------

    @staticmethod
    def _get_setting(key: str, default: str = "") -> str:
        try:
            import session_manager
            val = session_manager.session_mgr.get_setting(key, default)
            return str(val).strip() if val is not None else default
        except Exception:
            return default

    def collect_opts(self) -> Dict[str, str]:
        """엔진별 모델/추론강도 (N패널에서 설정한 값)."""
        g = self._get_setting
        return {
            "claude_model": g("cli_claude_model", "opus") or "opus",
            "claude_effort": g("cli_claude_effort", "medium") or "medium",
            "agy_model": g("cli_agy_model", "gemini-3.8-flash-low") or "gemini-3.8-flash-low",
            "agy_effort": g("cli_agy_effort", "low") or "low",
            "codex_model": g("cli_codex_model", ""),
            "codex_effort": g("cli_codex_effort", "medium") or "medium",
        }

    @staticmethod
    def _user_block() -> str:
        try:
            import session_manager
            return session_manager.session_mgr.get_user_rules_block()
        except Exception:
            return ""

    def build_guidelines(self) -> str:
        try:
            from guidelines import GUIDELINES
        except ImportError:
            from .guidelines import GUIDELINES
        return GUIDELINES + self._user_block() + "\n"

    def find_cli(self, cli_type: str) -> Optional[str]:
        return {
            "claude": self.find_claude_cli,
            "agy": self.find_agy_cli,
            "codex": self.find_codex_cli,
        }[cli_type]()

    # -------------------------------------------------------------
    # Command construction & local execution (Termux agent도 이 코드를 재사용)
    # -------------------------------------------------------------

    @staticmethod
    def save_images(images) -> list:
        """data URL(base64) 이미지를 임시 파일로 저장하고 경로 목록을 반환 (CLI는 파일 경로로 이미지를 읽는다)."""
        paths = []
        if not images:
            return paths
        out_dir = os.path.join(tempfile.gettempdir(), "mcpchat_images")
        os.makedirs(out_dir, exist_ok=True)
        for url in images:
            try:
                if not url or "," not in url:
                    continue
                head, raw = url.split(",", 1)
                ext = "png"
                if "image/" in head:
                    ext = head.split("image/", 1)[1].split(";", 1)[0].replace("jpeg", "jpg") or "png"
                p = os.path.join(out_dir, f"attach_{uuid.uuid4().hex[:10]}.{ext}")
                with open(p, "wb") as f:
                    f.write(base64.b64decode(raw))
                paths.append(p.replace("\\", "/"))
            except Exception:
                continue
        return paths

    @staticmethod
    def compose_prompt(cli_type: str, mode: str, prompt: str, guidelines: str, image_paths=None) -> str:
        """CLI 엔진에 실제로 전달되는 최종 프롬프트 (미리보기/기록/실행이 같은 함수를 사용)."""
        if image_paths:
            nl0 = chr(10)
            prompt = (prompt + nl0 + nl0 + "[첨부 이미지 - 작업 전에 반드시 열어서 확인하고 참고하세요]" + nl0
                      + nl0.join("- " + p for p in image_paths))
        plan_text = (
            guidelines
            + "PLAN MODE: Provide a structured step-by-step 3D modeling plan for Blender for: "
            + prompt
            + "\nDo NOT execute tools yet. Explain each step with the Python bpy code to be run."
        )
        if cli_type == "claude":
            if mode == "AUTO":
                return (
                    guidelines
                    + "AUTONOMOUS EXECUTION MODE: You MUST directly use the Blender MCP tools "
                    "(execute_blender_code, get_scene_info, capture_viewport) to execute code in Blender now. "
                    "Do NOT stop in Plan mode or ask for confirmation. Execute the Python code in Blender to complete this task.\n\nTask: "
                    + prompt
                )
            if mode == "PLAN":
                return plan_text
            return guidelines + "Task: " + prompt
        if cli_type == "codex":
            if mode == "PLAN":
                return plan_text
            if mode == "AUTO":
                return (
                    guidelines
                    + "AUTONOMOUS EXECUTION MODE: Use the Blender MCP tools "
                    "(execute_blender_code, get_scene_info, capture_viewport) directly, "
                    "without asking for confirmation.\n\nTask: " + prompt
                )
            return guidelines + "Task: " + prompt
        return guidelines + "Task: " + prompt  # agy

    @staticmethod
    def build_command(cli_type: str, bin_path: str, mode: str, prompt: str,
                      opts: Dict[str, str], guidelines: str, image_paths=None):
        """returns (cmd list, stdin_text or None)"""
        full_prompt = CLIRunner.compose_prompt(cli_type, mode, prompt, guidelines, image_paths)
        stdin_text = None

        if cli_type == "claude":
            cmd = [bin_path, "--model", opts.get("claude_model") or "opus",
                   "--effort", opts.get("claude_effort") or "medium"]
            if mode == "PLAN":
                cmd += ["--permission-mode", "plan"]
            else:
                cmd += ["--permission-mode", "bypassPermissions", "--dangerously-skip-permissions"]
            cmd += ["-p", full_prompt]

        elif cli_type == "codex":
            cmd = [bin_path, "exec", "--skip-git-repo-check"]
            if opts.get("codex_model"):
                cmd += ["-m", opts["codex_model"]]
            cmd += ["-c", f'model_reasoning_effort="{opts.get("codex_effort") or "medium"}"']
            cmd += ["--sandbox", "read-only"] if mode == "PLAN" else ["--dangerously-bypass-approvals-and-sandbox"]
            for _p in (image_paths or []):
                cmd += ["-i", _p]
            cmd += ["-"]  # 프롬프트는 stdin으로 전달 (인자 길이/따옴표 문제 방지)
            stdin_text = full_prompt

        else:  # agy
            cmd = [bin_path, "--model", opts.get("agy_model") or "gemini-3.8-flash-low",
                   "--effort", opts.get("agy_effort") or "low", "--dangerously-skip-permissions"]
            if mode == "AUTO":
                cmd += ["--mode", "auto"]
            elif mode == "PLAN":
                cmd += ["--mode", "plan"]
            cmd += ["-p", full_prompt]

        return cmd, stdin_text

    def run_local_sync(self, cli_type: str, prompt: str, mode: str,
                       opts: Dict[str, str], guidelines: str, timeout: int = 300,
                       image_paths=None) -> Tuple[bool, str]:
        bin_path = self.find_cli(cli_type)
        if not bin_path:
            return False, f"{cli_type} CLI binary not found on this device."
        is_win = (platform.system() == "Windows")
        use_shell = is_win and bin_path.lower().endswith((".cmd", ".bat"))
        cmd, stdin_text = self.build_command(cli_type, bin_path, mode, prompt, opts, guidelines, image_paths)
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=use_shell,
            encoding="utf-8",
            errors="replace"
        )
        try:
            stdout, stderr = proc.communicate(input=stdin_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return False, f"{cli_type} 실행 시간 초과 ({timeout}s)"
        return proc.returncode == 0, (stdout or stderr or f"Executed {cli_type}.")

    # -------------------------------------------------------------
    # Remote execution: Blender(Android APK) -> Termux agent (termux_agent.py)
    #   Android 앱 샌드박스 때문에 Blender APK는 Termux의 claude/agy/codex를 직접 실행할 수 없다.
    #   Termux에서 termux_agent.py(127.0.0.1)를 띄우고 HTTP로 실행을 위임한다.
    # -------------------------------------------------------------

    DEFAULT_AGENT_URL = "http://127.0.0.1:8787"

    def agent_settings(self) -> Tuple[str, str, bool]:
        url = self._get_setting("cli_remote_url", "")
        token = self._get_setting("cli_remote_token", "")
        return (url or self.DEFAULT_AGENT_URL), token, bool(url)

    def agent_request(self, path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 330):
        import urllib.request
        import urllib.error
        url, token, _ = self.agent_settings()
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url.rstrip("/") + path, data=data, headers=headers,
                                     method="POST" if payload is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise RuntimeError("Termux Agent 인증 실패: Preferences의 'Agent 토큰'을 확인하세요.")
            raise RuntimeError(f"Termux Agent HTTP {e.code}")

    def agent_health(self) -> Tuple[bool, str]:
        try:
            info = self.agent_request("/health", timeout=4)
            found = [k for k in ("claude", "codex", "agy") if info.get(k)]
            return True, "연결됨 - 감지: " + (", ".join(found) or "CLI 없음")
        except Exception as e:
            return False, f"연결 실패: {e}"

    def run_remote_sync(self, cli_type: str, prompt: str, mode: str,
                        opts: Dict[str, str], guidelines: str, images=None) -> Tuple[bool, str]:
        try:
            res = self.agent_request("/run", {
                "cli": cli_type, "mode": mode, "prompt": prompt,
                "opts": opts, "guidelines": guidelines,
                "images": images or [],   # Termux는 Blender 앱의 파일에 접근할 수 없으므로 데이터로 전달
            })
            return bool(res.get("ok")), str(res.get("output", ""))
        except Exception as e:
            url, _, _ = self.agent_settings()
            return False, (
                f"{cli_type} CLI를 이 기기에서 찾을 수 없고 Termux Agent({url})에도 연결하지 못했습니다.\n"
                f"원인: {e}\n"
                "해결: Termux에서 `bash ~/.config/blender_mcp_chat/start_agent.sh` 를 실행하세요 (처음이면 setup.sh 설치 명령 먼저).\n"
                "Termux를 닫거나 Android가 앱을 정리하면 Agent가 종료됩니다. Termux 알림의 'Acquire wakelock'을 켜 두세요."
            )

    def run_cli_command_async(self, cli_type: str, prompt: str, mode: str = "CHAT", on_complete=None, images=None):
        """
        claude / agy / codex 실행 (백그라운드 스레드).
        - 로컬에 바이너리가 있으면 로컬 실행 (Windows PC 등)
        - 없거나 Agent URL이 명시 설정되어 있으면 Termux Agent로 위임 (Android APK Blender)
        모델/추론강도는 N패널 설정(cli_<type>_model / cli_<type>_effort)을 사용.
        """
        def _target():
            try:
                opts = self.collect_opts()
                guidelines = self.build_guidelines()
                _, _, forced = self.agent_settings()
                local_bin = self.find_cli(cli_type)

                if forced or not local_bin:
                    ok, out = self.run_remote_sync(cli_type, prompt, mode, opts, guidelines, images)
                else:
                    ok, out = self.run_local_sync(cli_type, prompt, mode, opts, guidelines,
                                                  image_paths=self.save_images(images))
                if on_complete:
                    on_complete(ok, out)
            except Exception as e:
                if on_complete:
                    on_complete(False, f"Execution failed: {str(e)}")

        threading.Thread(target=_target, daemon=True).start()


# Global CLI runner singleton
cli_runner = CLIRunner()
