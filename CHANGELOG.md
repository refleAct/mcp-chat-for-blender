# Changelog

버전 규칙: 기능 추가 = 0.1 단위, 버그 수정 = 0.0.1 단위 (최대 .999)

## 0.8.5
- Web settings: every provider field (Custom endpoint / key / model, other keys) is optional; blank model or URL falls back to the provider default; fields are labeled optional

## 0.8.4
- Web UI works without an API key: chat / plan / auto fall back to an installed CLI (Claude Code → Codex → agy)
- README: prominent API-key security warning in all four languages

## 0.8.3
- Author/maintainer shown as **refleaction** (add-on info, LICENSE, README)
- README in English / 한국어 / 中文 / 日本語 with real English UI screenshots; API-key storage notes; manual MCP setup for each CLI
- Default chat wrap width 26 cells (no mid-line `...`), shorter model labels, queue state label fully translated
- `mcp_bridge.py --check` output is now English

## 0.8.2
- GitHub Actions: pushing a `v*` tag builds the add-on zip and publishes it to Releases automatically
- Install guide: use the Releases zip, not GitHub's "Source code (zip)" (that one fails with `No module named 'mcp-chat-for-blender-0'`)

## 0.8.1
- 큐 패널: 자동 저장 토글(.blend 스냅샷 / 뷰포트 이미지)을 저장 위치 설정 아래로 이동
- 채팅 히스토리 기본 높이 5줄, 한글 폭 기준 줄바꿈(말줄임 방지)

## 0.8 (첫 공개)
- N패널 AI 채팅(세션 탭 3개, 멀티라인 스크롤 히스토리, 대화 압축/초기화)
- 엔진: Claude Code(기본) / Codex CLI / agy CLI / Direct API, 엔진별 모델·추론 성능 드롭다운
- 모드: Chat / Plan(검토 후 실행·계속 계획) / Auto(기본값), 하나의 지시 = 하나의 큐 작업
- 작업 큐: 등록·수정·삭제·순서 변경·재시도·복제, 전역 딜레이, 진행/완료 표시
- 자동 저장: .blend(리소스 패킹) + .glb + 뷰포트 PNG, 저장 위치 지정
- 이미지 첨부(최대 3장, 미리보기), 전송 프롬프트 미리보기/기록
- 사용자 작업 지침(N패널), AI 기본 안전 규칙(영어 프롬프트) + 설정에서 규칙 편집/복원
- GitHub Releases 업데이트 확인/설치 버튼, 출처 표기
- API 키/토큰 암호화 저장(애드온 폴더, 삭제 시 함께 삭제)
- MCP/웹 서버, LAN 토큰 인증, Termux Agent(실험적, 미완성)
- UI 다국어: 한국어 / English / 中文 / 日本語
