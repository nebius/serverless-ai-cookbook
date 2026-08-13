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

  seedComposerDrafts();

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
