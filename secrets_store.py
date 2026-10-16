"""
Encrypted secret vault (API keys, LAN token, Agent token).

The vault file lives INSIDE the add-on folder (.vault/), so deleting the add-on deletes the secrets too.

Backends (chosen automatically, stored in the file header so it can be read back):
  DPAPI1  Windows DPAPI via ctypes  - real encryption bound to the logged-in Windows user
  OSSL1   `openssl enc -aes-256-cbc -pbkdf2` with a random key file (mode 600) - macOS / Linux / Termux
  OBF1    HMAC-SHA256 stream obfuscation with a random key file - LAST RESORT (e.g. Android APK without openssl).
          This only hides secrets from casual viewing; is_weak() reports it so the UI can warn.

Stdlib only. Thread-safe. Set MCP_VAULT_DIR / MCP_VAULT_BACKEND in the environment to override (tests).
"""

import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import threading

VAULT_DIR = os.environ.get("MCP_VAULT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vault")
VAULT_FILE = os.path.join(VAULT_DIR, "vault.bin")
KEY_FILE = os.path.join(VAULT_DIR, "vault.key")

# 값이 DB/설정/웹 API에 평문으로 저장되면 안 되는 항목
SECRET_KEYS = (
    "openrouter_api_key",
    "nvidia_nim_api_key",
    "custom_api_key",
    "mcp_token",
    "cli_remote_token",
)
MASK = "********"

_lock = threading.RLock()
_cache = None
_backend_used = None


# ----------------------------------------------------------------------------
# key file / backends
# ----------------------------------------------------------------------------

def _ensure_dir():
    os.makedirs(VAULT_DIR, exist_ok=True)
    try:
        os.chmod(VAULT_DIR, 0o700)
    except Exception:
        pass


def _key_bytes() -> bytes:
    _ensure_dir()
    if not os.path.exists(KEY_FILE):
        old = os.umask(0o077)
        try:
            with open(KEY_FILE, "wb") as f:
                f.write(base64.b64encode(os.urandom(48)))
        finally:
            os.umask(old)
        try:
            os.chmod(KEY_FILE, 0o600)
        except Exception:
            pass
    with open(KEY_FILE, "rb") as f:
        return f.read().strip()


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)):
        raise OSError("DPAPI call failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _openssl(data: bytes, decrypt: bool) -> bytes:
    exe = shutil.which("openssl")
    if not exe:
        raise OSError("openssl not found")
    _key_bytes()
    cmd = [exe, "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "100000", "-salt",
           "-pass", "file:" + KEY_FILE, "-base64", "-A"]
    if decrypt:
        cmd.append("-d")
    p = subprocess.run(cmd, input=data, capture_output=True, timeout=20)
    if p.returncode != 0:
        raise OSError("openssl failed: " + p.stderr.decode("utf-8", "ignore")[:200])
    return p.stdout


def _stream(data: bytes) -> bytes:
    key = _key_bytes()
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        out += hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out))


def _choose_backend() -> str:
    forced = os.environ.get("MCP_VAULT_BACKEND")
    if forced:
        return forced
    if sys.platform.startswith("win"):
        return "DPAPI1"
    if shutil.which("openssl"):
        return "OSSL1"
    return "OBF1"


def _encrypt(plain: bytes, backend: str) -> bytes:
    if backend == "DPAPI1":
        body = base64.b64encode(_dpapi(plain, True))
    elif backend == "OSSL1":
        body = _openssl(plain, False)
    else:
        body = base64.b64encode(_stream(plain))
    return backend.encode() + b":" + body


def _decrypt(blob: bytes) -> bytes:
    head, body = blob.split(b":", 1)
    if head == b"DPAPI1":
        return _dpapi(base64.b64decode(body), False)
    if head == b"OSSL1":
        return _openssl(body, True)
    if head == b"OBF1":
        return _stream(base64.b64decode(body))
    raise ValueError("unknown vault format")


# ----------------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------------

def _load() -> dict:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        data = {}
        try:
            if os.path.exists(VAULT_FILE):
                with open(VAULT_FILE, "rb") as f:
                    data = json.loads(_decrypt(f.read()).decode("utf-8"))
        except Exception:
            data = {}   # 다른 계정/PC에서 복사된 파일 등 복호화 불가 -> 빈 금고
        _cache = data
        return _cache


def _save():
    global _backend_used
    with _lock:
        _ensure_dir()
        backend = _choose_backend()
        try:
            blob = _encrypt(json.dumps(_cache or {}).encode("utf-8"), backend)
        except Exception:
            backend = "OBF1"
            blob = _encrypt(json.dumps(_cache or {}).encode("utf-8"), backend)
        _backend_used = backend
        tmp = VAULT_FILE + ".tmp"
        old = os.umask(0o077)
        try:
            with open(tmp, "wb") as f:
                f.write(blob)
        finally:
            os.umask(old)
        os.replace(tmp, VAULT_FILE)
        try:
            os.chmod(VAULT_FILE, 0o600)
        except Exception:
            pass


def get(name: str, default: str = "") -> str:
    with _lock:
        return _load().get(name, default)


def has(name: str) -> bool:
    return bool(get(name))


def set(name: str, value: str):  # noqa: A001
    with _lock:
        data = _load()
        if value:
            data[name] = value
        else:
            data.pop(name, None)
        _save()


def delete(name: str):
    set(name, "")


def backend_name() -> str:
    return _backend_used or _choose_backend()


def is_weak() -> bool:
    """True면 진짜 암호화가 아닌 난독화 수준 (Android APK 등 openssl 없는 환경)."""
    return backend_name() == "OBF1"


def wipe():
    """금고와 키 파일을 모두 삭제."""
    global _cache
    with _lock:
        _cache = {}
        shutil.rmtree(VAULT_DIR, ignore_errors=True)
