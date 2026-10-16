# 🧊 MCP Chat for Blender  `v0.8.2`

Blender 3D 뷰포트 안에서 **AI와 대화하며 3D 모델링을 시키는 애드온**입니다.
Claude Code · Codex · agy CLI · OpenRouter 등 여러 AI 엔진을 N패널 채팅창에서 바로 쓰고, AI가 만든 파이썬(bpy) 코드를 작업 큐로 안전하게 실행·저장합니다.

> ## ⚠️ 알림 (미완성 부분)
> **Blender 안드로이드(비공식 빌드)에서 Termux 연동으로 Claude를 쓰려고 했지만 미완성입니다.**
> 안드로이드 Blender(APK)는 앱 샌드박스 때문에 Termux에 설치된 `claude`를 직접 실행할 수 없어서, Termux에 중계 서버(`termux_agent.py`)를 띄워 연결하는 방식으로 만들었습니다. 코드와 설치 스크립트는 들어 있지만 **실제 안드로이드 기기에서 끝까지 동작하는 것은 확인하지 못했습니다.**
> 현재 정상 동작을 확인한 환경은 **Windows PC의 Blender + PC에 설치된 Claude Code**입니다. Codex CLI, agy CLI, macOS/Linux는 코드만 작성했고 검증하지 못했습니다.

---

## 1. 용도

- Blender 안에서 "이 사진처럼 모자를 만들어 줘" 같은 문장으로 3D 모델링·재질 작업을 AI에게 시킵니다.
- AI가 만든 코드를 바로 실행하지 않고 **작업 큐**에 쌓아 순서대로 실행하고, 성공할 때마다 `.blend` / `.glb` / 뷰포트 이미지를 자동 저장합니다.
- 작업 전에 **계획(Plan)을 먼저 검토**하고, 마음에 들면 실행하거나 계속 수정할 수 있습니다.

## 2. 주요 기능 요약

| 구분 | 내용 |
|---|---|
| **AI 엔진** | Claude Code(기본), Codex CLI, agy CLI, Direct API(OpenRouter · NVIDIA NIM · 로컬 Ollama · 사용자 지정) |
| **모델/추론 설정** | N패널에서 엔진별 모델(드롭다운 + 직접 입력)과 추론 성능 선택 |
| **모드** | Chat(대화·즉시 실행) / Plan(계획 수립 후 검토) / Auto(계획 + 자동 실행) |
| **Plan 검토** | 계획이 나오면 **실행 · 계속 계획 · 취소** 버튼으로 선택 |
| **작업 큐** | 등록·수정·삭제·순서 변경(▲▼)·재시도·복제, 전역 딜레이(기본 60초), 하나의 지시 = 하나의 큐 작업 |
| **자동 저장** | 작업 성공 시 `.blend`(리소스 패킹) + `.glb` + 뷰포트 PNG, 저장 위치 지정 가능 |
| **채팅** | 세션 탭 최대 3개, 멀티라인 히스토리(스크롤), 대화 압축·초기화, 메시지 복사 |
| **이미지 첨부** | 로컬 이미지 / 뷰포트 스냅샷 최대 3장(작은 미리보기). AI가 참고해서 제작 |
| **프롬프트 확인** | 전송 전 **미리보기**, 전송 후 **실제 전송된 프롬프트**(Auto는 AI 계획 포함) 보기 |
| **AI 실행 규칙 편집** | 기본 규칙(Blender Execution Rules)을 애드온 설정에서 직접 수정·복원 |
| **자동 업데이트** | 애드온 설정에서 GitHub Releases 최신 버전 확인 후 설치 |
| **사용자 작업 지침** | "베벨은 2단계; 베벨 면에 검은색 버텍스 컬러 적용" 같은 지침을 모든 작업에 자동 적용 |
| **기본 안전 규칙** | 요청하지 않은 조명·카메라 추가 금지, 기존 오브젝트 보존, 새 컬렉션에 배치, 렌더링 준비까지만 수행 |
| **API 키 보안** | 키/토큰을 암호화해 애드온 폴더에 저장(애드온 삭제 시 함께 삭제) |
| **MCP 서버** | Blender 안에서 MCP/웹 서버 실행. Claude Code 등이 `execute_blender_code`, `get_scene_info`, `capture_viewport` 도구로 Blender를 직접 조종 |
| **웹 채팅 UI** | 브라우저(PC·모바일)에서도 같은 세션/큐 사용 |
| **다국어** | 한국어 · English · 中文 · 日本語 |
| **Blender 지원** | 3.x 이상 (MCP를 지원하는 AI 클라이언트면 버전 무관하게 연결 가능, 전 버전 검증은 미완) |

## 3. 설치

1. [Releases](https://github.com/refleAct/mcp-chat-for-blender/releases)에서 **`mcp-chat-for-blender-vX.Y.Z.zip`** 을 내려받습니다.
   - ⚠️ GitHub의 **"Source code (zip)" / "Download ZIP"은 사용하지 마세요.** 폴더 이름에 버전 점(`.`)이 들어가 Blender가 설치 후 `No module named 'mcp-chat-for-blender-0'` 오류를 냅니다. 반드시 Releases에 첨부된 zip을 쓰세요.
   - 직접 만들기: `python package_addon.py` → `Z:\App\mcp-chat-for-blender.zip` (경로는 스크립트에서 변경)
2. Blender → **Edit › Preferences › Add-ons › Install from Disk…** → zip 선택 → 체크박스로 활성화
3. 3D 뷰포트에서 **N 키 → `MCP Chat` 탭**
4. (선택) Claude Code 연동: 애드온 설정의 **Claude Code MCP 자동 등록** 클릭 후 PC에 `claude` CLI 설치

### 지원 Blender 버전

| 버전 | 상태 |
|---|---|
| Blender 3.x | 지원(애드온 최소 버전 3.0). 동작하는 것으로 보임 |
| Blender 4.x 이상 | 지원 |
| 안드로이드 Blender(비공식) | 실험적 — 위 알림 참고 |

- 외부 AI가 **MCP(Model Context Protocol)** 로 Blender에 접속하는 구조라서, MCP를 지원하는 AI 클라이언트라면 Blender 버전과 관계없이 연결할 수 있습니다.
- 다만 **모든 버전에서 검증한 것은 아닙니다.** 버전에 따라 일부 UI 동작이 다를 수 있습니다. GLB 내보내기는 Blender의 glTF 애드온이 켜져 있어야 합니다.
- 파이썬 외부 패키지는 필요 없습니다(표준 라이브러리만 사용).

## 4. 사용법

### 4-1. 기본 흐름
1. N패널 **MCP Chat** 탭에서 **Engine**(기본 Claude Code)과 **모델/추론 성능**을 고릅니다.
2. 모드를 고릅니다. **기본값은 Auto**(계획 + 자동 실행)입니다. 실행 전에 계획을 확인하고 싶으면 **Plan**을 선택하세요.
3. 프롬프트를 입력하고 **전송**합니다. (`+` 버튼으로 이미지 첨부, 📋 버튼으로 클립보드 붙여넣기)
4. 결과/진행 상황은 채팅 히스토리에 표시됩니다. (`⏳ 작업 중…` 줄 → 완료 시 `✅`)

![엔진·모델·추론 성능 선택](docs/images/engine-model.png)

### 4-2. 채팅 히스토리
- 긴 메시지는 여러 줄로 보이고, 마우스 휠/스크롤바로 이전 대화를 볼 수 있습니다.
- 메시지 첫 줄의 ▼ 펼치기, 📋 복사, 📝 **전송된 프롬프트 보기** 버튼.
- 헤더의 작은 버튼: 새로고침 / 대화 **압축**(오래된 대화를 요약 1개로) / **초기화** / 세션 삭제.

![채팅 히스토리](docs/images/chat-history.png)

### 4-3. Plan → 검토 → 실행
1. **Plan** 모드로 전송하면 AI가 단계별 계획을 만듭니다.
2. 입력창 위에 **계획 검토** 박스가 나타납니다.
   - **실행**: 승인한 계획을 작업 큐 1건으로 등록해 실행
   - **계속 계획**: 수정/추가 요청을 입력해 계획을 다시 작성
   - **✖**: 계획 버리기

### 4-4. 작업 큐
- **Auto** 모드나 **큐 등록** 버튼으로 작업이 큐에 쌓입니다.
- 항목마다 상태 아이콘(대기/실행중/완료/실패), ▲▼ 순서 변경, 수정, 재시도, 복제, 삭제가 있습니다.
- 하단에서 **저장 위치**, **리소스 패킹**, **GLB 내보내기**를 설정합니다.

![작업 큐](docs/images/task-queue.png)

> 스크린샷은 개발 중 화면이며 버전에 따라 조금 다를 수 있습니다.

### 4-5. 사용자 작업 지침
입력창 아래 지침 칸에 적어 두면 **모든 작업**에 적용됩니다. 여러 개는 `;`로 구분합니다.
예) `베벨은 2단계; 베벨 면에 검은색 버텍스 컬러 적용`

### 4-6. 서버 / 웹 UI
- 애드온 설정에서 서버를 시작하면 `http://127.0.0.1:8000` 에서 웹 채팅 UI를 쓸 수 있습니다.
- Claude Code 등 외부 AI는 `http://127.0.0.1:8000/mcp` 로 Blender를 조종합니다.

## 5. 안드로이드 + Termux 연동 (실험적 · 미완성)

> 이 기능은 **미완성**입니다. 아래는 설계된 방식이며 실기기 검증은 되지 않았습니다.

1. Blender(안드로이드)에서 서버 시작
2. Termux에서: `curl -fsS http://127.0.0.1:8000/termux/setup.sh | bash`
   - MCP 브릿지 다운로드, `claude`/`agy`/`codex` MCP 등록, **Termux Agent**(`127.0.0.1:8787`) 실행
3. Blender 설정 › **Termux Agent**에 출력된 URL/토큰 입력 → **Agent 연결 테스트**
4. Agent가 꺼졌다면 Termux에서 `bash ~/.config/blender_mcp_chat/start_agent.sh`

PC의 Blender를 폰의 Termux에서 조종하려면 **LAN 접속 허용**을 켜고(토큰 인증), PC 방화벽에서 TCP 8000을 허용한 뒤 설정 화면의 **Termux 설치 명령 복사**를 사용합니다.

## 6. 언어 지원

| 언어 | 애드온(Blender) UI | 웹 UI |
|---|---|---|
| 한국어 | ✅ | ✅ |
| English | ✅ | ❌ |
| 中文 (简体) | ✅ | ❌ |
| 日本語 | ✅ | ❌ |

- 애드온 설정 맨 위 **Language** 에서 자동(Blender 언어) / 한 / 영 / 중 / 일을 선택합니다.
- 번역은 `i18n.py`의 표 한 곳에서 수정·추가할 수 있습니다. 표에 없는 문구는 원문 그대로 표시됩니다.
- 툴팁, 이전에 저장된 채팅 내용, AI 응답 언어, 웹 UI는 번역되지 않습니다.

## 7. 구조

```
mcp-chat-for-blender/
├─ __init__.py          Blender 애드온 본체: 패널·연산자·설정, 채팅/큐 UI
├─ blender_bridge.py    Blender 메인 스레드 안전 실행, 씬 정보, 뷰포트 캡처, .blend/.glb 저장
├─ task_queue.py        작업 큐 워커(순차 실행·진행 표시·자동 저장·들여쓰기 복구)
├─ session_manager.py   SQLite 저장소(세션·메시지·큐·설정), 암호화 키 연동
├─ llm_client.py        Direct API 클라이언트, Plan 프롬프트 생성
├─ cli_runner.py        claude / codex / agy CLI 실행, 프롬프트 조립, Termux Agent 호출
├─ guidelines.py        AI 기본 규칙 + 사용자 작업 지침(모든 엔진 공통)
├─ secrets_store.py     API 키/토큰 암호화 금고 (DPAPI · openssl · 난독화 폴백)
├─ i18n.py              UI 번역 표 (ko/en/zh/ja)
├─ server.py            HTTP/MCP 서버, 웹 UI·REST API, 토큰 인증
├─ mcp_handler.py       MCP JSON-RPC 도구 처리
├─ mcp_bridge.py        stdio ↔ HTTP MCP 브릿지 (Claude Code 등에서 사용)
├─ termux_agent.py      Termux에서 실행하는 CLI 중계 서버
├─ install_termux.sh    PRoot 환경 설치 스크립트
├─ package_addon.py     배포용 zip 패키징
├─ static/              웹 채팅 UI (index.html · app.js · style.css)
└─ docs/images/         README 스크린샷
```

데이터 위치: `~/.config/blender_mcp_chat/` (대화 DB, 저장된 .blend/.glb/이미지). 암호화된 키는 애드온 폴더 안 `.vault/`에 있습니다.

## 8. 보안 메모
- API 키·토큰은 암호화 저장되며 웹 API는 키를 돌려주지 않습니다.
- LAN 접속은 기본 꺼짐이며, 켜면 Bearer 토큰이 필요합니다. 로컬 접속도 Origin/Host를 검사합니다.
- 이 애드온은 AI가 만든 **파이썬 코드를 Blender에서 실행**합니다. 중요한 작업 파일은 백업하고 신뢰하는 AI/네트워크에서만 사용하세요.

## 9. 알려진 한계
- 안드로이드 Termux 연동 미완성(위 알림 참고)
- Blender 입력창에서 **한글 입력 중 띄어쓰기**가 안 되는 문제가 보고됨 (Blender/IME 쪽 문제로 추정). 웹 채팅 UI 입력이나 붙여넣기 버튼으로 우회 가능
- CLI 엔진(Claude/Codex/agy)은 매 요청이 새 대화로 실행됨(이전 대화 이어쓰기 없음)
- 진행 표시는 글자 기반이며 회전 애니메이션은 없음

## 10. 버전 규칙

- 현재 버전: **0.8.2**
- **기능 추가**: 0.1 단위로 올림 (0.8 → 0.9 → 1.0 …)
- **버그 수정**: 0.0.1 단위로 올림 (0.8.1 → 0.8.2 … 최대 0.8.999)
- Blender `bl_info`에는 `(0, 8, 2)` 형태의 튜플로 기록됩니다. 변경 내역은 [CHANGELOG.md](CHANGELOG.md) 참고.

## 11. 출처 및 참조 (Credits)

이 프로젝트는 아래 사양·도구·서비스를 **참조하거나 외부 프로그램으로 호출**합니다. 이름과 상표는 각 소유자에게 있으며, 이 프로젝트는 이들과 제휴 관계가 아닙니다.

| 항목 | 이 프로젝트에서의 사용 | 출처 |
|---|---|---|
| **MCP (Model Context Protocol)** | Blender 제어용 서버(`mcp_handler.py`)·stdio 브릿지(`mcp_bridge.py`)를 **공개 사양(프로토콜 버전 2024-11-05)을 보고 직접 구현**. 외부 MCP SDK 코드는 포함하지 않음 | Anthropic · <https://modelcontextprotocol.io> |
| **Claude Code** | 외부 CLI로 실행 (`claude -p`, `--model`, `--effort`, `--permission-mode`) | Anthropic · <https://docs.claude.com/en/docs/claude-code> |
| **Codex CLI** | 외부 CLI로 실행 (`codex exec`, `-m`, `-i`, `-c model_reasoning_effort`), `~/.codex/config.toml` MCP 등록 | OpenAI · <https://github.com/openai/codex> |
| **agy CLI** | 외부 CLI로 실행 (Antigravity) | Google Antigravity |
| **OpenRouter / NVIDIA NIM / Ollama · LM Studio** | Direct API 모드 (OpenAI 호환 Chat Completions 형식) | <https://openrouter.ai> · <https://build.nvidia.com> · <https://ollama.com> |
| **Blender Python API (`bpy`)** | 애드온 UI, 씬 제어, 저장 | Blender Foundation · <https://docs.blender.org/api/current/> (GPL) |
| **glTF 2.0 / glTF-Blender-IO** | `.glb` 내보내기에 Blender 내장 glTF 애드온 호출 | Khronos Group · <https://github.com/KhronosGroup/glTF-Blender-IO> (Apache-2.0) |
| **ambientCG** | AI 지침의 "AmbientCG 스타일 PBR 재질" 참조 (텍스처 파일은 포함하지 않음) | <https://ambientcg.com> (CC0) |
| **Termux** | 안드로이드 연동 대상 환경 (실험적) | <https://termux.dev> |
| **Windows DPAPI / OpenSSL** | API 키 암호화 저장 (Windows는 DPAPI, 그 외 `openssl enc -aes-256-cbc`) | Microsoft · <https://www.openssl.org> (Apache-2.0) |
| **GitHub Releases API** | 애드온 업데이트 확인 | <https://docs.github.com/rest/releases> |
| **Python 표준 라이브러리** | `http.server`, `sqlite3`, `urllib`, `zipfile` 등 (외부 패키지 번들 없음) | Python Software Foundation |

- 외부 라이브러리/SDK 소스코드는 이 저장소에 **포함하지 않았습니다**(표준 라이브러리만 사용). 외부 서비스·CLI는 사용자가 직접 설치/가입해야 합니다.
- 설계와 구현은 **Anthropic Claude Code** 와의 협업으로 작성되었습니다.
- 이 애드온은 `bpy`를 사용하므로 Blender의 GPL과 **호환되는 라이선스(MIT 기반)** 로 배포합니다.
- 출처에 빠졌거나 잘못된 항목은 이슈로 알려 주세요.

## 12. 작성
- 작성: **refleAct**
- AI 협업: Anthropic **Claude Code**와 함께 설계·구현
- 비공식 프로젝트이며 Blender Foundation, Anthropic, OpenAI, Google과 무관합니다.

## 13. 라이선스

**MIT 기반 + 출처 표기 유지 조건**

- ✅ **소스 수정** 가능
- ✅ **재배포** 가능 (수정본 포함, 상업적 이용 포함)
- ⚠️ **저작권 표기와 출처는 변경·삭제하지 마세요.** 수정·배포할 때 원 저작자(작성: refleAct)와 이 라이선스 문구를 그대로 유지해야 합니다.
- 소프트웨어는 **있는 그대로** 제공되며, 사용으로 인한 문제(작업 파일 손상 등)에 책임지지 않습니다.

전문은 [LICENSE](LICENSE) 파일을 참고하세요.

---

## English summary

**MCP Chat for Blender** lets you chat with AI (Claude Code, Codex CLI, agy CLI, OpenRouter/NVIDIA NIM/Ollama) in Blender's N-panel to build 3D models. AI-generated bpy code runs through a safe task queue with auto-save (`.blend` with packed resources, `.glb`, viewport PNG). Includes plan review (run / refine), prompt preview, user rules, encrypted API-key storage, and UI languages ko/en/zh/ja.

> **Notice:** Using Claude through Termux from the unofficial Blender for Android is **incomplete and unverified**. Verified setup: Blender on Windows PC with Claude Code on the same PC.

License: MIT-based — modify and redistribute freely, but **do not remove or alter the copyright/attribution notice**. See [LICENSE](LICENSE).
