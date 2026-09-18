(function prepareBioNemoStartingSessions() {
  "use strict";

  var examples = Array.isArray(globalThis.__BIONEMO_EXAMPLE_SESSIONS__)
    ? globalThis.__BIONEMO_EXAMPLE_SESSIONS__
    : [];
  var url = new URL(window.location.href);

  function gatewayUrlForPage() {
    var scheme = url.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}//${url.host}`;
  }

  function seedComposerDrafts() {
    if (!examples.length || !window.localStorage) return;
    var gatewayUrl = gatewayUrlForPage();
    var suffix = encodeURIComponent(gatewayUrl.trim() || "default").slice(0, 240);
    var storageKey = `openclaw.control.chatComposer.v1:${suffix}`;
    var markerKey = `bionemo.demoDraftSeed.v1:${suffix}`;
    try {
      if (window.localStorage.getItem(markerKey) === "1") return;
      var parsed = { version: 1, sessions: {} };
      var stored = window.localStorage.getItem(storageKey);
      if (stored) {
        var candidate;
        try { candidate = JSON.parse(stored); } catch { candidate = null; }
        if (candidate && candidate.version === 1 && candidate.sessions && typeof candidate.sessions === "object" && !Array.isArray(candidate.sessions)) {
          parsed = candidate;
        }
      }
      var now = Date.now();
      examples.forEach(function seedExample(example, index) {
        var sessionStorageKey = `${example.key}\u0000agent:${example.agentId}`;
        var existing = parsed.sessions[sessionStorageKey];
        var validExisting = existing && typeof existing === "object" && !Array.isArray(existing) ? existing : {};
        if (typeof validExisting.draft === "string" && validExisting.draft.trim()) return;
        parsed.sessions[sessionStorageKey] = {
          ...validExisting,
          draft: example.prompt,
          updatedAt: now + index,
        };
      });
      var newest = Object.entries(parsed.sessions)
        .sort(function newestFirst(left, right) {
          return Number(right[1] && right[1].updatedAt || 0) - Number(left[1] && left[1].updatedAt || 0);
        })
        .slice(0, 20);
      parsed.sessions = Object.fromEntries(newest);
      window.localStorage.setItem(storageKey, JSON.stringify(parsed));
      window.localStorage.setItem(markerKey, "1");
    } catch {
      // Storage may be unavailable or full. Notebook links still carry their
      // reviewed draft explicitly, and no failure may weaken authentication.
    }
  }

  // The pinned Control UI normally restores these native composer records when
  // switching sessions. Its SPA route transition currently reads the correct
  // record but can leave the textarea empty. Bridge that narrow integration
  // gap through the native input contract: never send, queue, or overwrite an
  // existing composer value, and never resurrect a draft the user removed
  // from native storage.
  function installExampleDraftBridge() {
    if (!examples.length || !window.document || typeof window.MutationObserver !== "function") return;
    var restored = new Set();
    var scheduled = false;

    function storedDraft(example) {
      if (!window.localStorage) return "";
      try {
        var storageKey = `openclaw.control.chatComposer.v1:${encodeURIComponent(gatewayUrlForPage().trim() || "default").slice(0, 240)}`;
        var stored = window.localStorage.getItem(storageKey);
        if (!stored) return "";
        var parsed = JSON.parse(stored);
        var entry = parsed && parsed.version === 1 && parsed.sessions
          ? parsed.sessions[`${example.key}\u0000agent:${example.agentId}`]
          : null;
        return entry && typeof entry.draft === "string" && entry.draft.trim() ? entry.draft : "";
      } catch {
        return "";
      }
    }

    function restoreRequestedExample() {
      var current = new URL(window.location.href);
      var requested = current.pathname === "/chat" ? current.searchParams.get("session") : "";
      var example = examples.find(function findExample(entry) { return entry.key === requested; });
      if (!example || restored.has(example.key)) return;
      var pane = window.document.querySelector("openclaw-chat-pane");
      if (!pane || !pane.state || pane.state.sessionKey !== example.key) return;
      var textarea = pane.querySelector(".agent-chat__composer-combobox > textarea");
      if (!textarea) return;
      if (typeof textarea.value === "string" && textarea.value.length > 0) {
        restored.add(example.key);
        return;
      }
      var draft = storedDraft(example);
      if (!draft) return;
      var descriptor = window.HTMLTextAreaElement
        ? Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")
        : null;
      if (descriptor && typeof descriptor.set === "function") descriptor.set.call(textarea, draft);
      else textarea.value = draft;
      textarea.dispatchEvent(new window.Event("input", { bubbles: true, composed: true }));
      restored.add(example.key);
    }

    function scheduleRestore() {
      if (scheduled) return;
      scheduled = true;
      var enqueue = typeof window.queueMicrotask === "function"
        ? window.queueMicrotask.bind(window)
        : function enqueueFallback(callback) { window.setTimeout(callback, 0); };
      enqueue(function runRestore() {
        scheduled = false;
        restoreRequestedExample();
      });
    }

    function startObserver() {
      if (!window.document.documentElement) return;
      var observer = new window.MutationObserver(scheduleRestore);
      observer.observe(window.document.documentElement, { attributes: true, childList: true, subtree: true });
      window.addEventListener("popstate", scheduleRestore);
      ["pushState", "replaceState"].forEach(function wrapHistory(method) {
        var original = window.history && window.history[method];
        if (typeof original !== "function") return;
        window.history[method] = function bridgedHistory() {
          var result = original.apply(this, arguments);
          scheduleRestore();
          return result;
        };
      });
      scheduleRestore();
    }

    if (window.document.documentElement) startObserver();
    else window.addEventListener("DOMContentLoaded", startObserver, { once: true });
  }

  seedComposerDrafts();
  installExampleDraftBridge();

  var defaultDemoPrompt = examples[0] && examples[0].prompt;
  var requestedSession = url.searchParams.get("session");
  var isRootDefault = url.pathname === "/" && (!requestedSession || requestedSession === "main");
  var isLegacyChatDefault = url.pathname === "/chat" && requestedSession === "main";

  if (!isRootDefault && !isLegacyChatDefault) return;

  url.pathname = "/chat";
  url.searchParams.set("session", "agent:bionemo:main");
  if (defaultDemoPrompt && !url.searchParams.has("draft")) url.searchParams.set("draft", defaultDemoPrompt);
  window.history.replaceState(
    window.history.state,
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
})();
