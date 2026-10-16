"""
GitHub Releases updater (stdlib only).

- check_latest(): reads the latest release of GITHUB_REPO and compares it with the installed version.
- install(): downloads the release zip, validates it, backs up the current files, and copies the new files over
  the add-on folder. The encrypted vault (.vault/) and backups are never touched.

Only https GitHub hosts are accepted. Blender must be restarted after an update.
"""

import io
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from urllib.parse import urlparse

GITHUB_REPO = "refleAct/mcp-chat-for-blender"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
KEEP_DIRS = {".vault", ".update_backup", "__pycache__"}
MAX_ZIP_BYTES = 50 * 1024 * 1024
ALLOWED_HOSTS = ("github.com", "githubusercontent.com")

# UI 상태 (설정 화면에서 읽음)
state = {"checking": False, "installing": False, "info": None, "message": "", "installed": False}


def parse_version(text) -> tuple:
    """'v0.8' -> (0, 8, 0), '0.8.001' -> (0, 8, 1)"""
    nums = [int(n) for n in re.findall(r"\d+", str(text))[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def format_version(t) -> str:
    return ".".join(str(n) for n in t)


def _check_url(url: str):
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS):
        raise ValueError(f"허용되지 않은 주소: {url}")


def _open(url: str, timeout: int = 20):
    _check_url(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": "MCP-Chat-for-Blender-Updater",
        "Accept": "application/vnd.github+json",
    })
    return urllib.request.urlopen(req, timeout=timeout)


def check_latest(current: tuple) -> dict:
    """최신 릴리즈 조회. 반환: {"ok", "newer", "latest", "tag", "asset_url", "notes", "page", "error"}"""
    try:
        with _open(API_LATEST) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False, "error": "게시된 릴리즈가 없습니다."}
        return {"ok": False, "error": f"GitHub 응답 오류 (HTTP {e.code})"}
    except Exception as e:
        return {"ok": False, "error": f"확인 실패: {e}"}

    tag = data.get("tag_name", "")
    latest = parse_version(tag)
    asset_url = ""
    for a in data.get("assets", []) or []:
        if str(a.get("name", "")).lower().endswith(".zip"):
            asset_url = a.get("browser_download_url", "")
            break
    return {
        "ok": True,
        "tag": tag,
        "latest": format_version(latest),
        "newer": latest > tuple(current),
        "asset_url": asset_url,
        "notes": (data.get("body") or "")[:600],
        "page": data.get("html_url", ""),
        "error": "",
    }


def _safe_members(zf: zipfile.ZipFile):
    """zip 내부 경로를 검증해서 (원본 이름, 루트 폴더를 뺀 상대 경로) 목록을 반환."""
    names = [n for n in zf.namelist() if not n.endswith("/")]
    roots = {n.split("/", 1)[0] for n in names if "/" in n}
    root = None
    for r in roots:
        if f"{r}/__init__.py" in names:
            root = r
            break
    if root is None:
        raise ValueError("올바른 애드온 zip이 아닙니다 (루트 폴더에 __init__.py 없음)")
    out = []
    for n in names:
        if not n.startswith(root + "/"):
            continue
        rel = os.path.normpath(n[len(root) + 1:])
        if rel.startswith("..") or os.path.isabs(rel) or rel.split(os.sep)[0] in KEEP_DIRS:
            continue
        out.append((n, rel))
    return out


def install(asset_url: str, current: tuple, addon_dir: str = ADDON_DIR):
    """릴리즈 zip을 내려받아 애드온 폴더에 덮어쓴다. 반환: (성공 여부, 메시지)"""
    if not asset_url:
        return False, "릴리즈에 zip 파일이 없습니다."
    try:
        with _open(asset_url, timeout=60) as resp:
            buf = io.BytesIO()
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                buf.write(chunk)
                if buf.tell() > MAX_ZIP_BYTES:
                    return False, "zip 파일이 너무 큽니다."
        buf.seek(0)
        zf = zipfile.ZipFile(buf)
        members = _safe_members(zf)

        init_text = zf.read(next(n for n, rel in members if rel == "__init__.py")).decode("utf-8", "ignore")
        m = re.search(r'"version"\s*:\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)', init_text)
        if not m or "bl_info" not in init_text:
            return False, "zip 안의 애드온 정보를 읽을 수 없습니다."
        new_ver = tuple(int(x) for x in m.groups())
        if new_ver <= tuple(current):
            return False, f"이미 최신 버전입니다 (v{format_version(current)})."

        # 백업: 현재 파일을 .update_backup/ 에 보관 (이전 백업은 교체)
        backup = os.path.join(addon_dir, ".update_backup", format_version(current))
        shutil.rmtree(os.path.join(addon_dir, ".update_backup"), ignore_errors=True)
        os.makedirs(backup, exist_ok=True)
        for root_dir, dirs, files in os.walk(addon_dir):
            dirs[:] = [d for d in dirs if d not in KEEP_DIRS]
            for f in files:
                src = os.path.join(root_dir, f)
                dst = os.path.join(backup, os.path.relpath(src, addon_dir))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

        # 새 파일 적용 (임시 폴더에 먼저 풀어 검증 후 복사)
        with tempfile.TemporaryDirectory() as tmp:
            for name, rel in members:
                target = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            for _, rel in members:
                dest = os.path.join(addon_dir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(os.path.join(tmp, rel), dest)
        return True, f"v{format_version(new_ver)} 설치 완료. Blender를 재시작하세요."
    except Exception as e:
        return False, f"업데이트 실패: {e}"
