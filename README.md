# 🧊 Blender MCP AI Assistant (Android & Termux PRoot)

안드로이드 기기 내부의 **Termux PRoot Linux (Debian/Ubuntu)** 환경에서 실행되는 Blender와 완벽하게 연동되는 **AI 챗 어시스턴트 & MCP (Model Context Protocol) 애드온**입니다.

---

## ✨ 주요 기능

1. **블렌더 MCP 컨트롤**:
   - `execute_blender_code`: 파이썬 스크립트 실행 (오브젝트 생성/변형, 재질, 조명, 카메라, 렌더링).
   - `get_scene_info`: 씬 내 오브젝트 및 재질 메타데이터 실시간 조회.
   - `capture_viewport`: 현재 3D 뷰포트 화면을 캡처하여 AI에게 시각적 피드백 제공.
   - 메인 스레드 안전성: `bpy.app.timers` 기반 작업 큐로 크래시 없는 안전한 실행.

2. **다중 대화 세션 (Multi-Session)**:
   - 새 채팅 세션 생성, 세션 이름 변경, 세션 히스토리 보관 및 삭제.
   - SQLite 기반 경량 내장 DB (Python 표준 라이브러리, 제로 의존성).

3. **멀티모달 이미지 지원**:
   - 📷 안드로이드 갤러리 또는 카메라 사진 직접 첨부.
   - 🖼️ 원클릭 뷰포트 스크린샷 캡처 및 프롬프트 첨부.
   - VLM (비전 모델: Claude 3.5 Sonnet, GPT-4o, Gemini, Qwen2.5-VL 등)과 완벽 호환.

4. **다양한 백엔드 & CLI 에이전트 지원**:
   - **Termux Claude Code / agy CLI**: 표준 MCP stdio 브릿지(`mcp_bridge.py`) 및 SSE 엔드포인트 지원.
   - **OpenRouter**: 최신 클로드, GPT, 딥시크 모델 연동.
   - **NVIDIA NIM**: 초고속 추론 마이크로서비스 연동.
   - **Local LLM**: Termux 내부 또는 로컬 네트워크의 Ollama, LM Studio, vLLM 연동.

5. **AI 모델 및 추론 성능(Reasoning) 조절**:
   - `reasoning_effort` (`None` / `Low` / `Medium` / `High` - o1, o3, DeepSeek R1).
   - `thinking_budget` (Claude 3.7 Sonnet 확장 사고 토큰 예산).
   - Temperature, System Prompt 실시간 커스텀.

6. **ARM64 환경 100% 무설치 호환 (Zero Dependency)**:
   - 외부 C-extension 빌드가 전혀 필요 없으며, 순수 파이썬 표준 라이브러리로 구축되어 PRoot Linux ARM64에서 즉시 실행됩니다.

---

## 🚀 빠른 시작 가이드 (Termux PRoot Linux)

### 1. 애드온 설치
Termux PRoot 터미널에서 다음 명령을 실행합니다:

```bash
cd ~/
# 저장소 복제 (또는 워크스페이스에서 복사)
git clone https://<your-repo>/mcp-chat-for-blender.git
cd mcp-chat-for-blender

# 자동 설치 스크립트 실행 (Blender 애드온 경로로 심볼릭 링크 생성)
chmod +x install_termux.sh
./install_termux.sh
```

### 2. 블렌더에서 애드온 활성화
1. 블렌더를 실행합니다 (`blender`).
2. 상단 메뉴에서 **Edit > Preferences > Add-ons** 로 이동합니다.
3. 검색창에 `MCP Chat`을 검색한 뒤 체크박스를 켭니다.
4. 3D 뷰포트 우측의 **N-패널(사이드바) > MCP Chat** 탭을 열면 서버 상태가 `Online (Port 8000)`으로 표시됩니다.

---

## 📱 안드로이드 모바일 사용 방법 (웹 UI / PWA)

블렌더가 실행 중인 상태에서 안드로이드의 브라우저(크롬, 삼성 인터넷 등)를 엽니다:

👉 **접속 주소**: `http://127.0.0.1:8000`

- **화면 분할(Split Screen) / 삼성 DeX**: 상단/좌측에 블렌더, 하단/우측에 웹 채팅창을 띄워놓고 작업하면 최적입니다.
- **홈 화면에 추가**: 브라우저 메뉴에서 "홈 화면에 추가"를 누르면 앱처럼 독립된 창으로 실행할 수 있습니다.
- **사진 첨부**: 하단 `📷` 버튼을 누르면 폰 갤러리나 카메라가 열려 사진을 첨부할 수 있습니다.
- **뷰포트 캡처**: 하단 `🖼️` 버튼을 누르면 현재 블렌더 화면을 즉시 캡처하여 첨부합니다.

---

## ⚡ Termux Claude Code / agy CLI 연동

Termux CLI 환경에서 Claude Code를 사용하여 블렌더를 조종하려면:

### 방법 1: `claude mcp add` 명령어 사용
```bash
claude mcp add blender python3 ~/mcp-chat-for-blender/mcp_bridge.py
```

### 방법 2: `~/.claude.json` 직접 설정
`~/.claude.json` 파일의 `mcpServers` 항목에 아래 내용을 추가합니다:

```json
{
  "mcpServers": {
    "blender": {
      "command": "python3",
      "args": ["/root/mcp-chat-for-blender/mcp_bridge.py"]
    }
  }
}
```

이제 Termux에서 `claude`를 실행하면 블렌더 MCP 도구(`execute_blender_code`, `get_scene_info`, `capture_viewport`)를 자동으로 인식하여 터미널에서 대화하며 블렌더를 조종할 수 있습니다!

---

## ⚙️ REST API & MCP 엔드포인트 명세

| 엔드포인트 | 메서드 | 설명 |
| :--- | :---: | :--- |
| `/` | `GET` | 모바일 반응형 웹 UI 서빙 |
| `/api/sessions` | `GET` / `POST` | 세션 목록 조회 및 신규 세션 생성 |
| `/api/sessions/<id>` | `GET` / `PATCH` / `DELETE` | 세션 상세, 설정 변경, 삭제 |
| `/api/sessions/<id>/messages` | `POST` | 메시지 전송 및 LLM 에이전트 자율 도구 실행 |
| `/api/blender/viewport` | `GET` | 3D 뷰포트 스크린샷 캡처 (Base64) |
| `/api/blender/scene` | `GET` | 현재 씬의 오브젝트 및 재질 요약 정보 |
| `/api/settings` | `GET` / `POST` | LLM 프로바이더 키, 모델, 추론 강도 설정 |
| `/mcp` | `POST` | MCP JSON-RPC 2.0 엔드포인트 |
| `/sse` | `GET` | MCP SSE 스트림 엔드포인트 |
