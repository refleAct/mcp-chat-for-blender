/**
 * Blender MCP AI Assistant Frontend Logic
 * Touch & Mobile First, Multi-session, Vision Multimodal, Reasoning controls.
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentSessionId = null;
  let attachedImages = []; // base64 strings
  let isSending = false;
  let cachedSettings = {};

  // DOM Elements
  const sidebar = document.getElementById("sidebar");
  const sidebarBackdrop = document.getElementById("sidebar-backdrop");
  const toggleSidebarBtn = document.getElementById("toggle-sidebar-btn");
  const closeSidebarBtn = document.getElementById("close-sidebar-btn");
  const newChatBtn = document.getElementById("new-chat-btn");
  const sessionsList = document.getElementById("sessions-list");
  
  const currentSessionTitle = document.getElementById("current-session-title");
  const currentModelBadge = document.getElementById("current-model-badge");
  const currentReasoningBadge = document.getElementById("current-reasoning-badge");
  
  const messagesContainer = document.getElementById("messages-container");
  const welcomeCard = document.getElementById("welcome-card");
  const chatTextarea = document.getElementById("chat-textarea");
  const sendBtn = document.getElementById("send-btn");
  
  const imageFileInput = document.getElementById("image-file-input");
  const attachmentPreviewBar = document.getElementById("attachment-preview-bar");
  const btnAttachViewport = document.getElementById("btn-attach-viewport");
  const btnQuickViewport = document.getElementById("btn-quick-viewport");
  const btnQuickScene = document.getElementById("btn-quick-scene");
  
  // Settings Modal Elements
  const settingsModal = document.getElementById("settings-modal");
  const openSettingsBtn = document.getElementById("open-settings-btn");
  const closeSettingsBtn = document.getElementById("close-settings-btn");
  const cancelSettingsBtn = document.getElementById("cancel-settings-btn");
  const saveSettingsBtn = document.getElementById("save-settings-btn");
  const providerTabs = document.querySelectorAll(".tab-btn");
  const temperatureSlider = document.getElementById("cfg-temperature");
  const temperatureVal = document.getElementById("cfg-temperature-val");

  // ==========================================================================
  // Initialization
  // ==========================================================================
  async function init() {
    setupEventListeners();
    await loadSettings();
    await loadSessions();
  }

  // ==========================================================================
  // Event Listeners
  // ==========================================================================
  function setupEventListeners() {
    // Sidebar Toggle
    toggleSidebarBtn.addEventListener("click", () => {
      sidebar.classList.add("open");
      sidebarBackdrop.classList.add("active");
    });

    const closeSidebar = () => {
      sidebar.classList.remove("open");
      sidebarBackdrop.classList.remove("active");
    };

    closeSidebarBtn.addEventListener("click", closeSidebar);
    sidebarBackdrop.addEventListener("click", closeSidebar);

    // New Chat
    newChatBtn.addEventListener("click", async () => {
      closeSidebar();
      await createNewSession();
    });

    // Auto-resizing Textarea
    chatTextarea.addEventListener("input", () => {
      chatTextarea.style.height = "auto";
      chatTextarea.style.height = Math.min(chatTextarea.scrollHeight, 140) + "px";
    });

    // Enter to send (Shift+Enter for newline)
    chatTextarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    sendBtn.addEventListener("click", sendMessage);

    // Image Upload
    imageFileInput.addEventListener("change", handleFileUpload);
    btnAttachViewport.addEventListener("click", captureAndAttachViewport);
    btnQuickViewport.addEventListener("click", captureAndAttachViewport);
    btnQuickScene.addEventListener("click", querySceneInfo);

    // Quick Prompt Chips
    document.querySelectorAll(".quick-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const prompt = chip.getAttribute("data-prompt");
        chatTextarea.value = prompt;
        chatTextarea.focus();
        chatTextarea.dispatchEvent(new Event("input"));
      });
    });

    // Settings Modal
    openSettingsBtn.addEventListener("click", () => {
      closeSidebar();
      openSettings();
    });
    closeSettingsBtn.addEventListener("click", () => settingsModal.hidden = true);
    cancelSettingsBtn.addEventListener("click", () => settingsModal.hidden = true);
    saveSettingsBtn.addEventListener("click", saveSettings);

    // Provider Tabs
    providerTabs.forEach(tab => {
      tab.addEventListener("click", () => {
        providerTabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        switchProviderForm(tab.dataset.provider);
      });
    });

    // Temperature slider sync
    temperatureSlider.addEventListener("input", (e) => {
      temperatureVal.textContent = e.target.value;
    });
  }

  // ==========================================================================
  // Session Management
  // ==========================================================================
  async function loadSessions() {
    try {
      const res = await fetch("/api/sessions");
      const data = await res.json();
      const sessions = data.sessions || [];

      renderSessionsList(sessions);

      if (sessions.length > 0) {
        await switchSession(sessions[0].id);
      } else {
        await createNewSession();
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
    }
  }

  function renderSessionsList(sessions) {
    sessionsList.innerHTML = "";
    sessions.forEach(s => {
      const item = document.createElement("div");
      item.className = `session-item ${s.id === currentSessionId ? "active" : ""}`;
      item.innerHTML = `
        <span class="session-item-title">${escapeHtml(s.title || "새 대화")}</span>
        <button class="session-delete-btn" title="삭제">✕</button>
      `;

      item.addEventListener("click", (e) => {
        if (e.target.classList.contains("session-delete-btn")) {
          e.stopPropagation();
          deleteSession(s.id);
        } else {
          switchSession(s.id);
          sidebar.classList.remove("open");
          sidebarBackdrop.classList.remove("active");
        }
      });

      sessionsList.appendChild(item);
    });
  }

  async function createNewSession() {
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New Chat" })
      });
      const data = await res.json();
      if (data.session) {
        currentSessionId = data.session.id;
        await loadSessions();
      }
    } catch (err) {
      console.error("Error creating session:", err);
    }
  }

  async function switchSession(sessionId) {
    currentSessionId = sessionId;
    try {
      const res = await fetch(`/api/sessions/${sessionId}`);
      const data = await res.json();
      if (data.session) {
        renderCurrentSession(data.session);
        updateActiveSessionItemHighlight();
      }
    } catch (err) {
      console.error("Error loading session:", err);
    }
  }

  async function deleteSession(sessionId) {
    if (!confirm("이 대화 세션을 삭제하시겠습니까?")) return;
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
      await loadSessions();
    } catch (err) {
      console.error("Error deleting session:", err);
    }
  }

  function updateActiveSessionItemHighlight() {
    document.querySelectorAll(".session-item").forEach(item => {
      item.classList.remove("active");
    });
    // Rerender or mark active
    const activeEl = [...document.querySelectorAll(".session-item")].find(
      el => el.querySelector(".session-item-title")?.textContent === currentSessionTitle.textContent
    );
    if (activeEl) activeEl.classList.add("active");
  }

  function renderCurrentSession(session) {
    currentSessionTitle.textContent = session.title || "Blender AI Assistant";
    currentModelBadge.textContent = session.model_name || cachedSettings.openrouter_model || "claude-3.5-sonnet";
    
    const reasoning = session.reasoning_effort || cachedSettings.reasoning_effort || "medium";
    currentReasoningBadge.textContent = `Reasoning: ${reasoning.toUpperCase()}`;

    messagesContainer.innerHTML = "";

    if (!session.messages || session.messages.length === 0) {
      messagesContainer.appendChild(welcomeCard);
      welcomeCard.style.display = "block";
    } else {
      welcomeCard.style.display = "none";
      session.messages.forEach(msg => appendMessageUI(msg));
      scrollToBottom();
    }
  }

  // ==========================================================================
  // Chat Messaging UI & Logic
  // ==========================================================================
  async function sendMessage() {
    const text = chatTextarea.value.trim();
    if ((!text && attachedImages.length === 0) || isSending || !currentSessionId) return;

    isSending = true;
    sendBtn.disabled = true;

    const outgoingImages = [...attachedImages];
    // Clear input
    chatTextarea.value = "";
    chatTextarea.style.height = "auto";
    attachedImages = [];
    renderAttachmentPreviews();

    // Render optimistic user message
    welcomeCard.style.display = "none";
    appendMessageUI({
      role: "user",
      content: text,
      images: outgoingImages
    });
    scrollToBottom();

    // Show temporary thinking indicator
    const thinkingRow = document.createElement("div");
    thinkingRow.className = "message-row assistant";
    thinkingRow.id = "temp-thinking-indicator";
    thinkingRow.innerHTML = `
      <div class="message-bubble">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="animation: spin 1s linear infinite; display:inline-block;">⚡</span>
          <span>AI가 블렌더 도구를 호출하고 코드를 실행 중입니다...</span>
        </div>
      </div>
    `;
    messagesContainer.appendChild(thinkingRow);
    scrollToBottom();

    try {
      const res = await fetch(`/api/sessions/${currentSessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: text,
          images: outgoingImages
        })
      });

      const indicator = document.getElementById("temp-thinking-indicator");
      if (indicator) indicator.remove();

      const data = await res.json();
      if (data.reply) {
        appendMessageUI(data.reply);
        scrollToBottom();
      }

      if (data.session) {
        currentSessionTitle.textContent = data.session.title;
      }
      
      // Refresh session titles
      const listRes = await fetch("/api/sessions");
      const listData = await listRes.json();
      renderSessionsList(listData.sessions || []);
    } catch (err) {
      const indicator = document.getElementById("temp-thinking-indicator");
      if (indicator) indicator.remove();

      appendMessageUI({
        role: "assistant",
        content: `⚠️ 통신 중 오류가 발생했습니다: ${err.message}`
      });
      scrollToBottom();
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      chatTextarea.focus();
    }
  }

  function appendMessageUI(msg) {
    const row = document.createElement("div");
    row.className = `message-row ${msg.role}`;

    let bubbleContent = "";

    // 1. Attached / Captured Images
    if (msg.images && msg.images.length > 0) {
      bubbleContent += `<div class="message-images-grid">`;
      msg.images.forEach(imgUrl => {
        bubbleContent += `<img src="${imgUrl}" class="message-image-thumb" alt="첨부 이미지" onclick="window.open('${imgUrl}')">`;
      });
      bubbleContent += `</div>`;
    }

    // 2. Reasoning / Thinking Accordion
    if (msg.thought) {
      bubbleContent += `
        <div class="thought-card">
          <div class="thought-header" onclick="this.nextElementSibling.hidden = !this.nextElementSibling.hidden">
            <span>🧠 AI 심층 추론 과정 (Thinking)</span>
            <span>▼</span>
          </div>
          <div class="thought-content" hidden>${escapeHtml(msg.thought)}</div>
        </div>
      `;
    }

    // 3. Tool Execution Cards (Code execution & outputs)
    if (msg.tool_calls && msg.tool_calls.length > 0) {
      msg.tool_calls.forEach(tc => {
        const fnName = tc.name || "Tool";
        const argsStr = tc.arguments?.code || JSON.stringify(tc.arguments || {}, null, 2);
        const result = tc.result || {};
        let outputText = result.stdout || result.message || "";
        if (result.error) outputText += `\nError: ${result.error}`;

        bubbleContent += `
          <div class="tool-event-card">
            <div class="tool-event-header" onclick="this.nextElementSibling.hidden = !this.nextElementSibling.hidden">
              <span>🔧 Blender Tool: <b>${escapeHtml(fnName)}</b></span>
              <span>▼</span>
            </div>
            <div class="tool-event-body">
              <div class="tool-code-block">${escapeHtml(argsStr)}</div>
              ${outputText ? `<div class="tool-output-block">${escapeHtml(outputText)}</div>` : ''}
            </div>
          </div>
        `;
      });
    }

    // 4. Main Markdown / Text Content
    if (msg.content) {
      bubbleContent += `<div class="message-text">${formatMarkdownText(msg.content)}</div>`;
    }

    row.innerHTML = `<div class="message-bubble">${bubbleContent}</div>`;
    messagesContainer.appendChild(row);
  }

  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // ==========================================================================
  // Image & Viewport Attachment
  // ==========================================================================
  function handleFileUpload(e) {
    const files = Array.from(e.target.files);
    files.forEach(file => {
      const reader = new FileReader();
      reader.onload = (event) => {
        attachedImages.push(event.target.result);
        renderAttachmentPreviews();
      };
      reader.readAsDataURL(file);
    });
    imageFileInput.value = "";
  }

  async function captureAndAttachViewport() {
    btnAttachViewport.style.opacity = "0.5";
    try {
      const res = await fetch("/api/blender/viewport");
      const data = await res.json();
      if (data.image_base64) {
        attachedImages.push(data.image_base64);
        renderAttachmentPreviews();
      } else {
        alert("뷰포트 캡처 실패: " + (data.error || "알 수 없는 오류"));
      }
    } catch (err) {
      alert("뷰포트 캡처 요청 중 에러: " + err.message);
    } finally {
      btnAttachViewport.style.opacity = "1";
    }
  }

  function renderAttachmentPreviews() {
    attachmentPreviewBar.innerHTML = "";
    attachedImages.forEach((imgBase64, index) => {
      const thumb = document.createElement("div");
      thumb.className = "preview-thumb-box";
      thumb.innerHTML = `
        <img src="${imgBase64}">
        <button class="preview-remove-btn" data-index="${index}">✕</button>
      `;
      thumb.querySelector(".preview-remove-btn").addEventListener("click", () => {
        attachedImages.splice(index, 1);
        renderAttachmentPreviews();
      });
      attachmentPreviewBar.appendChild(thumb);
    });
  }

  async function querySceneInfo() {
    try {
      const res = await fetch("/api/blender/scene");
      const sceneData = await res.json();
      chatTextarea.value = `현재 블렌더 씬 정보입니다:\n\`\`\`json\n${JSON.stringify(sceneData, null, 2)}\n\`\`\`\n이 구성을 분석해줘.`;
      chatTextarea.focus();
      chatTextarea.dispatchEvent(new Event("input"));
    } catch (err) {
      alert("씬 정보 조회 실패: " + err.message);
    }
  }

  // ==========================================================================
  // Settings Management
  // ==========================================================================
  async function loadSettings() {
    try {
      const res = await fetch("/api/settings");
      const data = await res.json();
      cachedSettings = data.settings || {};
      populateSettingsForm(cachedSettings);
    } catch (err) {
      console.error("Failed to load settings:", err);
    }
  }

  function populateSettingsForm(s) {
    const activeProvider = s.active_provider || "openrouter";
    switchProviderForm(activeProvider);
    providerTabs.forEach(t => {
      t.classList.toggle("active", t.dataset.provider === activeProvider);
    });

    document.getElementById("cfg-openrouter-key").value = s.openrouter_api_key || "";
    document.getElementById("cfg-openrouter-model").value = s.openrouter_model || "anthropic/claude-3.5-sonnet";

    document.getElementById("cfg-nvidia-key").value = s.nvidia_nim_api_key || "";
    document.getElementById("cfg-nvidia-model").value = s.nvidia_nim_model || "meta/llama-3.3-70b-instruct";

    document.getElementById("cfg-local-url").value = s.local_base_url || "http://127.0.0.1:11434/v1";
    document.getElementById("cfg-local-model").value = s.local_model || "qwen2.5-coder:latest";

    document.getElementById("cfg-custom-url").value = s.custom_base_url || "";
    document.getElementById("cfg-custom-key").value = s.custom_api_key || "";
    document.getElementById("cfg-custom-model").value = s.custom_model || "";

    document.getElementById("cfg-reasoning-effort").value = s.reasoning_effort || "medium";
    document.getElementById("cfg-thinking-budget").value = s.thinking_budget || "2048";
    temperatureSlider.value = s.temperature || "0.7";
    temperatureVal.textContent = s.temperature || "0.7";
    document.getElementById("cfg-port").value = s.port || "8000";
  }

  function switchProviderForm(provider) {
    const forms = {
      openrouter: document.getElementById("form-openrouter"),
      nvidia_nim: document.getElementById("form-nvidia_nim"),
      local: document.getElementById("form-local"),
      custom: document.getElementById("form-custom")
    };

    Object.keys(forms).forEach(p => {
      if (forms[p]) forms[p].hidden = (p !== provider);
    });
  }

  function openSettings() {
    populateSettingsForm(cachedSettings);
    settingsModal.hidden = false;
  }

  async function saveSettings() {
    const activeTab = document.querySelector(".tab-btn.active");
    const activeProvider = activeTab ? activeTab.dataset.provider : "openrouter";

    const newSettings = {
      active_provider: activeProvider,
      openrouter_api_key: document.getElementById("cfg-openrouter-key").value.trim(),
      openrouter_model: document.getElementById("cfg-openrouter-model").value.trim(),
      nvidia_nim_api_key: document.getElementById("cfg-nvidia-key").value.trim(),
      nvidia_nim_model: document.getElementById("cfg-nvidia-model").value.trim(),
      local_base_url: document.getElementById("cfg-local-url").value.trim(),
      local_model: document.getElementById("cfg-local-model").value.trim(),
      custom_base_url: document.getElementById("cfg-custom-url").value.trim(),
      custom_api_key: document.getElementById("cfg-custom-key").value.trim(),
      custom_model: document.getElementById("cfg-custom-model").value.trim(),
      reasoning_effort: document.getElementById("cfg-reasoning-effort").value,
      thinking_budget: document.getElementById("cfg-thinking-budget").value,
      temperature: temperatureSlider.value,
      port: document.getElementById("cfg-port").value
    };

    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSettings)
      });
      const data = await res.json();
      cachedSettings = data.settings || newSettings;
      
      // Update header badges
      currentReasoningBadge.textContent = `Reasoning: ${newSettings.reasoning_effort.toUpperCase()}`;
      settingsModal.hidden = true;
    } catch (err) {
      alert("설정 저장 실패: " + err.message);
    }
  }

  // ==========================================================================
  // Markdown & Escaping Helpers
  // ==========================================================================
  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMarkdownText(text) {
    if (!text) return "";
    let safe = escapeHtml(text);

    // Code blocks ```python ... ```
    safe = safe.replace(/```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
    });

    // Inline code `...`
    safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold **...**
    safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Newlines to <br> (outside pre)
    safe = safe.split(/(<pre>[\s\S]*?<\/pre>)/g).map((chunk, i) => {
      if (i % 2 === 1) return chunk; // inside pre
      return chunk.replace(/\n/g, '<br>');
    }).join("");

    return safe;
  }

  // Run init
  init();
});
