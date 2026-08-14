(function prepareBioNemoStartingSessions() {
  "use strict";

  var examples = Array.isArray(globalThis.__BIONEMO_EXAMPLE_SESSIONS__)
    ? globalThis.__BIONEMO_EXAMPLE_SESSIONS__
    : [];
  var nativeComposerSessionCap = 20;
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
    var markerKey = `bionemo.demoDraftSeed.v2:${suffix}`;
    var legacyMarkerKey = `bionemo.demoDraftSeed.v1:${suffix}`;
    try {
      if (window.localStorage.getItem(markerKey) === "1") return;
      var upgradingFromV1 = window.localStorage.getItem(legacyMarkerKey) === "1";
      var parsed = { version: 1, sessions: {} };
      var stored = window.localStorage.getItem(storageKey);
      if (stored) {
        var candidate;
        try { candidate = JSON.parse(stored); } catch { candidate = null; }
        if (candidate && candidate.version === 1 && candidate.sessions && typeof candidate.sessions === "object" && !Array.isArray(candidate.sessions)) {
          parsed = candidate;
        }
      }
      var storedSessionCount = Object.keys(parsed.sessions).length;
      var minimumExistingUpdatedAt = Object.values(parsed.sessions).reduce(function oldestTimestamp(minimum, entry) {
        var updatedAt = entry && typeof entry.updatedAt === "number" && Number.isFinite(entry.updatedAt)
          ? entry.updatedAt
          : minimum;
        return Math.min(minimum, updatedAt);
      }, 0);
      var exampleUpdatedAtBase = minimumExistingUpdatedAt - examples.length;
      examples.forEach(function seedExample(example, index) {
        // A missing v1 draft may mean that its user deliberately cleared it.
        // During the v2 upgrade, seed only newly introduced definitions.
        if (upgradingFromV1 && example.draftSeedGeneration === 1) return;
        var sessionStorageKey = `${example.key}\u0000agent:${example.agentId}`;
        var hasExisting = Object.prototype.hasOwnProperty.call(parsed.sessions, sessionStorageKey);
        var existing = parsed.sessions[sessionStorageKey];
        var validExisting = existing && typeof existing === "object" && !Array.isArray(existing) ? existing : {};
        if (typeof validExisting.draft === "string" && validExisting.draft.trim()) return;
        // OpenClaw retains at most 20 composer records on its next native
        // write. Existing records are user-owned and always take precedence;
        // fill only genuinely free slots in deterministic catalog order.
        if (!hasExisting && storedSessionCount >= nativeComposerSessionCap) return;
        parsed.sessions[sessionStorageKey] = {
          ...validExisting,
          draft: example.prompt,
          // New image records are deliberately older than every preserved
          // native record, so OpenClaw evicts an example before user state if
          // a later user session takes the store over its retention cap.
          ...(hasExisting ? {} : { updatedAt: exampleUpdatedAtBase + index }),
        };
        if (!hasExisting) storedSessionCount += 1;
      });
      window.localStorage.setItem(storageKey, JSON.stringify(parsed));
      window.localStorage.setItem(markerKey, "1");
    } catch {
      // Storage may be unavailable or full. Static starter transcripts and
      // notebook links still expose reviewed prompts, and no failure may
      // weaken authentication.
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
    var lastRequested = "";
    var restoredForRequested = false;
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
      if (requested !== lastRequested) {
        lastRequested = requested;
        restoredForRequested = false;
      }
      var example = examples.find(function findExample(entry) { return entry.key === requested; });
      if (!example || restoredForRequested) return;
      var pane = window.document.querySelector("openclaw-chat-pane");
      if (!pane || !pane.state || pane.state.sessionKey !== example.key) return;
      var textarea = pane.querySelector(".agent-chat__composer-combobox > textarea");
      if (!textarea) return;
      if (typeof textarea.value === "string" && textarea.value.length > 0) {
        restoredForRequested = true;
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
      restoredForRequested = true;
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
