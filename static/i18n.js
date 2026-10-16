/**
 * Web UI translation (English is the default / source language; ko / zh / ja are translations).
 *
 * The HTML and app.js are written in English. This file:
 *   - holds the translation table (English source -> ko / zh / ja),
 *   - translates text nodes and placeholder/title/aria-label/alt attributes automatically
 *     (also for nodes added later by app.js, via a MutationObserver),
 *   - exposes t(text) and tf(text, ...values) for strings built in JS,
 *   - wraps alert/confirm/prompt so dialog messages are translated too.
 * Strings containing "{}" are matched as patterns. Unknown text is left as written.
 * The language is stored in localStorage ("mcp_lang"); the default is English.
 */
(function () {
  "use strict";

  const LANGS = ["en", "ko", "zh", "ja"];
  const LABELS = { en: "English", ko: "한국어", zh: "中文", ja: "日本語" };

  // English source : [ko, zh, ja]
  const T = {
  "Close sidebar": [
    "사이드바 닫기",
    "关闭侧边栏",
    "サイドバーを閉じる"
  ],
  "New chat session": [
    "새 채팅 세션",
    "新建聊天会话",
    "新しいチャットセッション"
  ],
  "Recent chat sessions": [
    "최근 대화 세션",
    "最近的聊天会话",
    "最近のチャットセッション"
  ],
  "Model & AI settings": [
    "모델 & AI 설정",
    "模型和 AI 设置",
    "モデルと AI 設定"
  ],
  "Open menu": [
    "메뉴 열기",
    "打开菜单",
    "メニューを開く"
  ],
  "Rename session": [
    "세션 이름 변경",
    "重命名会话",
    "セッション名を変更"
  ],
  "Capture Blender screen": [
    "블렌더 화면 캡처",
    "捕获 Blender 画面",
    "Blender 画面をキャプチャ"
  ],
  "Viewport capture": [
    "뷰포트 캡처",
    "视口截图",
    "ビューポートキャプチャ"
  ],
  "Get current scene info": [
    "현재 씬 정보 조회",
    "查询当前场景信息",
    "現在のシーン情報を取得"
  ],
  "Scene info": [
    "씬 정보",
    "场景信息",
    "シーン情報"
  ],
  "Add a new session tab": [
    "새 세션 탭 추가",
    "添加新的会话标签页",
    "新しいセッションタブを追加"
  ],
  "＋ New tab": [
    "＋ 새 탭",
    "＋ 新标签页",
    "＋ 新規タブ"
  ],
  "Android Blender AI assistant": [
    "안드로이드 블렌더 AI 어시스턴트",
    "Android Blender AI 助手",
    "Android Blender AI アシスタント"
  ],
  "Enter a prompt and the AI writes Python scripts to create and edit the Blender 3D scene.": [
    "프롬프트를 입력하면 AI가 직접 파이썬 스크립트를 작성하여 블렌더 3D 씬을 생성하고 조작합니다.",
    "输入提示词后，AI 会编写 Python 脚本来创建和操作 Blender 3D 场景。",
    "プロンプトを入力すると、AI が Python スクリプトを書いて Blender の 3D シーンを作成・操作します。"
  ],
  "🏙️ Create a cyberpunk neon cube": [
    "🏙️ 사이버펑크 네온 큐브 생성",
    "🏙️ 创建赛博朋克霓虹立方体",
    "🏙️ サイバーパンクのネオンキューブを作成"
  ],
  "📊 Analyze and summarize the scene": [
    "📊 씬 분석 및 요약",
    "📊 分析并总结场景",
    "📊 シーンの分析と要約"
  ],
  "🌲 Create low-poly forest terrain": [
    "🌲 저폴리곤 숲 지형 생성",
    "🌲 创建低多边形森林地形",
    "🌲 ローポリの森の地形を作成"
  ],
  "📸 Capture the viewport and review the composition": [
    "📸 뷰포트 캡처 및 구도 평가",
    "📸 截取视口并评估构图",
    "📸 ビューポートをキャプチャして構図を評価"
  ],
  "Chat and run directly": [
    "일반 대화 및 직접 실행",
    "普通对话并直接执行",
    "通常の会話と直接実行"
  ],
  "Make a plan first": [
    "사전 작업 계획 수립",
    "先制定工作计划",
    "先に作業計画を立てる"
  ],
  "Plan, then run the task queue automatically in order": [
    "계획 수립 후 작업큐 자동 순차 실행",
    "制定计划后按顺序自动执行任务队列",
    "計画を立てた後、タスクキューを順番に自動実行"
  ],
  "Click to manage the task queue": [
    "클릭하여 작업큐 관리",
    "点击管理任务队列",
    "クリックしてタスクキューを管理"
  ],
  "Pause/resume": [
    "일시정지/재개",
    "暂停/继续",
    "一時停止/再開"
  ],
  "Clear queue": [
    "큐 비우기",
    "清空队列",
    "キューをクリア"
  ],
  "Attach image/photo": [
    "이미지/사진 첨부",
    "附加图片/照片",
    "画像/写真を添付"
  ],
  "Capture the current 3D viewport and attach it": [
    "현재 3D 뷰포트 캡처 후 첨부",
    "截取当前 3D 视口并附加",
    "現在の 3D ビューポートをキャプチャして添付"
  ],
  "Enter what you want Blender to do... (e.g. add a chrome sphere and a red light)": [
    "블렌더에 요청할 작업을 입력하세요... (예: 크롬 구체와 붉은 조명 추가)",
    "请输入要让 Blender 执行的操作...（例：添加铬球和红色灯光）",
    "Blender に依頼する作業を入力してください...（例：クロームの球と赤いライトを追加）"
  ],
  "Send message": [
    "메시지 전송",
    "发送消息",
    "メッセージを送信"
  ],
  "💡 You can attach photos from the mobile camera/gallery · Termux Claude Code / agy CLI (MCP) supported": [
    "💡 모바일 카메라/갤러리 사진 첨부 가능 · Termux Claude Code / agy CLI (MCP) 연동 지원",
    "💡 可附加手机相机/相册的照片 · 支持 Termux Claude Code / agy CLI (MCP)",
    "💡 モバイルのカメラ/ギャラリーの写真を添付できます · Termux Claude Code / agy CLI (MCP) 連携に対応"
  ],
  "AI model and endpoint settings": [
    "AI 모델 및 엔드포인트 설정",
    "AI 模型和端点设置",
    "AI モデルとエンドポイントの設定"
  ],
  "API keys are optional. If left empty, requests are handled automatically by the Claude Code CLI installed on the PC (or Codex/agy if it is missing).": [
    "API 키는 선택 사항입니다. 비워 두면 PC에 설치된 Claude Code CLI(없으면 Codex/agy)로 자동 처리됩니다.",
    "API 密钥是可选的。留空时会自动使用 PC 上安装的 Claude Code CLI（没有则使用 Codex/agy）处理。",
    "API キーは任意です。空欄の場合は、PC にインストールされた Claude Code CLI（なければ Codex/agy）で自動的に処理されます。"
  ],
  "(optional)": [
    "(선택)",
    "（可选）",
    "（任意）"
  ],
  "Recommended: anthropic/claude-3.5-sonnet, openai/gpt-4o, deepseek/deepseek-r1": [
    "추천: anthropic/claude-3.5-sonnet, openai/gpt-4o, deepseek/deepseek-r1",
    "推荐：anthropic/claude-3.5-sonnet、openai/gpt-4o、deepseek/deepseek-r1",
    "推奨：anthropic/claude-3.5-sonnet、openai/gpt-4o、deepseek/deepseek-r1"
  ],
  "Recommended: meta/llama-3.3-70b-instruct, nvidia/llama-3.1-nemotron-70b-instruct": [
    "추천: meta/llama-3.3-70b-instruct, nvidia/llama-3.1-nemotron-70b-instruct",
    "推荐：meta/llama-3.3-70b-instruct、nvidia/llama-3.1-nemotron-70b-instruct",
    "推奨：meta/llama-3.3-70b-instruct、nvidia/llama-3.1-nemotron-70b-instruct"
  ],
  "Address of Ollama, LM Studio or vLLM inside Termux or on the same Wi-Fi": [
    "Termux 내부 또는 동일 Wi-Fi의 Ollama, LM Studio, vLLM 주소",
    "Termux 内部或同一 Wi-Fi 下的 Ollama、LM Studio、vLLM 地址",
    "Termux 内または同じ Wi-Fi 上の Ollama、LM Studio、vLLM のアドレス"
  ],
  "(optional · blank = default)": [
    "(선택 · 비우면 기본값)",
    "（可选 · 留空则使用默认值）",
    "（任意 · 空欄なら既定値）"
  ],
  "(optional · blank = gpt-4o)": [
    "(선택 · 비우면 gpt-4o)",
    "（可选 · 留空则为 gpt-4o）",
    "（任意 · 空欄なら gpt-4o）"
  ],
  "Reasoning effort": [
    "추론 강도 (Reasoning)",
    "推理强度 (Reasoning)",
    "推論の強さ (Reasoning)"
  ],
  "Off (default)": [
    "사용 안 함 (기본)",
    "不使用（默认）",
    "使用しない（既定）"
  ],
  "Low (fast reasoning)": [
    "Low (빠른 추론)",
    "Low（快速推理）",
    "Low（高速な推論）"
  ],
  "Medium (balanced)": [
    "Medium (균형)",
    "Medium（均衡）",
    "Medium（バランス）"
  ],
  "High (deep reasoning)": [
    "High (심층 추론)",
    "High（深度推理）",
    "High（深い推論）"
  ],
  "Applies to o1, o3-mini, DeepSeek R1, etc.": [
    "o1, o3-mini, DeepSeek R1 등에 적용",
    "适用于 o1、o3-mini、DeepSeek R1 等",
    "o1、o3-mini、DeepSeek R1 などに適用"
  ],
  "Claude thinking tokens": [
    "Claude Thinking 토큰",
    "Claude Thinking 令牌",
    "Claude Thinking トークン"
  ],
  "Extended thinking budget for Claude 3.7 Sonnet": [
    "Claude 3.7 Sonnet 확장 사고 예산",
    "Claude 3.7 Sonnet 扩展思考预算",
    "Claude 3.7 Sonnet の拡張思考の予算"
  ],
  "Temperature (creativity)": [
    "Temperature (창의성)",
    "Temperature（创造性）",
    "Temperature（創造性）"
  ],
  "Global queue delay (s)": [
    "작업큐 전역 딜레이 (초)",
    "任务队列全局延迟（秒）",
    "タスクキューのグローバル遅延（秒）"
  ],
  "Wait time between consecutive tasks (prevents overheating)": [
    "연속 작업 사이 대기시간 (발열 방지)",
    "连续任务之间的等待时间（防止发热）",
    "連続するタスク間の待機時間（発熱防止）"
  ],
  "Server port": [
    "서버 포트",
    "服务器端口",
    "サーバーポート"
  ],
  "Auto-save options": [
    "자동 저장 옵션 (Auto-Save)",
    "自动保存选项 (Auto-Save)",
    "自動保存オプション (Auto-Save)"
  ],
  "Auto-save .blend snapshot": [
    ".blend 스냅샷 자동 저장",
    "自动保存 .blend 快照",
    ".blend スナップショットを自動保存"
  ],
  "Auto-save render image": [
    "렌더 이미지 자동 저장",
    "自动保存渲染图片",
    "レンダー画像を自動保存"
  ],
  "Cancel": [
    "취소",
    "取消",
    "キャンセル"
  ],
  "Save settings": [
    "설정 저장",
    "保存设置",
    "設定を保存"
  ],
  "Plan mode: enter the goal you want a 3D modeling/scene plan for...": [
    "플랜 모드: 3D 모델링/씬 제작 계획을 수립할 목표를 입력하세요...",
    "计划模式：请输入想要制定 3D 建模/场景制作计划的目标...",
    "プランモード：3D モデリング/シーン制作の計画を立てたい目標を入力してください..."
  ],
  "Auto mode: after the plan is generated it is queued automatically, then run and saved in order...": [
    "오토 모드: 계획 생성 후 작업큐에 자동 등록되어 순차 실행 및 저장됩니다...",
    "自动模式：生成计划后会自动加入任务队列，并依次执行和保存...",
    "オートモード：計画を生成した後、自動的にタスクキューに登録され、順に実行・保存されます..."
  ],
  "Delete all queued tasks?": [
    "대기열 작업을 모두 삭제하시겠습니까?",
    "要删除所有排队的任务吗？",
    "キューのタスクをすべて削除しますか？"
  ],
  "Rename": [
    "이름 변경",
    "重命名",
    "名前を変更"
  ],
  "Delete": [
    "삭제",
    "删除",
    "削除"
  ],
  "New chat": [
    "새 대화",
    "新对话",
    "新しい会話"
  ],
  "Enter a new session name:": [
    "새 세션 이름을 입력하세요:",
    "请输入新的会话名称：",
    "新しいセッション名を入力してください:"
  ],
  "Failed to rename the session: {}": [
    "세션 이름 변경 실패: {}",
    "重命名会话失败：{}",
    "セッション名の変更に失敗しました: {}"
  ],
  "Delete this chat session?": [
    "이 대화 세션을 삭제하시겠습니까?",
    "要删除此聊天会话吗？",
    "このチャットセッションを削除しますか？"
  ],
  "The AI is calling Blender tools and running code...": [
    "AI가 블렌더 도구를 호출하고 코드를 실행 중입니다...",
    "AI 正在调用 Blender 工具并执行代码...",
    "AI が Blender のツールを呼び出してコードを実行中です..."
  ],
  "The AI is building a step-by-step 3D plan...": [
    "AI가 단계별 3D 제작 계획(Plan)을 수립 중입니다...",
    "AI 正在制定分步 3D 制作计划...",
    "AI が段階的な 3D 制作計画（Plan）を作成中です..."
  ],
  "The AI is planning and starting the task queue automatically...": [
    "AI가 계획 수립 후 작업큐를 자동 가동 중입니다...",
    "AI 正在制定计划并自动启动任务队列...",
    "AI が計画を立てた後、タスクキューを自動で開始しています..."
  ],
  "Work plan": [
    "작업 계획서",
    "工作计划书",
    "作業計画書"
  ],
  "Plan generation failed": [
    "플랜 생성 실패",
    "生成计划失败",
    "プランの生成に失敗しました"
  ],
  "Failed to start Auto mode": [
    "오토 모드 시작 실패",
    "启动自动模式失败",
    "オートモードの開始に失敗しました"
  ],
  "⚡ **Auto Mode started**": [
    "⚡ **Auto Mode 가동 시작**",
    "⚡ **自动模式已启动**",
    "⚡ **オートモード開始**"
  ],
  "Your instruction was queued as **1 task**. Planning and step execution run in order inside this task, and a .blend snapshot and render image are saved automatically when it finishes.": [
    "지시가 작업큐 **1건**으로 등록되었습니다. 계획 수립과 단계 실행은 이 작업 안에서 순차 처리되며, 완료 시 .blend 스냅샷과 렌더 이미지가 자동 저장됩니다.",
    "指令已作为 **1 个任务**加入队列。计划制定和步骤执行将在该任务内依次处理，完成后会自动保存 .blend 快照和渲染图片。",
    "指示を**1件**のタスクとしてキューに登録しました。計画の作成とステップの実行はこのタスク内で順に処理され、完了すると .blend スナップショットとレンダー画像が自動保存されます。"
  ],
  "⚠️ A communication error occurred: {}": [
    "⚠️ 통신 중 오류가 발생했습니다: {}",
    "⚠️ 通信时发生错误：{}",
    "⚠️ 通信中にエラーが発生しました: {}"
  ],
  "Attached image": [
    "첨부 이미지",
    "附加图片",
    "添付画像"
  ],
  "🧠 AI deep reasoning (Thinking)": [
    "🧠 AI 심층 추론 과정 (Thinking)",
    "🧠 AI 深度推理过程 (Thinking)",
    "🧠 AI の深い推論過程 (Thinking)"
  ],
  "Viewport capture failed: {}": [
    "뷰포트 캡처 실패: {}",
    "视口截图失败：{}",
    "ビューポートのキャプチャに失敗しました: {}"
  ],
  "Unknown error": [
    "알 수 없는 오류",
    "未知错误",
    "不明なエラー"
  ],
  "Error while requesting a viewport capture: {}": [
    "뷰포트 캡처 요청 중 에러: {}",
    "请求视口截图时出错：{}",
    "ビューポートのキャプチャ要求中にエラー: {}"
  ],
  "Failed to get scene info: {}": [
    "씬 정보 조회 실패: {}",
    "查询场景信息失败：{}",
    "シーン情報の取得に失敗しました: {}"
  ],
  "Failed to save settings: {}": [
    "설정 저장 실패: {}",
    "保存设置失败：{}",
    "設定の保存に失敗しました: {}"
  ],
  "This is the current Blender scene:": [
    "현재 블렌더 씬 정보입니다:",
    "这是当前的 Blender 场景信息：",
    "現在の Blender シーン情報です:"
  ],
  "Analyze this setup.": [
    "이 구성을 분석해줘.",
    "请分析这个构成。",
    "この構成を分析してください。"
  ]
  ,"Create a simple cyberpunk neon cube with a lighting set": ["간단한 사이버펑크 네온 큐브와 조명 세트를 만들어줘", "创建一个带灯光组的简单赛博朋克霓虹立方体", "シンプルなサイバーパンクのネオンキューブとライトセットを作って"]
  ,"List all objects and material info in the current scene and analyze it": ["현재 씬의 모든 오브젝트 목록과 재질 정보를 분석해줘", "列出当前场景中所有对象和材质信息并进行分析", "現在のシーンのすべてのオブジェクトとマテリアル情報を一覧にして分析して"]
  ,"Create low-poly pine trees and terrain on the ground": ["저폴리곤(Low-poly) 소나무와 지형을 바닥에 생성해줘", "在地面上创建低多边形松树和地形", "地面にローポリの松の木と地形を作成して"]
  ,"Capture the current viewport and review the composition": ["현재 뷰포트 화면을 캡처해서 구도를 평가해줘", "截取当前视口画面并评估构图", "現在のビューポート画面をキャプチャして構図を評価して"]
};

  const IDX = { ko: 0, zh: 1, ja: 2 };
  const exact = { ko: {}, zh: {}, ja: {} };
  const patterns = { ko: [], zh: [], ja: [] };
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  Object.keys(T).forEach((src) => {
    ["ko", "zh", "ja"].forEach((lang) => {
      const val = T[src][IDX[lang]];
      exact[lang][src] = val;
      if (src.indexOf("{}") >= 0) {
        patterns[lang].push([new RegExp("^" + esc(src).replace(/\\\{\\\}/g, "([\\s\\S]+?)") + "$"), val]);
      }
    });
  });
  ["ko", "zh", "ja"].forEach((l) => patterns[l].sort((a, b) => b[0].source.length - a[0].source.length));

  function detect() {
    try {
      const saved = localStorage.getItem("mcp_lang");
      if (saved && LANGS.indexOf(saved) >= 0) return saved;
    } catch (e) { /* storage may be blocked */ }
    return "en";   // default language
  }

  let lang = detect();

  /** Translate an English source string into the current language (unknown text is returned unchanged). */
  function t(text) {
    if (lang === "en" || typeof text !== "string" || !text) return text;
    const trimmed = text.trim();
    if (!trimmed) return text;
    let out = exact[lang][trimmed];
    if (out === undefined) {
      for (const [rx, val] of patterns[lang]) {
        const m = trimmed.match(rx);
        if (m) {
          out = val;
          for (let i = 1; i < m.length; i++) out = out.replace("{}", () => m[i]);
          break;
        }
      }
    }
    if (out === undefined) return text;
    const lead = text.match(/^\s*/)[0];
    const tail = text.match(/\s*$/)[0];
    return lead + out + tail;
  }

  /** t() followed by filling "{}" placeholders with the given values. */
  function tf(text, ...values) {
    let out = t(text);
    values.forEach((v) => { out = out.replace("{}", () => v); });
    return out;
  }

  // ---- DOM translation (originals are remembered so switching languages works in both directions) ----
  const textState = new WeakMap();   // text node -> { orig, shown }
  const attrState = new WeakMap();   // element   -> { attr: { orig, shown } }
  const ATTRS = ["placeholder", "title", "aria-label", "alt"];
  let busy = false;

  function translateTextNode(node) {
    const st = textState.get(node);
    const orig = st && node.data === st.shown ? st.orig : node.data;   // still our output, or new/changed by app.js
    const shown = t(orig);
    if (!st && shown === orig) return;
    textState.set(node, { orig, shown });
    if (node.data !== shown) node.data = shown;
  }

  function translateAttrs(el) {
    if (!el.hasAttribute) return;
    let st = attrState.get(el);
    ATTRS.forEach((a) => {
      if (!el.hasAttribute(a)) return;
      const cur = el.getAttribute(a);
      const rec = st && st[a];
      const orig = rec && cur === rec.shown ? rec.orig : cur;
      const shown = t(orig);
      if (!rec && shown === orig) return;
      if (!st) { st = {}; attrState.set(el, st); }
      st[a] = { orig, shown };
      if (cur !== shown) el.setAttribute(a, shown);
    });
  }

  function translateTree(root) {
    if (!root) return;
    busy = true;
    try {
      if (root.nodeType === Node.TEXT_NODE) { translateTextNode(root); return; }
      if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;
      if (root.nodeType === Node.ELEMENT_NODE) translateAttrs(root);
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
      let n;
      while ((n = walker.nextNode())) {
        if (n.nodeType === Node.TEXT_NODE) {
          const p = n.parentNode && n.parentNode.nodeName;
          if (p === "SCRIPT" || p === "STYLE" || p === "TEXTAREA") continue;
          translateTextNode(n);
        } else {
          translateAttrs(n);
        }
      }
    } finally {
      busy = false;
    }
  }

  const observer = new MutationObserver((mutations) => {
    if (busy || lang === "en") return;
    mutations.forEach((m) => {
      if (m.type === "childList") m.addedNodes.forEach((n) => translateTree(n));
      else if (m.type === "characterData") translateTree(m.target);
      else if (m.type === "attributes") translateAttrs(m.target);
    });
  });

  function setLang(next) {
    if (LANGS.indexOf(next) < 0) return;
    lang = next;
    try { localStorage.setItem("mcp_lang", next); } catch (e) { /* ignore */ }
    document.documentElement.lang = next;
    translateTree(document.body);
    const sel = document.getElementById("lang-select");
    if (sel && sel.value !== next) sel.value = next;
  }

  // ---- dialogs ----
  const nativeAlert = window.alert.bind(window);
  const nativeConfirm = window.confirm.bind(window);
  const nativePrompt = window.prompt.bind(window);
  window.alert = (msg) => nativeAlert(t(String(msg)));
  window.confirm = (msg) => nativeConfirm(t(String(msg)));
  window.prompt = (msg, def) => nativePrompt(t(String(msg)), def);

  function buildSelector() {
    const footer = document.querySelector(".sidebar-footer");
    if (!footer || document.getElementById("lang-select")) return;
    const sel = document.createElement("select");
    sel.id = "lang-select";
    sel.className = "form-input";
    sel.setAttribute("aria-label", "Language");
    sel.style.cssText = "margin-top:8px;width:100%";
    LANGS.forEach((l) => {
      const o = document.createElement("option");
      o.value = l;
      o.textContent = LABELS[l];
      sel.appendChild(o);
    });
    sel.value = lang;
    sel.addEventListener("change", () => setLang(sel.value));
    footer.appendChild(sel);
  }

  window.t = t;
  window.tf = tf;
  window.mcpI18n = { setLang, getLang: () => lang, translateTree };

  function init() {
    document.documentElement.lang = lang;
    buildSelector();
    translateTree(document.body);
    observer.observe(document.body, {
      childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ATTRS,
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
