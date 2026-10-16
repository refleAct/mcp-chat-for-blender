"""
Add-on UI translation (ko / en / zh / ja).

Source strings in the code are Korean (or English for a few labels). tr() looks the source string up in TABLE
and returns the text for the selected language. Strings with "{}" placeholders are matched as patterns, so
f-string messages such as "작업 '{}'(이)가 수정되었습니다." are translated too.

Language setting: Preferences > 언어 / Language  (AUTO follows Blender's interface language).
"""

import re

LANGS = ("ko", "en", "zh", "ja")

_state = {"lang": "AUTO", "blender_locale": ""}

# source: (ko, en, zh, ja)   -- ko may be None when the source already is Korean
_T = {
    # ---- chat panel ----
    "전송": (None, "Send", "发送", "送信"),
    "큐 등록": (None, "Queue", "加入队列", "キュー登録"),
    "이름 변경": (None, "Rename", "重命名", "名前変更"),
    "모델": (None, "Model", "模型", "モデル"),
    "모델 ID": (None, "Model ID", "模型 ID", "モデルID"),
    "실행": (None, "Run", "执行", "実行"),
    "계속 계획": (None, "Refine plan", "继续规划", "計画を続ける"),
    "계획 검토: {}": (None, "Review plan: {}", "审阅计划: {}", "計画の確認: {}"),
    "수정/추가 요청을 입력하고 전송하세요": (None, "Enter your changes and send", "请输入修改/补充要求并发送", "修正・追加の要望を入力して送信してください"),
    "대화 기록이 없습니다. 프롬프트를 입력하세요.": (None, "No messages yet. Enter a prompt.", "暂无对话记录。请输入提示词。", "会話履歴がありません。プロンプトを入力してください。"),
    "첨부 이미지 ({}/3)": (None, "Attached images ({}/3)", "附加图片 ({}/3)", "添付画像 ({}/3)"),
    "표시 줄 수": (None, "Visible lines", "显示行数", "表示行数"),
    "채팅 콘솔 로딩 오류: {}": (None, "Chat console error: {}", "聊天控制台加载错误: {}", "チャットコンソール読み込みエラー: {}"),
    "세션 {}": (None, "Session {}", "会话 {}", "セッション {}"),
    "세션 1": (None, "Session 1", "会话 1", "セッション 1"),
    "세션 {} 새 이름:": (None, "New name for session {}:", "会话 {} 的新名称:", "セッション {} の新しい名前:"),
    "새 이름": (None, "New name", "新名称", "新しい名前"),
    "📁 로컬 이미지 첨부...": (None, "📁 Attach local image...", "📁 附加本地图片...", "📁 ローカル画像を添付..."),
    "📸 뷰포트 스냅샷 첨부": (None, "📸 Attach viewport snapshot", "📸 附加视口快照", "📸 ビューポートのスナップショットを添付"),
    "최대 3개 첨부 완료 (3/3)": (None, "Maximum 3 attached (3/3)", "已附加最多 3 张 (3/3)", "最大3枚まで添付済み (3/3)"),
    "✅ 생성이 완료되었습니다.": (None, "✅ Generation complete.", "✅ 生成完成。", "✅ 生成が完了しました。"),
    "(내용 없음)": (None, "(empty)", "(无内容)", "(内容なし)"),
    "저장 위치": (None, "Output folder", "保存位置", "保存場所"),
    "리소스 패킹": (None, "Pack resources", "打包资源", "リソースのパック"),
    "GLB 내보내기": (None, "Export GLB", "导出 GLB", "GLB エクスポート"),
    "⏳ {} 작업 중…": (None, "⏳ {} working…", "⏳ {} 工作中…", "⏳ {} 作業中…"),
    "⏳ Plan 수립 중…": (None, "⏳ Building plan…", "⏳ 正在制定计划…", "⏳ 計画を作成中…"),
    "⏳ AI 응답 생성 중…": (None, "⏳ AI is generating a response…", "⏳ AI 正在生成回复…", "⏳ AI が応答を生成中…"),
    "⏳ 작업 진행중: {} - {}": (None, "⏳ Task in progress: {} - {}", "⏳ 任务进行中: {} - {}", "⏳ タスク進行中: {} - {}"),
    "계획 수립 중": (None, "Building plan", "正在制定计划", "計画を作成中"),
    "실행 중": (None, "Running", "执行中", "実行中"),
    "CLI 작업 중": (None, "CLI working", "CLI 工作中", "CLI 作業中"),
    "Step {}/{} 실행 중: {}": (None, "Step {}/{} running: {}", "步骤 {}/{} 执行中: {}", "ステップ {}/{} 実行中: {}"),
    "줄 너비": (None, "Line width", "行宽", "行幅"),
    # ---- queue panel ----
    "작업 큐 목록 ({}개):": (None, "Task queue ({} items):", "任务队列 ({} 项):", "タスクキュー ({}件):"),
    "등록된 큐 작업이 없습니다.": (None, "No queued tasks.", "队列中没有任务。", "キューにタスクがありません。"),
    "작업 개시": (None, "Start", "开始任务", "開始"),
    "일시정지": (None, "Pause", "暂停", "一時停止"),
    "재개": (None, "Resume", "继续", "再開"),
    "비우기": (None, "Clear", "清空", "クリア"),
    "완료/실패 항목 정리": (None, "Clear finished/failed", "清理已完成/失败项", "完了/失敗を整理"),
    "전역 딜레이(초)": (None, "Global delay (s)", "全局延迟(秒)", "グローバル遅延(秒)"),
    "자동 저장:": (None, "Auto-save:", "自动保存:", "自動保存:"),
    ".blend 스냅샷": (None, ".blend snapshot", ".blend 快照", ".blend スナップショット"),
    "뷰포트 이미지": (None, "Viewport image", "视口图片", "ビューポート画像"),
    "대기: {}": (None, "Pending: {}", "等待: {}", "待機: {}"),
    "실행중: {}": (None, "Running: {}", "执行中: {}", "実行中: {}"),
    "완료: {}": (None, "Done: {}", "完成: {}", "完了: {}"),
    "PAUSED (일시정지)": (None, "PAUSED", "已暂停", "一時停止中"),
    "RUNNING (동작중)": (None, "RUNNING", "运行中", "実行中"),
    "작업큐 로딩 오류: {}": (None, "Queue panel error: {}", "队列面板加载错误: {}", "キューパネルのエラー: {}"),
    # ---- preferences ----
    "사용자 작업 지침 (모든 AI 작업에 적용)": (None, "User rules (applied to every AI task)", "用户工作准则 (适用于所有 AI 任务)", "ユーザー作業指針 (すべてのAI作業に適用)"),
    "여러 개는 ; 로 구분. 예) 베벨은 2단계; 베벨 면에 검은색 버텍스 컬러 적용": (None, "Separate multiple rules with ;  e.g. Bevel with 2 segments; black vertex color on bevel faces", "多条用 ; 分隔。例) 倒角 2 段; 倒角面应用黑色顶点色", "複数は ; で区切る。例) ベベルは2段階; ベベル面に黒い頂点カラーを適用"),
    "Direct API 설정 (OpenRouter / NVIDIA NIM / Local Ollama)": (None, "Direct API settings (OpenRouter / NVIDIA NIM / Local Ollama)", "Direct API 设置 (OpenRouter / NVIDIA NIM / Local Ollama)", "Direct API 設定 (OpenRouter / NVIDIA NIM / Local Ollama)"),
    "Termux Agent (Android Blender APK + Termux의 claude/agy/codex)": (None, "Termux Agent (Android Blender APK + claude/agy/codex in Termux)", "Termux Agent (Android Blender APK + Termux 中的 claude/agy/codex)", "Termux Agent (Android Blender APK + Termux の claude/agy/codex)"),
    "Agent 연결 테스트": (None, "Test Agent connection", "测试 Agent 连接", "Agent 接続テスト"),
    "Termux에서 설치 명령 실행 후 출력되는 URL/토큰을 입력하세요 (아래 로컬 서버 설정 참고)": (None, "Run the install command in Termux, then enter the printed URL/token (see local server settings below)", "在 Termux 运行安装命令后，输入输出的 URL/令牌 (参见下方本地服务器设置)", "Termux でインストールコマンドを実行し、出力された URL/トークンを入力してください (下のローカルサーバー設定を参照)"),
    "Claude Code MCP 자동 등록": (None, "Auto-register Claude Code MCP", "自动注册 Claude Code MCP", "Claude Code MCP を自動登録"),
    "Codex CLI MCP 자동 등록": (None, "Auto-register Codex CLI MCP", "自动注册 Codex CLI MCP", "Codex CLI MCP を自動登録"),
    "agy CLI MCP 자동 등록": (None, "Auto-register agy CLI MCP", "自动注册 agy CLI MCP", "agy CLI MCP を自動登録"),
    "환경 감지: {}": (None, "Environment: {}", "环境检测: {}", "環境検出: {}"),
    "환경 감지 오류: {}": (None, "Environment detection error: {}", "环境检测错误: {}", "環境検出エラー: {}"),
    "{}: 감지됨 ({})": (None, "{}: detected ({})", "{}: 已检测到 ({})", "{}: 検出済み ({})"),
    "{}: 미감지": (None, "{}: not found", "{}: 未检测到", "{}: 未検出"),
    "Termux 접속 정보 (서버 재시작 후 적용)": (None, "Termux connection info (applies after server restart)", "Termux 连接信息 (服务器重启后生效)", "Termux 接続情報 (サーバー再起動後に適用)"),
    "  Token: {}…{}  (복사 버튼으로 전체 사용)": (None, "  Token: {}…{}  (use the copy button for the full token)", "  令牌: {}…{}  (使用复制按钮获取完整令牌)", "  トークン: {}…{}  (コピーボタンで全体を使用)"),
    "Termux 설치 명령 복사": (None, "Copy Termux install command", "复制 Termux 安装命令", "Termux インストールコマンドをコピー"),
    "토큰 재발급": (None, "Regenerate token", "重新生成令牌", "トークン再発行"),
    "폰 Termux에서 복사한 명령을 붙여넣어 실행. Windows 방화벽 TCP 포트 허용 필요": (None, "Paste and run the copied command in Termux. The Windows firewall must allow the TCP port", "在手机 Termux 中粘贴运行复制的命令。需要在 Windows 防火墙放行该 TCP 端口", "コピーしたコマンドをスマホの Termux に貼り付けて実行。Windows ファイアウォールで TCP ポートの許可が必要"),
    "현재 로컬 전용 (PC 내부에서만 접속 가능)": (None, "Local only (reachable from this PC only)", "当前仅限本机 (只能在本 PC 内访问)", "現在はローカル専用 (この PC 内からのみ接続可能)"),
    # ---- operator reports ----
    "새 세션 '{}'(이)가 추가되었습니다.": (None, "Session '{}' was added.", "已添加新会话 '{}'。", "新しいセッション '{}' を追加しました。"),
    "세션은 최대 3개까지만 추가할 수 있습니다.": (None, "You can add up to 3 sessions.", "最多只能添加 3 个会话。", "セッションは最大3つまで追加できます。"),
    "세션이 삭제되었습니다.": (None, "Session deleted.", "会话已删除。", "セッションを削除しました。"),
    "마지막 세션이 삭제되어 새 '세션 1'이 만들어졌습니다.": (None, "The last session was deleted; a new 'Session 1' was created.", "最后一个会话已删除，已创建新的“会话 1”。", "最後のセッションを削除したため、新しい「セッション 1」を作成しました。"),
    "세션 이름을 입력해 주세요.": (None, "Please enter a session name.", "请输入会话名称。", "セッション名を入力してください。"),
    "세션 이름이 '{}'(으)로 변경되었습니다.": (None, "Session renamed to '{}'.", "会话已重命名为 '{}'。", "セッション名を '{}' に変更しました。"),
    "메시지가 복사되었습니다.": (None, "Message copied.", "消息已复制。", "メッセージをコピーしました。"),
    "클립보드에 텍스트가 없습니다.": (None, "No text in the clipboard.", "剪贴板中没有文本。", "クリップボードにテキストがありません。"),
    "{}개 메시지를 요약으로 압축했습니다.": (None, "Compacted {} messages into a summary.", "已将 {} 条消息压缩为摘要。", "{}件のメッセージを要約に圧縮しました。"),
    "압축할 이전 대화가 충분하지 않습니다.": (None, "Not enough earlier messages to compact.", "没有足够的历史对话可压缩。", "圧縮する過去の会話が足りません。"),
    "MCP Chat 세션 및 모듈이 새로고침되었습니다.": (None, "MCP Chat sessions and modules reloaded.", "MCP Chat 会话和模块已刷新。", "MCP Chat のセッションとモジュールを再読み込みしました。"),
    "새로고침 실패: {}": (None, "Reload failed: {}", "刷新失败: {}", "再読み込み失敗: {}"),
    "초기화 실패: {}": (None, "Clear failed: {}", "清除失败: {}", "クリア失敗: {}"),
    "이미지는 최대 3개까지만 첨부할 수 있습니다.": (None, "You can attach up to 3 images.", "最多只能附加 3 张图片。", "画像は最大3枚まで添付できます。"),
    "첨부됨: {} ({}/3)": (None, "Attached: {} ({}/3)", "已附加: {} ({}/3)", "添付しました: {} ({}/3)"),
    "뷰포트 스냅샷 첨부됨 ({}/3)": (None, "Viewport snapshot attached ({}/3)", "已附加视口快照 ({}/3)", "ビューポートのスナップショットを添付しました ({}/3)"),
    "스냅샷 캡처 실패: {}": (None, "Snapshot capture failed: {}", "快照捕获失败: {}", "スナップショットの取得に失敗: {}"),
    "이미지 읽기 실패: {}": (None, "Failed to read image: {}", "读取图片失败: {}", "画像の読み込みに失敗: {}"),
    "안드로이드 저장소 권한 오류: Termux 터미널에서 'termux-setup-storage'를 실행하거나 브라우저 웹 UI(http://127.0.0.1:8000)에서 첨부하세요.": (None, "Android storage permission error: run 'termux-setup-storage' in Termux, or attach from the browser web UI (http://127.0.0.1:8000).", "Android 存储权限错误: 请在 Termux 中运行 'termux-setup-storage'，或通过浏览器网页界面 (http://127.0.0.1:8000) 附加。", "Android ストレージ権限エラー: Termux で 'termux-setup-storage' を実行するか、ブラウザの Web UI (http://127.0.0.1:8000) から添付してください。"),
    "프롬프트 또는 이미지를 입력하세요": (None, "Enter a prompt or an image", "请输入提示词或图片", "プロンプトまたは画像を入力してください"),
    "[{}] {} 모드로 프롬프트 실행 중...": (None, "[{}] Running prompt in {} mode...", "[{}] 正在以 {} 模式执行提示词...", "[{}] {} モードでプロンプトを実行中..."),
    "단계별 Plan 계획 수립 중...": (None, "Building a step-by-step plan...", "正在制定分步计划...", "段階的な計画を作成中..."),
    "오토 모드: 계획 생성 후 작업큐 자동 실행...": (None, "Auto mode: generating a plan and running it via the queue...", "自动模式: 生成计划后通过任务队列自动执行...", "オートモード: 計画を生成してキューで自動実行..."),
    "AI 추론 및 실행 중...": (None, "AI is thinking and running...", "AI 正在推理并执行...", "AI が推論・実行中..."),
    "전송 프롬프트를 텍스트 창에 표시했습니다.": (None, "Sent prompt shown in the text editor.", "已在文本窗口中显示发送的提示词。", "送信プロンプトをテキストエディターに表示しました。"),
    "전송된 프롬프트를 텍스트 창에 표시했습니다.": (None, "Sent prompt shown in the text editor.", "已在文本窗口中显示已发送的提示词。", "送信済みプロンプトをテキストエディターに表示しました。"),
    "텍스트 에디터를 열 수 없습니다. Text Editor에서 '{}'를 선택해 확인하세요.": (None, "Cannot open the text editor. Select '{}' in a Text Editor to view it.", "无法打开文本编辑器。请在 Text Editor 中选择 '{}' 查看。", "テキストエディターを開けません。Text Editor で '{}' を選択して確認してください。"),
    "텍스트 에디터를 열 수 없습니다. Text Editor에서 'MCP Sent Prompt'를 선택하세요.": (None, "Cannot open the text editor. Select 'MCP Sent Prompt' in a Text Editor.", "无法打开文本编辑器。请在 Text Editor 中选择 'MCP Sent Prompt'。", "テキストエディターを開けません。Text Editor で 'MCP Sent Prompt' を選択してください。"),
    "저장된 프롬프트가 없습니다.": (None, "No saved prompt.", "没有已保存的提示词。", "保存されたプロンプトがありません。"),
    "실행할 계획이 없습니다.": (None, "There is no plan to run.", "没有可执行的计划。", "実行する計画がありません。"),
    "수정/추가 요청을 입력하고 전송하세요.": (None, "Enter your changes and send.", "请输入修改/补充要求并发送。", "修正・追加の要望を入力して送信してください。"),
    "▶ 계획이 작업 큐 1건으로 등록되어 실행됩니다 ('{}').": (None, "▶ The plan was queued as 1 task and will run ('{}').", "▶ 计划已作为 1 个任务加入队列并执行 ('{}')。", "▶ 計画を1件のタスクとしてキューに登録し実行します ('{}')。"),
    "⚡ Auto Mode: 지시가 작업 큐 1건으로 등록되었습니다 ('{}'). 계획 수립과 단계 실행은 이 작업 안에서 순차 처리됩니다.": (None, "⚡ Auto Mode: your instruction was queued as 1 task ('{}'). Planning and step execution run inside this task.", "⚡ 自动模式: 指令已作为 1 个任务加入队列 ('{}')。计划制定和步骤执行将在该任务内依次处理。", "⚡ オートモード: 指示を1件のタスクとしてキューに登録しました ('{}')。計画作成とステップ実行はこのタスク内で順次処理されます。"),
    "Direct API 설정 저장됨 ({}: {})": (None, "Direct API settings saved ({}: {})", "Direct API 设置已保存 ({}: {})", "Direct API 設定を保存しました ({}: {})"),
    "사용자 작업 지침이 저장되었습니다.": (None, "User rules saved.", "用户工作准则已保存。", "ユーザー作業指針を保存しました。"),
    "사용자 작업 지침이 비워졌습니다.": (None, "User rules cleared.", "用户工作准则已清空。", "ユーザー作業指針をクリアしました。"),
    "모든 작업에 적용할 지침 (여러 개는 ; 로 구분)": (None, "Rules applied to every task (separate with ;)", "适用于所有任务的准则 (多条用 ; 分隔)", "すべての作業に適用する指針 (複数は ; で区切る)"),
    "예) 베벨은 2단계; 베벨 면에 검은색 버텍스 컬러 적용": (None, "e.g. Bevel with 2 segments; black vertex color on bevel faces", "例) 倒角 2 段; 倒角面应用黑色顶点色", "例) ベベルは2段階; ベベル面に黒い頂点カラーを適用"),
    "LAN IP를 찾지 못했습니다. 네트워크 연결을 확인하세요.": (None, "Could not find a LAN IP. Check your network connection.", "未找到局域网 IP。请检查网络连接。", "LAN の IP が見つかりません。ネットワーク接続を確認してください。"),
    "복사됨: Termux에 붙여넣기 ({}:{})": (None, "Copied: paste it in Termux ({}:{})", "已复制: 请粘贴到 Termux ({}:{})", "コピーしました: Termux に貼り付けてください ({}:{})"),
    "토큰이 재발급되었습니다. Termux에서 설치 명령을 다시 실행하세요.": (None, "Token regenerated. Run the install command in Termux again.", "令牌已重新生成。请在 Termux 中重新运行安装命令。", "トークンを再発行しました。Termux でインストールコマンドを再実行してください。"),
    "작업 큐를 개시했습니다.": (None, "Task queue started.", "任务队列已开始。", "タスクキューを開始しました。"),
    "큐에 등록할 프롬프트 또는 이미지를 입력하세요.": (None, "Enter a prompt or image to queue.", "请输入要加入队列的提示词或图片。", "キューに登録するプロンプトまたは画像を入力してください。"),
    "작업 '{}'(이)가 큐에 등록되었습니다.": (None, "Task '{}' was queued.", "任务 '{}' 已加入队列。", "タスク '{}' をキューに登録しました。"),
    "큐 작업이 삭제되었습니다.": (None, "Queued task deleted.", "队列任务已删除。", "キューのタスクを削除しました。"),
    "작업 '{}'(이)가 수정되었습니다.": (None, "Task '{}' was updated.", "任务 '{}' 已修改。", "タスク '{}' を修正しました。"),
    "작업 제목": (None, "Task title", "任务标题", "タスクのタイトル"),
    "프롬프트 / 코드": (None, "Prompt / code", "提示词 / 代码", "プロンプト / コード"),
    "이미지 기반 큐 작업": (None, "Image-based queued task", "基于图片的队列任务", "画像ベースのキュータスク"),
    # ---- task status words ----
    "대기": (None, "Pending", "等待", "待機"),
    "완료": (None, "Done", "完成", "完了"),
    "실패": (None, "Failed", "失败", "失敗"),
    "취소": (None, "Cancelled", "已取消", "キャンセル"),
    # ---- English-source labels (translated to Korean/zh/ja) ----
    "MCP Chat & AI Console": ("MCP 채팅 & AI 콘솔", None, "MCP 聊天 & AI 控制台", "MCP チャット & AI コンソール"),
    "Task Queue & Auto-Save": ("작업 큐 & 자동 저장", None, "任务队列 & 自动保存", "タスクキュー & 自動保存"),
    "Engine": ("엔진", None, "引擎", "エンジン"),
    "Queue Worker: {}": ("큐 워커: {}", None, "队列工作进程: {}", "キューワーカー: {}"),
    "Server: Online (Port {})": ("서버: 온라인 (포트 {})", None, "服务器: 在线 (端口 {})", "サーバー: オンライン (ポート {})"),
    "Server: Offline": ("서버: 오프라인", None, "服务器: 离线", "サーバー: オフライン"),
    "Start Server": ("서버 시작", None, "启动服务器", "サーバー開始"),
    "Stop Server": ("서버 중지", None, "停止服务器", "サーバー停止"),
    "Open Web Chat UI": ("웹 채팅 UI 열기", None, "打开网页聊天界面", "Web チャット UI を開く"),
    "Server & Mobile Web UI": ("서버 & 모바일 웹 UI", None, "服务器 & 移动网页界面", "サーバー & モバイル Web UI"),
    "Claude Code & agy CLI": ("Claude Code & agy CLI", None, "Claude Code & agy CLI", "Claude Code & agy CLI"),
    "Termux / PC MCP Endpoint: http://127.0.0.1:<port>/mcp": (None, None, "Termux / PC MCP 端点: http://127.0.0.1:<port>/mcp", "Termux / PC MCP エンドポイント: http://127.0.0.1:<port>/mcp"),
    "Local Web Chat: http://127.0.0.1:<port>": (None, None, "本地网页聊天: http://127.0.0.1:<port>", "ローカル Web チャット: http://127.0.0.1:<port>"),
    "{}: 저장됨 (암호화)": (None, "{}: saved (encrypted)", "{}: 已保存 (加密)", "{}: 保存済み (暗号化)"),
    "API 키/토큰 보안 저장소: {}": (None, "API key/token secure storage: {}", "API 密钥/令牌安全存储: {}", "API キー/トークンのセキュア保存: {}"),
    "이 환경에는 시스템 암호화가 없어 키가 약하게만 보호됩니다 (openssl 설치 권장)": (None, "No system encryption is available here, so keys are only weakly protected (installing openssl is recommended)", "此环境没有系统加密，密钥仅受弱保护 (建议安装 openssl)", "この環境にはシステム暗号化がなく、キーは弱い保護のみです (openssl のインストール推奨)"),
    "키는 애드온 폴더 안에 암호화되어 저장되며, 애드온을 삭제하면 함께 삭제됩니다": (None, "Keys are stored encrypted inside the add-on folder and are deleted together with the add-on", "密钥加密保存在插件文件夹内，删除插件时会一并删除", "キーはアドオンフォルダ内に暗号化して保存され、アドオンを削除すると一緒に削除されます"),
    "모든 데이터 삭제 (대화/키/출력)": (None, "Delete all data (chats/keys/output)", "删除所有数据 (对话/密钥/输出)", "すべてのデータを削除 (会話/キー/出力)"),
    "저장된 키가 있습니다 (비워 두면 유지)": (None, "A key is already saved (leave empty to keep it)", "已有保存的密钥 (留空则保持不变)", "保存済みのキーがあります (空のままなら維持)"),
    "저장된 키가 삭제되었습니다.": (None, "Saved key deleted.", "已删除保存的密钥。", "保存されたキーを削除しました。"),
    "모든 데이터가 삭제되었습니다.": (None, "All data deleted.", "所有数据已删除。", "すべてのデータを削除しました。"),
    "삭제 실패: {}": (None, "Delete failed: {}", "删除失败: {}", "削除失敗: {}"),
    "버전: v{}  (GitHub Releases)": (None, "Version: v{}  (GitHub Releases)", "版本: v{}  (GitHub Releases)", "バージョン: v{}  (GitHub Releases)"),
    "업데이트 확인": (None, "Check for updates", "检查更新", "アップデートを確認"),
    "업데이트 설치": (None, "Install update", "安装更新", "アップデートをインストール"),
    "확인 중…": (None, "Checking…", "检查中…", "確認中…"),
    "설치 중…": (None, "Installing…", "安装中…", "インストール中…"),
    "새 버전 v{} 이(가) 있습니다": (None, "New version v{} is available", "有新版本 v{}", "新しいバージョン v{} があります"),
    "최신 버전입니다": (None, "You are up to date", "已是最新版本", "最新バージョンです"),
    "업데이트를 내려받는 중입니다.": (None, "Downloading the update…", "正在下载更新…", "アップデートをダウンロード中です…"),
    "게시된 릴리즈가 없습니다.": (None, "No release has been published.", "尚未发布任何版本。", "公開されたリリースがありません。"),
    "v{} 설치 완료. Blender를 재시작하세요.": (None, "v{} installed. Please restart Blender.", "v{} 安装完成。请重启 Blender。", "v{} のインストールが完了しました。Blender を再起動してください。"),
    "출처 / 참조": (None, "Credits / References", "来源 / 参考", "出典 / 参考"),
    "MCP (Model Context Protocol): Anthropic 공개 사양, 이 애드온에서 직접 구현": (None, "MCP (Model Context Protocol): Anthropic's open specification, implemented in this add-on", "MCP (Model Context Protocol): Anthropic 公开规范，由本插件自行实现", "MCP (Model Context Protocol): Anthropic の公開仕様。このアドオンで独自に実装"),
    "CLI: Claude Code (Anthropic) · Codex (OpenAI) · agy (Google)": (None, None, None, None),
    "MCP 사양": (None, "MCP spec", "MCP 规范", "MCP 仕様"),
    "전체 출처 (README)": (None, "Full credits (README)", "完整来源 (README)", "すべての出典 (README)"),
    "AI 실행 규칙 (Blender Execution Rules)": (None, "AI execution rules (Blender Execution Rules)", "AI 执行规则 (Blender Execution Rules)", "AI 実行ルール (Blender Execution Rules)"),
    "사용자 수정 규칙 사용 중": (None, "Using your edited rules", "正在使用自定义规则", "編集したルールを使用中"),
    "기본 규칙 사용 중": (None, "Using the default rules", "正在使用默认规则", "デフォルトのルールを使用中"),
    "규칙 편집": (None, "Edit rules", "编辑规则", "ルールを編集"),
    "편집 내용 저장": (None, "Save edits", "保存修改", "編集内容を保存"),
    "기본값 복원": (None, "Restore default", "恢复默认", "デフォルトに戻す"),
    "Text Editor에서 수정한 뒤 '편집 내용 저장'을 누르세요. AI에 그대로 전달되므로 영어 권장": (None, "Edit in the Text Editor, then press 'Save edits'. The text is sent to the AI as-is, so English is recommended", "在 Text Editor 中修改后点击“保存修改”。内容将原样发送给 AI，建议使用英文", "Text Editor で編集してから「編集内容を保存」を押してください。AI にそのまま送られるため英語を推奨"),
    "텍스트 창에서 규칙을 수정한 뒤 '편집 내용 저장'을 누르세요.": (None, "Edit the rules in the text editor, then press 'Save edits'.", "请在文本窗口中修改规则后点击“保存修改”。", "テキストエディターでルールを編集し、「編集内容を保存」を押してください。"),
    "먼저 '규칙 편집'을 눌러 규칙을 불러오세요.": (None, "Press 'Edit rules' first to load the rules.", "请先点击“编辑规则”载入规则。", "先に「ルールを編集」を押してルールを読み込んでください。"),
    "기본 규칙을 사용합니다.": (None, "Using the default rules.", "将使用默认规则。", "デフォルトのルールを使用します。"),
    "수정한 규칙이 저장되었습니다. 이후 모든 요청에 적용됩니다.": (None, "Your rules were saved and apply to all later requests.", "修改后的规则已保存，之后所有请求都会应用。", "編集したルールを保存しました。以降のすべてのリクエストに適用されます。"),
    "기본 규칙으로 복원했습니다.": (None, "Restored the default rules.", "已恢复默认规则。", "デフォルトのルールに戻しました。"),
    # ---- preferences: language ----
    "언어 / Language": (None, "Language", "语言 / Language", "言語 / Language"),
}

# ko/en/zh/ja column index
_COL = {"ko": 0, "en": 1, "zh": 2, "ja": 3}


def _build():
    exact = {lang: {} for lang in LANGS}
    patterns = {lang: [] for lang in LANGS}
    for src, vals in _T.items():
        for lang, idx in _COL.items():
            val = vals[idx] if vals[idx] is not None else src
            exact[lang][src] = val
            if "{}" in src:
                rx = "^" + re.escape(src).replace(re.escape("{}"), "(.+?)") + "$"
                patterns[lang].append((re.compile(rx, re.S), val))
    for lang in LANGS:
        patterns[lang].sort(key=lambda p: -len(p[0].pattern))
    return exact, patterns


_EXACT, _PATTERNS = _build()


def set_language(lang: str, blender_locale: str = ""):
    _state["lang"] = lang or "AUTO"
    if blender_locale:
        _state["blender_locale"] = blender_locale


def current_lang() -> str:
    lang = _state["lang"]
    if lang in LANGS:
        return lang
    loc = (_state["blender_locale"] or "").lower()
    if loc.startswith("ko"):
        return "ko"
    if loc.startswith("ja"):
        return "ja"
    if loc.startswith("zh"):
        return "zh"
    return "en" if loc.startswith("en") else "ko"


_cache = {}


def tr(text):
    """source 문자열을 현재 언어로 번역. 매칭되지 않으면 원문 그대로."""
    if not isinstance(text, str) or not text:
        return text
    lang = current_lang()
    key = (lang, text)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    out = _EXACT[lang].get(text)
    if out is None:
        for rx, val in _PATTERNS[lang]:
            m = rx.match(text)
            if m:
                out = val
                for g in m.groups():
                    out = out.replace("{}", g, 1)
                break
    if out is None:
        out = text
    if len(_cache) < 4000:
        _cache[key] = out
    return out
