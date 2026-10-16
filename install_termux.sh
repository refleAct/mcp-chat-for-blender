#!/usr/bin/env bash
# ==============================================================================
# Installer script for Blender MCP Chat in Termux / PRoot Linux
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🚀 Setting up Blender MCP Chat in Termux / PRoot Linux..."

# Ensure mcp_bridge is executable
chmod +x "$SCRIPT_DIR/mcp_bridge.py"

# Detect Blender user scripts directory
BLENDER_CONFIG_BASE="$HOME/.config/blender"

if [ ! -d "$BLENDER_CONFIG_BASE" ]; then
    echo "📁 Creating Blender config base at $BLENDER_CONFIG_BASE..."
    mkdir -p "$BLENDER_CONFIG_BASE"
fi

# Find or ask for Blender version directory (e.g., 3.6, 4.0, 4.1, 4.2)
VERSION_DIRS=($(find "$BLENDER_CONFIG_BASE" -maxdepth 1 -mindepth 1 -type d -name "[0-9]*" | sort -V))

if [ ${#VERSION_DIRS[@]} -eq 0 ]; then
    DEFAULT_VER="4.2"
    TARGET_ADDON_DIR="$BLENDER_CONFIG_BASE/$DEFAULT_VER/scripts/addons/mcp-chat-for-blender"
    mkdir -p "$BLENDER_CONFIG_BASE/$DEFAULT_VER/scripts/addons"
else
    # Use newest installed version
    LATEST_DIR="${VERSION_DIRS[-1]}"
    TARGET_ADDON_DIR="$LATEST_DIR/scripts/addons/mcp-chat-for-blender"
    mkdir -p "$LATEST_DIR/scripts/addons"
fi

echo "📦 Linking add-on into $TARGET_ADDON_DIR..."
rm -rf "$TARGET_ADDON_DIR"
ln -sf "$SCRIPT_DIR" "$TARGET_ADDON_DIR"

echo "✅ Add-on installed successfully!"
echo ""
echo "------------------------------------------------------------------------"
echo "👉 1. Blender 설정 방법:"
echo "   - Blender 실행 -> Edit -> Preferences -> Add-ons"
echo "   - 'MCP Chat for Blender' 검색 후 체크박스 활성화"
echo "   - 3D 뷰포트 우측 N-패널의 'MCP Chat' 탭에서 'Start Server' 확인"
echo ""
echo "👉 2. 안드로이드 모바일 브라우저 접속:"
echo "   - 크롬 또는 삼성인터넷에서 http://127.0.0.1:8000 접속"
echo "   - '홈 화면에 추가'하여 앱처럼 사용"
echo ""
echo "👉 3. Termux Claude Code / agy CLI 연동 (~/.claude.json):"
echo "   claude mcp add blender python3 $SCRIPT_DIR/mcp_bridge.py"
echo "------------------------------------------------------------------------"
