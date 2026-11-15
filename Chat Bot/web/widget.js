/**
 * AstroChat Web Component (<astro-chat>)
 * Framework-Free Drop-in Chat Widget for NASA Space Apps Challenge 2026.
 *
 * Supported Modes:
 * - floating: Round launcher button fixed in corner; opens a popup chat panel (open/close/minimize,
 *             unread badge, remembers open/closed state for page session, never covers vital controls).
 * - tab: Fills container 100% (ideal for embedding inside dashboard tabs), no launcher.
 * - inline: Normal box in page flow (max-width: 480px), no launcher.
 *
 * Supported Attributes:
 * - mode="floating" | "tab" | "inline" (default: "inline")
 * - api-base: Base URL of backend (default: same origin "")
 * - astronaut-id: Astronaut ID (default: 1)
 * - mission-day: Mission Day number (default: 42)
 * - language="ar" | "en" | "auto" (default: "auto")
 * - theme="auto" | "dark" | "light" (default: "auto")
 *
 * Host-Page Event Bridge:
 * - Listens for: 'astro:task', 'astro:context', 'astro:signals-summary'
 * - Dispatches: 'astro:session', 'astro:question', 'astro:message', 'astro:session-ended', 'astro:escalate'
 * - Exposes: window.AstroChat API (open, close, startSession, endSession, sendSystemNote, getSessionId, setContext)
 */

(function () {
  let activeWidgetInstance = null;

  const template = document.createElement("template");
  template.innerHTML = `
    <style>
      :host {
        display: block;
        box-sizing: border-box;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        
        /* Futuristic Medical HUD Color Palette */
        --astro-bg: #070d1a;
        --astro-panel: rgba(14, 23, 42, 0.92);
        --astro-panel-border: rgba(0, 240, 255, 0.28);
        --astro-accent: #00f0ff;
        --astro-accent-hover: #38bdf8;
        --astro-accent-dim: rgba(0, 240, 255, 0.12);
        --astro-text: #f8fafc;
        --astro-text-muted: #94a3b8;
        --astro-header-bg: rgba(15, 23, 42, 0.98);
        --astro-user-bubble: linear-gradient(135deg, #0284c7, #0099cc);
        --astro-asst-bubble: rgba(30, 41, 59, 0.92);
        --astro-glow: 0 0 16px rgba(0, 240, 255, 0.25);
        --astro-danger: #ef4444;
        --astro-warning: #f59e0b;
        --astro-success: #10b981;
      }

      :host([theme="light"]) {
        --astro-bg: #f1f5f9;
        --astro-panel: rgba(255, 255, 255, 0.96);
        --astro-panel-border: rgba(2, 132, 199, 0.35);
        --astro-accent: #0284c7;
        --astro-accent-hover: #0369a1;
        --astro-accent-dim: rgba(2, 132, 199, 0.12);
        --astro-text: #0f172a;
        --astro-text-muted: #64748b;
        --astro-header-bg: #f8fafc;
        --astro-user-bubble: linear-gradient(135deg, #0284c7, #0369a1);
        --astro-asst-bubble: #e2e8f0;
        --astro-glow: 0 0 12px rgba(2, 132, 199, 0.18);
      }

      *, *::before, *::after {
        box-sizing: border-box;
      }

      /* ---------------------------------------------------- */
      /* Base Container Layout */
      /* ---------------------------------------------------- */
      .astro-container {
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 100%;
        background: var(--astro-bg);
        border: 1px solid var(--astro-panel-border);
        border-radius: 16px;
        overflow: hidden;
        box-shadow: var(--astro-glow), 0 12px 36px rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        color: var(--astro-text);
        position: relative;
      }

      /* RTL Support */
      .astro-container.rtl {
        direction: rtl;
        text-align: right;
      }

      /* ---------------------------------------------------- */
      /* Modes */
      /* ---------------------------------------------------- */

      /* TAB MODE: Fills parent container completely */
      :host([mode="tab"]) {
        width: 100%;
        height: 100%;
        min-height: 0;
      }
      :host([mode="tab"]) .astro-container {
        border-radius: 0;
        box-shadow: none;
        border: none;
      }
      :host([mode="tab"]) .astro-launcher {
        display: none !important;
      }
      :host([mode="tab"]) .astro-floating-wrapper {
        position: static !important;
        width: 100% !important;
        height: 100% !important;
        display: flex !important;
      }
      :host([mode="tab"]) .astro-window-controls {
        display: none !important;
      }

      /* INLINE MODE: Box in document flow */
      :host([mode="inline"]) {
        width: 100%;
        max-width: 480px;
        height: 620px;
        margin: 0 auto;
      }
      :host([mode="inline"]) .astro-launcher {
        display: none !important;
      }
      :host([mode="inline"]) .astro-floating-wrapper {
        position: static !important;
        width: 100% !important;
        height: 100% !important;
        display: flex !important;
      }
      :host([mode="inline"]) .astro-window-controls {
        display: none !important;
      }

      /* FLOATING MODE: Launcher button + popup window */
      :host([mode="floating"]), :host(:not([mode])) {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 99999;
      }
      :host([mode="floating"].rtl), :host(:not([mode]).rtl) {
        right: auto;
        left: 24px;
      }

      .astro-launcher {
        width: 58px;
        height: 58px;
        border-radius: 50%;
        background: var(--astro-panel);
        border: 2px solid var(--astro-accent);
        box-shadow: var(--astro-glow), 0 8px 24px rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 26px;
        cursor: pointer;
        outline: none;
        position: relative;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
      }
      .astro-launcher:hover {
        transform: scale(1.08);
        box-shadow: 0 0 20px var(--astro-accent), 0 10px 28px rgba(0, 0, 0, 0.6);
      }
      .astro-launcher:focus-visible {
        outline: 3px solid var(--astro-accent);
        outline-offset: 3px;
      }

      .astro-unread-badge {
        position: absolute;
        top: -4px;
        right: -4px;
        background: var(--astro-danger);
        color: #ffffff;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        padding: 2px 7px;
        min-width: 18px;
        text-align: center;
        border: 2px solid var(--astro-bg);
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
        display: none;
      }
      .astro-unread-badge.visible {
        display: block;
        animation: pulseBadge 1.8s infinite;
      }

      .astro-floating-wrapper {
        position: fixed;
        bottom: 94px;
        right: 24px;
        width: 420px;
        height: 600px;
        max-width: calc(100vw - 32px);
        max-height: calc(100vh - 120px);
        z-index: 99999;
        display: none;
        flex-direction: column;
      }
      :host(.rtl) .astro-floating-wrapper {
        right: auto;
        left: 24px;
      }
      .astro-floating-wrapper.open {
        display: flex;
        animation: slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      }
      .astro-floating-wrapper.minimized {
        height: 60px;
        overflow: hidden;
      }
      .astro-floating-wrapper.minimized .astro-messages,
      .astro-floating-wrapper.minimized .astro-footer,
      .astro-floating-wrapper.minimized .astro-escalate-banner,
      .astro-floating-wrapper.minimized .astro-task-strip,
      .astro-floating-wrapper.minimized .astro-action-card {
        display: none !important;
      }

      @media (max-width: 600px) {
        :host([mode="floating"]), :host(:not([mode])) {
          bottom: 16px;
          right: 16px;
        }
        :host([mode="floating"].rtl), :host(:not([mode]).rtl) {
          left: 16px;
          right: auto;
        }
        .astro-floating-wrapper {
          bottom: 84px;
          right: 12px;
          left: 12px;
          width: auto;
          max-width: none;
          height: 75vh;
        }
      }

      /* ---------------------------------------------------- */
      /* Header & Controls */
      /* ---------------------------------------------------- */
      .astro-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        background: var(--astro-header-bg);
        border-bottom: 1px solid var(--astro-panel-border);
        flex-shrink: 0;
      }

      .astro-header-left {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .astro-badge-icon {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: linear-gradient(135deg, #0284c7, var(--astro-accent));
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 17px;
        box-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
      }

      .astro-title {
        font-size: 14.5px;
        font-weight: 600;
        color: var(--astro-text);
        margin: 0;
        letter-spacing: 0.2px;
      }

      .astro-subtitle {
        font-size: 11px;
        color: var(--astro-text-muted);
        margin: 0;
      }

      .astro-header-right {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .astro-mode-pill {
        font-size: 10.5px;
        padding: 3px 8px;
        border-radius: 999px;
        background: var(--astro-accent-dim);
        color: var(--astro-accent);
        border: 1px solid var(--astro-accent);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .astro-mode-pill.companion {
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        border-color: #6366f1;
      }

      .astro-window-controls {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .astro-win-btn {
        background: transparent;
        border: none;
        color: var(--astro-text-muted);
        width: 26px;
        height: 26px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-size: 14px;
        transition: background 0.15s, color 0.15s;
      }
      .astro-win-btn:hover {
        background: rgba(255, 255, 255, 0.1);
        color: var(--astro-text);
      }

      /* ---------------------------------------------------- */
      /* Task HUD Strip */
      /* ---------------------------------------------------- */
      .astro-task-strip {
        display: none;
        align-items: center;
        gap: 8px;
        padding: 7px 14px;
        background: rgba(0, 240, 255, 0.1);
        border-bottom: 1px solid var(--astro-panel-border);
        font-size: 11.5px;
        color: var(--astro-accent);
        font-weight: 500;
      }
      .astro-task-strip.visible {
        display: flex;
        animation: fadeIn 0.25s ease;
      }
      .astro-task-pulse {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--astro-accent);
        box-shadow: 0 0 8px var(--astro-accent);
        animation: pulseDot 1.2s infinite ease-in-out;
      }

      /* ---------------------------------------------------- */
      /* Escalation Banner */
      /* ---------------------------------------------------- */
      .astro-escalate-banner {
        display: none;
        background: #451a03;
        border-bottom: 1px solid #92400e;
        color: #fef3c7;
        padding: 9px 14px;
        font-size: 12px;
        line-height: 1.4;
      }
      .astro-escalate-banner.visible {
        display: flex;
        align-items: center;
        gap: 8px;
        animation: fadeIn 0.3s ease;
      }

      /* ---------------------------------------------------- */
      /* Messages List */
      /* ---------------------------------------------------- */
      .astro-messages {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        background: var(--astro-bg);
      }

      .astro-msg {
        max-width: 84%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 13.5px;
        line-height: 1.5;
        word-break: break-word;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      }

      .astro-msg.assistant {
        align-self: flex-start;
        background: var(--astro-asst-bubble);
        color: var(--astro-text);
        border-bottom-left-radius: 2px;
        border: 1px solid rgba(255, 255, 255, 0.08);
      }
      .astro-container.rtl .astro-msg.assistant {
        align-self: flex-start;
        border-bottom-left-radius: 12px;
        border-bottom-right-radius: 2px;
      }

      .astro-msg.user {
        align-self: flex-end;
        background: var(--astro-user-bubble);
        color: #ffffff;
        border-bottom-right-radius: 2px;
      }
      .astro-container.rtl .astro-msg.user {
        align-self: flex-end;
        border-bottom-right-radius: 12px;
        border-bottom-left-radius: 2px;
      }

      .astro-msg-time {
        display: block;
        font-size: 10px;
        color: rgba(255, 255, 255, 0.6);
        margin-top: 4px;
        text-align: right;
      }
      .astro-container.rtl .astro-msg-time {
        text-align: left;
      }

      /* ---------------------------------------------------- */
      /* Action Card (End of Session) */
      /* ---------------------------------------------------- */
      .astro-action-card {
        display: none;
        background: rgba(30, 27, 75, 0.85);
        border: 1px solid #4338ca;
        border-radius: 12px;
        padding: 14px;
        text-align: center;
        margin: 10px 0;
      }
      .astro-action-card.visible {
        display: block;
        animation: fadeIn 0.3s ease;
      }
      .astro-action-title {
        font-size: 13px;
        font-weight: 600;
        color: #c7d2fe;
        margin-bottom: 8px;
      }
      .astro-action-btn {
        background: #4f46e5;
        color: #ffffff;
        border: none;
        padding: 8px 18px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: background 0.2s;
      }
      .astro-action-btn:hover {
        background: #4338ca;
      }

      /* ---------------------------------------------------- */
      /* Typing Indicator */
      /* ---------------------------------------------------- */
      .astro-typing {
        display: none;
        align-self: flex-start;
        padding: 8px 12px;
        background: var(--astro-asst-bubble);
        border-radius: 12px;
        border-bottom-left-radius: 2px;
      }
      .astro-typing.visible {
        display: flex;
        gap: 4px;
        align-items: center;
      }
      .astro-dot {
        width: 6px;
        height: 6px;
        background: var(--astro-text-muted);
        border-radius: 50%;
        animation: bounce 1.2s infinite ease-in-out;
      }
      .astro-dot:nth-child(2) { animation-delay: 0.2s; }
      .astro-dot:nth-child(3) { animation-delay: 0.4s; }

      /* ---------------------------------------------------- */
      /* Footer Input */
      /* ---------------------------------------------------- */
      .astro-footer {
        padding: 12px 14px;
        background: var(--astro-header-bg);
        border-top: 1px solid var(--astro-panel-border);
        display: flex;
        gap: 8px;
        flex-shrink: 0;
      }
      .astro-input {
        flex: 1;
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid var(--astro-panel-border);
        border-radius: 8px;
        padding: 10px 14px;
        color: var(--astro-text);
        font-size: 13.5px;
        outline: none;
        transition: border-color 0.2s, box-shadow 0.2s;
      }
      .astro-input:focus {
        border-color: var(--astro-accent);
        box-shadow: 0 0 8px var(--astro-accent-dim);
      }
      .astro-send-btn {
        background: var(--astro-accent);
        color: #070d1a;
        border: none;
        border-radius: 8px;
        padding: 0 16px;
        font-weight: 600;
        font-size: 13.5px;
        cursor: pointer;
        transition: background 0.2s, opacity 0.2s;
      }
      .astro-send-btn:hover:not(:disabled) {
        background: var(--astro-accent-hover);
      }
      .astro-send-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }

      @keyframes bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
      }
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(4px); }
        to { opacity: 1; transform: translateY(0); }
      }
      @keyframes slideUp {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
      }
      @keyframes pulseBadge {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.15); }
      }
      @keyframes pulseDot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.4; transform: scale(0.8); }
      }
    </style>

    <!-- Floating Launcher (visible only in floating mode) -->
    <div
      class="astro-launcher"
      id="launcherBtn"
      role="button"
      tabindex="0"
      aria-label="Open Astronaut Check-in Assistant"
      aria-expanded="false"
    >
      <span>🚀</span>
      <span class="astro-unread-badge" id="unreadBadge">0</span>
    </div>

    <!-- Main Container / Window -->
    <div class="astro-floating-wrapper" id="panelWrapper">
      <div class="astro-container" id="container">
        <!-- Header -->
        <div class="astro-header">
          <div class="astro-header-left">
            <div class="astro-badge-icon">🚀</div>
            <div>
              <h3 class="astro-title" id="titleText">AstroCheck Companion</h3>
              <p class="astro-subtitle" id="subtitleText">Mission Day -- • ID: --</p>
            </div>
          </div>
          <div class="astro-header-right">
            <span class="astro-mode-pill" id="modePill">Check-in</span>
            <div class="astro-window-controls" id="windowControls">
              <a class="astro-win-btn" id="expandBtn" style="display:none;text-decoration:none;" aria-label="Open Full Page AI Assistant" title="Open Full View">↗</a>
              <button class="astro-win-btn" id="minBtn" aria-label="Minimize Chat Panel" title="Minimize">−</button>
              <button class="astro-win-btn" id="closeBtn" aria-label="Close Chat Panel" title="Close">✕</button>
            </div>
          </div>
        </div>

        <!-- Task HUD Live Indicator Strip -->
        <div class="astro-task-strip" id="taskStrip">
          <span class="astro-task-pulse"></span>
          <span id="taskStripText">Active Task</span>
        </div>

        <!-- Escalation Banner -->
        <div class="astro-escalate-banner" id="escalateBanner">
          <span>🛡️</span>
          <span id="escalateBannerText">Flight surgeon and ground support notified. Reassuring support active.</span>
        </div>

        <!-- Messages Area -->
        <div class="astro-messages" id="messagesList" role="log" aria-live="polite">
          <div class="astro-typing" id="typingIndicator">
            <span class="astro-dot"></span>
            <span class="astro-dot"></span>
            <span class="astro-dot"></span>
          </div>
        </div>

        <!-- Check-in Complete Action Card -->
        <div class="astro-action-card" id="actionCard">
          <div class="astro-action-title" id="actionTitle">Check-in Complete. How would you like to proceed?</div>
          <button class="astro-action-btn" id="keepTalkingBtn">Keep Talking (Companion Mode)</button>
        </div>

        <!-- Footer Input Form -->
        <form class="astro-footer" id="chatForm">
          <input
            type="text"
            class="astro-input"
            id="messageInput"
            placeholder="Type your check-in message..."
            autocomplete="off"
            aria-label="Message text"
          />
          <button type="submit" class="astro-send-btn" id="sendBtn">Send</button>
        </form>
      </div>
    </div>
  `;

  class AstroChat extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.shadowRoot.appendChild(template.content.cloneNode(true));

      this.sessionId = null;
      this.sessionMode = "session"; // "session" | "companion"
      this.isArabic = false;
      this.isEnded = false;
      this.isBackendOffline = false;
      this.offlineCheckinStep = 0;
      this.offlineAnswers = [];
      this.unreadCount = 0;
      this.questionIndex = 0;

      // Host telemetry context
      this.hostContext = {
        task: null,
        phase: null,
        current_tab: null,
        note: null,
        signals_summary: null,
      };

      activeWidgetInstance = this;
    }

    static get observedAttributes() {
      return ["mode", "session-mode", "api-base", "astronaut-id", "mission-day", "language", "theme", "title-text", "full-page-href"];
    }

    get mode() {
      return (this.getAttribute("mode") || "inline").toLowerCase();
    }

    get requestedSessionMode() {
      const val = (this.getAttribute("session-mode") || "session").toLowerCase();
      return val === "companion" ? "companion" : "session";
    }

    get apiBase() {
      if (this.hasAttribute("api-base")) {
        return (this.getAttribute("api-base") || "").trim().replace(/\/+$/, "");
      }
      return window.location.origin;
    }

    get astronautId() {
      return parseInt(this.getAttribute("astronaut-id") || "1", 10);
    }

    get missionDay() {
      return parseInt(this.getAttribute("mission-day") || "42", 10);
    }

    get language() {
      const l = (this.getAttribute("language") || "auto").toLowerCase();
      if (l === "auto") {
        return (navigator.language || "").startsWith("ar") ? "ar" : "en";
      }
      return l;
    }

    get theme() {
      return (this.getAttribute("theme") || "auto").toLowerCase();
    }

    attributeChangedCallback(name, oldValue, newValue) {
      if (oldValue === newValue) return;
      if (name === "mode") {
        this.applyMode();
      } else if (name === "session-mode") {
        this.sessionMode = this.requestedSessionMode;
        if (this.titleText) this.setupLanguage();
      } else if (name === "language" || name === "title-text" || name === "astronaut-id" || name === "mission-day") {
        if (this.titleText) this.setupLanguage();
      } else if (name === "full-page-href") {
        this.syncExpandLink();
      } else if (name === "theme") {
        this.applyTheme();
      } else if (name === "api-base") {
        this.isBackendOffline = false;
        this.sessionId = null;
      }
    }

    connectedCallback() {
      this.sessionMode = this.requestedSessionMode;
      this.cacheElements();
      this.syncExpandLink();
      this.applyMode();
      this.applyTheme();
      this.setupLanguage();
      this.bindHostEvents();
      this.bindDomEvents();
      this.restoreSessionState();
      this.initSession();
    }

    syncExpandLink() {
      if (!this.expandBtn) return;
      const href = (this.getAttribute("full-page-href") || "").trim();
      if (href && this.mode === "floating") {
        this.expandBtn.setAttribute("href", href);
        this.expandBtn.style.display = "flex";
      } else {
        this.expandBtn.style.display = "none";
      }
    }

    disconnectedCallback() {
      this.unbindHostEvents();
      if (activeWidgetInstance === this) {
        activeWidgetInstance = null;
      }
    }

    cacheElements() {
      this.container = this.shadowRoot.getElementById("container");
      this.panelWrapper = this.shadowRoot.getElementById("panelWrapper");
      this.launcherBtn = this.shadowRoot.getElementById("launcherBtn");
      this.unreadBadge = this.shadowRoot.getElementById("unreadBadge");
      this.titleText = this.shadowRoot.getElementById("titleText");
      this.subtitleText = this.shadowRoot.getElementById("subtitleText");
      this.modePill = this.shadowRoot.getElementById("modePill");
      this.windowControls = this.shadowRoot.getElementById("windowControls");
      this.expandBtn = this.shadowRoot.getElementById("expandBtn");
      this.minBtn = this.shadowRoot.getElementById("minBtn");
      this.closeBtn = this.shadowRoot.getElementById("closeBtn");
      this.taskStrip = this.shadowRoot.getElementById("taskStrip");
      this.taskStripText = this.shadowRoot.getElementById("taskStripText");
      this.escalateBanner = this.shadowRoot.getElementById("escalateBanner");
      this.escalateBannerText = this.shadowRoot.getElementById("escalateBannerText");
      this.messagesList = this.shadowRoot.getElementById("messagesList");
      this.typingIndicator = this.shadowRoot.getElementById("typingIndicator");
      this.actionCard = this.shadowRoot.getElementById("actionCard");
      this.actionTitle = this.shadowRoot.getElementById("actionTitle");
      this.keepTalkingBtn = this.shadowRoot.getElementById("keepTalkingBtn");
      this.chatForm = this.shadowRoot.getElementById("chatForm");
      this.messageInput = this.shadowRoot.getElementById("messageInput");
      this.sendBtn = this.shadowRoot.getElementById("sendBtn");
    }

    applyMode() {
      if (!this.panelWrapper) return;
      const m = this.mode;

      if (m === "floating") {
        this.launcherBtn.style.display = "flex";
        // Floating wrapper opens according to state
        const savedState = sessionStorage.getItem(`astro_chat_state_${this.astronautId}`);
        if (savedState === "open") {
          this.open();
        } else if (savedState === "minimized") {
          this.minimize();
        } else {
          this.close();
        }
      } else {
        // Tab or inline: hide launcher, display wrapper directly
        this.launcherBtn.style.display = "none";
        this.panelWrapper.classList.add("open");
        this.panelWrapper.classList.remove("minimized");
      }
    }

    applyTheme() {
      const t = this.theme;
      if (t === "light") {
        this.setAttribute("theme", "light");
      } else if (t === "dark") {
        this.removeAttribute("theme");
      } else {
        // Auto
        if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
          this.setAttribute("theme", "light");
        } else {
          this.removeAttribute("theme");
        }
      }
    }

    setupLanguage() {
      this.isArabic = (this.language === "ar");
      if (this.isArabic) {
        this.container.classList.add("rtl");
        this.classList.add("rtl");
        this.titleText.textContent = "المساعد النفسي لرائد الفضاء";
        this.subtitleText.textContent = `يوم المهمة ${this.missionDay} • رائد الفضاء #${this.astronautId}`;
        this.modePill.textContent = this.sessionMode === "companion" ? "الرفيق" : "جلسة فحص";
        this.messageInput.placeholder = "اكتب رسالتك هنا...";
        this.sendBtn.textContent = "إرسال";
        this.escalateBannerText.textContent = "تم إشعار طبيب الرحلة والدعم الأرضي. لست وحدك، الفريق يتابعك بكل عناية.";
        this.actionTitle.textContent = "اكتملت جلسة الفحص اليومية بنجاح.";
        this.keepTalkingBtn.textContent = "مواصلة الحديث (وضع الرفيق)";
      } else {
        const customTitle = (this.getAttribute("title-text") || "").trim();
        this.container.classList.remove("rtl");
        this.classList.remove("rtl");
        this.titleText.textContent = customTitle || "Astronaut Check-in Assistant";
        this.subtitleText.textContent = `Mission Day ${this.missionDay} • Crew #${this.astronautId}`;
        this.modePill.textContent = this.sessionMode === "companion" ? "Open Chat" : "Check-in";
        this.messageInput.placeholder = "Ask Mission AI Assistant...";
        this.sendBtn.textContent = "Send";
        this.escalateBannerText.textContent = "Flight surgeon and ground support notified. Reassuring support active.";
        this.actionTitle.textContent = "Check-in complete. Switch to Open Discussion to keep talking freely.";
        this.keepTalkingBtn.textContent = "Continue in Open Discussion";
      }
      this.syncExpandLink();
    }

    bindDomEvents() {
      this.chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.handleUserSend();
      });

      this.keepTalkingBtn.addEventListener("click", () => {
        this.switchToCompanion();
      });

      // Floating Mode window controls
      this.launcherBtn.addEventListener("click", () => {
        if (this.panelWrapper.classList.contains("open") && !this.panelWrapper.classList.contains("minimized")) {
          this.close();
        } else {
          this.open();
        }
      });

      this.launcherBtn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this.open();
        }
      });

      this.closeBtn.addEventListener("click", () => this.close());
      this.minBtn.addEventListener("click", () => {
        if (this.panelWrapper.classList.contains("minimized")) {
          this.open();
        } else {
          this.minimize();
        }
      });

      // Keyboard Esc closes floating window
      this.escHandler = (e) => {
        if (e.key === "Escape" && this.mode === "floating" && this.panelWrapper.classList.contains("open")) {
          this.close();
        }
      };
      window.addEventListener("keydown", this.escHandler);
    }

    bindHostEvents() {
      // 1. Task Lifecycle event
      this.taskHandler = (e) => {
        const { task, phase, info } = e.detail || {};
        this.handleHostTask(task, phase, info);
      };
      window.addEventListener("astro:task", this.taskHandler);

      // 2. Host Page Context
      this.contextHandler = (e) => {
        const { current_tab, note } = e.detail || {};
        if (current_tab !== undefined) this.hostContext.current_tab = current_tab;
        if (note !== undefined) this.hostContext.note = note;
      };
      window.addEventListener("astro:context", this.contextHandler);

      // 3. Signals Summary from Teammate camera/mic module
      this.signalsHandler = (e) => {
        const { recent } = e.detail || {};
        if (recent) this.hostContext.signals_summary = recent;
      };
      window.addEventListener("astro:signals-summary", this.signalsHandler);
    }

    unbindHostEvents() {
      window.removeEventListener("astro:task", this.taskHandler);
      window.removeEventListener("astro:context", this.contextHandler);
      window.removeEventListener("astro:signals-summary", this.signalsHandler);
      window.removeEventListener("keydown", this.escHandler);
    }

    // ----------------------------------------------------
    // Window State API
    // ----------------------------------------------------
    open() {
      this.panelWrapper.classList.remove("minimized");
      this.panelWrapper.classList.add("open");
      this.launcherBtn.setAttribute("aria-expanded", "true");
      this.unreadCount = 0;
      this.updateUnreadBadge();
      sessionStorage.setItem(`astro_chat_state_${this.astronautId}`, "open");
      setTimeout(() => this.messageInput.focus(), 50);
    }

    close() {
      this.panelWrapper.classList.remove("open", "minimized");
      this.launcherBtn.setAttribute("aria-expanded", "false");
      sessionStorage.setItem(`astro_chat_state_${this.astronautId}`, "closed");
      this.launcherBtn.focus();
    }

    minimize() {
      this.panelWrapper.classList.add("open", "minimized");
      sessionStorage.setItem(`astro_chat_state_${this.astronautId}`, "minimized");
    }

    restoreSessionState() {
      if (this.mode === "floating") {
        const st = sessionStorage.getItem(`astro_chat_state_${this.astronautId}`);
        if (st === "open") this.open();
        else if (st === "minimized") this.minimize();
      }
    }

    updateUnreadBadge() {
      if (this.unreadCount > 0 && (!this.panelWrapper.classList.contains("open") || this.panelWrapper.classList.contains("minimized"))) {
        this.unreadBadge.textContent = this.unreadCount;
        this.unreadBadge.classList.add("visible");
      } else {
        this.unreadBadge.classList.remove("visible");
      }
    }

    // ----------------------------------------------------
    // Host Bridge Event Dispatcher
    // ----------------------------------------------------
    dispatchBridge(eventName, detail) {
      const evt = new CustomEvent(eventName, {
        detail: detail,
        bubbles: true,
        composed: true,
      });
      window.dispatchEvent(evt);
      this.dispatchEvent(evt);
    }

    // ----------------------------------------------------
    // Task Event Handling
    // ----------------------------------------------------
    async handleHostTask(task, phase, info) {
      this.hostContext.task = task;
      this.hostContext.phase = phase;

      if (phase === "started") {
        this.taskStripText.textContent = this.isArabic
          ? `مهمة جارية: ${task} • جلسة الفحص مؤجلة مؤقتاً`
          : `Active Task: ${task} • Check-in paused`;
        this.taskStrip.classList.add("visible");

        // Forward task started event to backend
        if (this.sessionId) {
          try {
            await fetch(`${this.apiBase}/sessions/${this.sessionId}/events`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ task, phase: "started", info }),
            });
          } catch (e) {
            console.warn("Error forwarding task started event to backend:", e);
          }
        }
      } else if (phase === "ended") {
        this.taskStripText.textContent = this.isArabic
          ? `اكتملت المهمة: ${task} • استئناف الفحص...`
          : `Task Completed: ${task} • Resuming check-in...`;
        setTimeout(() => this.taskStrip.classList.remove("visible"), 4000);

        // Forward task ended event to backend
        if (this.sessionId) {
          try {
            await fetch(`${this.apiBase}/sessions/${this.sessionId}/events`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ task, phase: "ended", info }),
            });
          } catch (e) {
            console.warn("Error forwarding task ended event to backend:", e);
          }

          // Check if a queued question was held during the task
          await this.pollPendingQuestion();
        }
      }
    }

    async pollPendingQuestion() {
      if (!this.sessionId) return;
      try {
        const res = await fetch(`${this.apiBase}/sessions/${this.sessionId}/pending?deliver=true`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.has_pending && data.question) {
          this.appendMessage("assistant", data.question);
          this.questionIndex = data.question_index || (this.questionIndex + 1);
          this.dispatchBridge("astro:question", {
            session_id: this.sessionId,
            index: this.questionIndex,
            text: data.question,
            ts: new Date().toISOString(),
          });
        }
      } catch (err) {
        console.warn("Error polling pending question:", err);
      }
    }

    // ----------------------------------------------------
    // Session API Integration
    // ----------------------------------------------------
    getOfflineCheckinQuestions() {
      if (this.isArabic) {
        return [
          "[1/7] النوم والراحة: كم ساعة نمت اليوم وهل شعرت بالراحة عند الاستيقاظ؟",
          "[2/7] المزاج والطاقة: كيف تقيم حالتك المزاجية ومستوى طاقتك منذ الصباح؟",
          "[3/7] ضغط العمل: هل مهام اليوم وضغط الجدول التشغيلي تحت السيطرة؟",
          "[4/7] التركيز والانتباه: هل لاحظت أي إرهاق ذهني أو صعوبة في التركيز أثناء الفحوصات؟",
          "[5/7] التواصل والطاقم: كيف تسير علاقتك مع بقية الطاقم والتواصل مع الأرض والعائلة؟",
          "[6/7] الراحة الجسدية والبيئة: هل تعاني من صداع أو احتقان أو ضيق بسبب ثاني أكسيد الكربون أو الضوضاء؟",
          "[7/7] ملاحظات إضافية: هل هناك أي شيء آخر تود تسجيله لمتابعة طبيب الرحلة؟",
        ];
      }
      return [
        "[1/7] Sleep & circadian rest: How many hours did you sleep, and did you wake up rested?",
        "[2/7] Mood & energy: How has your overall mood and emotional energy felt today?",
        "[3/7] Workload & stress: Are EVA, maintenance, and timeline demands feeling manageable?",
        "[4/7] Cognition & focus: Any brain fog, slowed recall, or checklist concentration difficulty?",
        "[5/7] Crew cohesion & contact: How are interactions with crewmates and ground/family going?",
        "[6/7] Habitat & physical comfort: Any headache, congestion, eye strain, or CO2/noise discomfort?",
        "[7/7] Final check: Anything else you want logged or flagged for Flight Surgeon review today?",
      ];
    }

    detectOfflineCrisis(text) {
      return /(self[- ]?harm|suicide|kill myself|end my life|hurt myself|want to die|انتحار|أؤذي نفسي|اؤذي نفسي|أقتل نفسي|اقتل نفسي)/i.test(String(text || ""));
    }

    startOfflineModeNotice(silent, reasonPrefix) {
      this.isBackendOffline = true;
      this.isEnded = false;
      this.actionCard?.classList.remove("visible");
      if (!silent) {
        if (this.sessionMode === "session") {
          this.offlineCheckinStep = 1;
          this.offlineAnswers = [];
          const q1 = this.getOfflineCheckinQuestions()[0];
          const intro = this.isArabic
            ? `الفحص اليومي المحلي (7 أسئلة) جاهز — الخادم غير متصل.\n${q1}`
            : `Offline Daily Check-in active (7 Questions, local NASA Copilot mode).\n${q1}`;
          this.appendMessage("assistant", intro);
        } else {
          const hasLocalCopilot = typeof window.queryBioCopilot === "function";
          const offlineMsg = this.isArabic
            ? "الخادم غير متصل حالياً — يمكنك الكتابة أدناه لاستخدام المساعد المحلي."
            : hasLocalCopilot
              ? reasonPrefix
              : "No backend URL configured. Enter a FastAPI backend URL to enable live sessions.";
          this.appendMessage("assistant", offlineMsg);
        }
      }
      this.dispatchBridge("astro:backend-offline", { apiBase: this.apiBase });
    }

    async initSession(silent = false) {
      this.sessionMode = this.requestedSessionMode;
      if (!this.apiBase) {
        if (!this.hasAttribute("session-mode")) {
          this.sessionMode = "companion";
          if (this.titleText) this.setupLanguage();
        }
        this.startOfflineModeNotice(
          silent,
          "Offline NASA Copilot mode active (no remote FastAPI backend configured on this static host). Type below to ask about vitals, NASA HRP risks, CO2/radiation, or connect a backend URL on the left."
        );
        this.showTyping(false);
        return;
      }

      this.showTyping(true);
      const controller = typeof AbortController === "function" ? new AbortController() : null;
      const timerId = controller ? setTimeout(() => controller.abort(), 4500) : null;
      try {
        const res = await fetch(`${this.apiBase}/sessions/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller ? controller.signal : undefined,
          body: JSON.stringify({
            astronaut_id: this.astronautId,
            mission_day: this.missionDay,
            mode: this.sessionMode,
          }),
        });

        if (!res.ok) {
          throw new Error(`Failed to start session: HTTP ${res.status}`);
        }

        const data = await res.json();
        this.isBackendOffline = false;
        this.sessionId = data.session_id;
        this.sessionMode = data.mode || this.requestedSessionMode;
        this.questionIndex = this.sessionMode === "companion" ? 0 : 1;
        this.setupLanguage();

        // Auto-detect Arabic from first message if language is "auto"
        if (this.language === "auto" && /[\u0600-\u06FF]/.test(data.first_message)) {
          this.setAttribute("language", "ar");
          this.setupLanguage();
        }

        this.appendMessage("assistant", data.first_message);

        // Dispatch bridge events
        this.dispatchBridge("astro:session", {
          session_id: this.sessionId,
          astronaut_id: this.astronautId,
          mode: this.sessionMode,
        });

        this.dispatchBridge("astro:question", {
          session_id: this.sessionId,
          index: 1,
          text: data.first_message,
          ts: new Date().toISOString(),
        });
      } catch (err) {
        // Suppress unhandled connection refuse noise while running locally
        console.warn("Bio Astro Assistant: Backend offline at " + this.apiBase + ". Switched to client-side NASA Bio-Copilot.");
        this.startOfflineModeNotice(
          silent,
          "FastAPI backend offline at " + this.apiBase + ". Run Chat Bot\\run.bat locally or connect a deployed backend URL — meanwhile, type below for instant Offline NASA Copilot replies."
        );
      } finally {
        if (timerId) clearTimeout(timerId);
        this.showTyping(false);
      }
    }

    buildOfflineReply(text) {
      if (this.detectOfflineCrisis(text)) {
        this.showEscalationBanner();
        this.dispatchBridge("astro:escalate", {
          session_id: null,
          reason: "Crisis safety safeguard triggered in offline mode",
        });
        return this.isArabic
          ? "تم تفعيل تنبيه الدعم الفوري. لست وحدك — يرجى التواصل مباشرة مع طبيب الرحلة أو مركز التحكم الأرضي أو فريق السلامة المعتمد الآن."
          : "Priority crew safety alert triggered. You are not alone — please contact the Flight Surgeon, Ground Control medical officer, or your mission support team immediately.";
      }
      if (this.sessionMode === "session" && !this.isEnded) {
        this.offlineAnswers.push(text);
        const questions = this.getOfflineCheckinQuestions();
        if (this.offlineCheckinStep < questions.length) {
          this.offlineCheckinStep += 1;
          const ack = this.isArabic ? "تم التوثيق." : "Logged.";
          return `${ack} ${questions[this.offlineCheckinStep - 1]}`;
        }
        this.isEnded = true;
        this.actionCard?.classList.add("visible");
        this.dispatchBridge("astro:session-ended", {
          session_id: null,
          analysis_ready: false,
        });
        const combined = this.offlineAnswers.join(" | ");
        const copilotSummary = this.queryCopilotOffline(combined);
        return this.isArabic
          ? `اكتمل الفحص اليومي (7/7) في الوضع المحلي.\n${copilotSummary}`
          : `7/7 Daily Check-in complete (Offline Mode).\n${copilotSummary}`;
      }
      return this.queryCopilotOffline(text);
    }

    queryCopilotOffline(text) {
      if (typeof window.queryBioCopilot === "function") {
        const sess = window.BioShell && typeof window.BioShell.getSession === "function" ? window.BioShell.getSession() : null;
        const features = sess ? sess.features : {};
        const ans = window.queryBioCopilot(text, features);
        if (ans && (ans.responseText || ans.answer)) {
          return ans.responseText || ans.answer;
        }
      }
      return "Offline mode active (start Chat Bot\\run.bat on port 8000 for full conversational check-in & history).";
    }

    async handleUserSend() {
      const text = this.messageInput.value.trim();
      if (!text) return;

      this.messageInput.value = "";
      this.appendMessage("user", text);
      this.setInputsDisabled(true);
      this.showTyping(true);

      this.dispatchBridge("astro:message", {
        role: "user",
        text: text,
        ts: new Date().toISOString(),
        escalate: false,
      });

      try {
        if (!this.sessionId && !this.isBackendOffline) {
          await this.initSession(true);
        }

        if (!this.sessionId) {
          const fallbackReply = this.buildOfflineReply(text);
          this.appendMessage("assistant", fallbackReply);
          this.dispatchBridge("astro:message", {
            role: "assistant",
            text: fallbackReply,
            ts: new Date().toISOString(),
            escalate: false,
          });
          return;
        }

        const payload = {
          session_id: this.sessionId,
          message: text,
          context: {
            task: this.hostContext.task,
            phase: this.hostContext.phase,
            current_tab: this.hostContext.current_tab,
            note: this.hostContext.note,
            signals_summary: this.hostContext.signals_summary,
          },
        };

        const res = await fetch(`${this.apiBase}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          throw new Error(`Chat error: HTTP ${res.status}`);
        }

        const data = await res.json();
        this.appendMessage("assistant", data.reply);

        if (data.escalate) {
          this.showEscalationBanner();
          this.dispatchBridge("astro:escalate", {
            session_id: this.sessionId,
            reason: "Escalation triggered by safety monitoring",
          });
        }

        // If not a task pause acknowledgment and not ended, dispatch question event
        if (!data.task_active && !data.session_should_end && this.sessionMode === "session") {
          this.questionIndex += 1;
          this.dispatchBridge("astro:question", {
            session_id: this.sessionId,
            index: this.questionIndex,
            text: data.reply,
            ts: new Date().toISOString(),
          });
        }

        this.dispatchBridge("astro:message", {
          role: "assistant",
          text: data.reply,
          ts: new Date().toISOString(),
          escalate: !!data.escalate,
        });

        const shouldEnd = data.session_should_end || data.should_end;
        if (shouldEnd && this.sessionMode === "session") {
          await this.completeSession();
        }
      } catch (err) {
        console.error("Chat error:", err);
        const errText = this.isArabic
          ? "حدث خطأ أثناء إرسال الرسالة."
          : "An error occurred sending your message.";
        this.appendMessage("assistant", errText);
      } finally {
        this.showTyping(false);
        this.setInputsDisabled(false);
        this.messageInput.focus();
      }
    }

    async completeSession() {
      this.isEnded = true;
      let analysisReady = false;
      try {
        const res = await fetch(`${this.apiBase}/sessions/${this.sessionId}/end`, {
          method: "POST",
        });
        if (res.ok) analysisReady = true;
      } catch (e) {
        console.warn("End session call notice:", e);
      }

      this.actionCard.classList.add("visible");
      this.scrollToBottom();

      this.dispatchBridge("astro:session-ended", {
        session_id: this.sessionId,
        analysis_ready: analysisReady,
      });
    }

    async switchToCompanion() {
      if (!this.apiBase || this.isBackendOffline || !this.sessionId) {
        this.sessionMode = "companion";
        this.modePill.textContent = this.isArabic ? "الرفيق" : "Companion";
        this.modePill.classList.add("companion");
        this.actionCard.classList.remove("visible");
        const msg = this.isArabic
          ? "تم التبديل إلى وضع الرفيق المحلي. يمكنك طرح أي سؤال حول القياسات الحيوية أو مخاطر ناسا."
          : "Switched to Companion mode (Offline NASA Copilot). Ask anything about vitals, sleep, radiation, or NASA HRP risks.";
        this.appendMessage("assistant", msg);
        this.dispatchBridge("astro:message", {
          role: "assistant",
          text: msg,
          ts: new Date().toISOString(),
          escalate: false,
        });
        this.messageInput.focus();
        return;
      }

      this.keepTalkingBtn.disabled = true;
      this.showTyping(true);
      try {
        const res = await fetch(`${this.apiBase}/sessions/${this.sessionId}/companion`, {
          method: "POST",
        });
        if (!res.ok) {
          throw new Error(`Companion switch error: HTTP ${res.status}`);
        }
        const data = await res.json();
        this.sessionMode = "companion";
        this.modePill.textContent = this.isArabic ? "الرفيق" : "Companion";
        this.modePill.classList.add("companion");
        this.actionCard.classList.remove("visible");
        this.appendMessage("assistant", data.opening_message);

        this.dispatchBridge("astro:session", {
          session_id: this.sessionId,
          astronaut_id: this.astronautId,
          mode: "companion",
        });

        this.dispatchBridge("astro:message", {
          role: "assistant",
          text: data.opening_message,
          ts: new Date().toISOString(),
          escalate: false,
        });
      } catch (err) {
        console.error("Companion transition error:", err);
      } finally {
        this.showTyping(false);
        this.keepTalkingBtn.disabled = false;
        this.messageInput.focus();
      }
    }

    showEscalationBanner() {
      this.escalateBanner.classList.add("visible");
    }

    showTyping(show) {
      if (show) {
        this.typingIndicator.classList.add("visible");
        this.messagesList.appendChild(this.typingIndicator);
      } else {
        this.typingIndicator.classList.remove("visible");
      }
      this.scrollToBottom();
    }

    setInputsDisabled(disabled) {
      this.messageInput.disabled = disabled;
      this.sendBtn.disabled = disabled;
    }

    appendMessage(role, content) {
      const msgDiv = document.createElement("div");
      msgDiv.className = `astro-msg ${role}`;

      const textSpan = document.createElement("span");
      textSpan.textContent = content;
      msgDiv.appendChild(textSpan);

      const timeSpan = document.createElement("span");
      timeSpan.className = "astro-msg-time";
      const now = new Date();
      timeSpan.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      msgDiv.appendChild(timeSpan);

      this.messagesList.insertBefore(msgDiv, this.typingIndicator);
      this.scrollToBottom();

      // If floating mode and window is closed/minimized, update unread count
      if (role === "assistant" && this.mode === "floating") {
        if (!this.panelWrapper.classList.contains("open") || this.panelWrapper.classList.contains("minimized")) {
          this.unreadCount += 1;
          this.updateUnreadBadge();
        }
      }
    }

    scrollToBottom() {
      setTimeout(() => {
        this.messagesList.scrollTop = this.messagesList.scrollHeight;
      }, 50);
    }

    // ----------------------------------------------------
    // Global window.AstroChat helper hooks
    // ----------------------------------------------------
    sendSystemNote(text) {
      this.hostContext.note = text;
    }

    setContext(obj) {
      if (!obj || typeof obj !== "object") return;
      Object.assign(this.hostContext, obj);
    }
  }

  // Register Custom Web Component
  if (!customElements.get("astro-chat")) {
    customElements.define("astro-chat", AstroChat);
  }

  // Expose global window.AstroChat API
  window.AstroChat = {
    open: function () {
      if (activeWidgetInstance) activeWidgetInstance.open();
    },
    close: function () {
      if (activeWidgetInstance) activeWidgetInstance.close();
    },
    startSession: function () {
      if (activeWidgetInstance) {
        activeWidgetInstance.isBackendOffline = false;
        activeWidgetInstance.sessionId = null;
        activeWidgetInstance.initSession();
      }
    },
    endSession: function () {
      if (activeWidgetInstance) activeWidgetInstance.completeSession();
    },
    sendSystemNote: function (text) {
      if (activeWidgetInstance) activeWidgetInstance.sendSystemNote(text);
    },
    getSessionId: function () {
      return activeWidgetInstance ? activeWidgetInstance.sessionId : null;
    },
    setContext: function (obj) {
      if (activeWidgetInstance) activeWidgetInstance.setContext(obj);
    },
  };
})();
