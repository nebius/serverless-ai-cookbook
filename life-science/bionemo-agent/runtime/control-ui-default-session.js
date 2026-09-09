(function prepareBioNemoStartingSessions() {
  "use strict";

  var examples = Array.isArray(globalThis.__BIONEMO_EXAMPLE_SESSIONS__)
    ? globalThis.__BIONEMO_EXAMPLE_SESSIONS__
    : [];
  var nativeComposerSessionCap = 20;
  var previousSourceOwnedPromptFingerprints = Object.freeze({
    "agent:bionemo:dashboard:egfr-research-drug-demo": "608:a78dc6f63503b2038d117d846aab456b1c8afae15d2fbaadeff28f96a3824078",
    "agent:bionemo:dashboard:compare-protein-structures": "633:20214fdeba0d23447c5d8e023adba46bff976f1161e339d94310390433ffe042",
    "agent:bionemo:dashboard:optimize-ligand-complex": "640:1713b67dd3eaaf31a7e881a78b6770c156adbd76d79cc6aff9b3f14b0b5714ed",
    "agent:bionemo:dashboard:bulk-openfold2-five-proteins": "751:cc2c25912e802f6163d2e370de36c1a3336568fe33bc410c927a6c7b5a4039e9",
    "agent:bionemo:dashboard:openclaw-workbench-tour": "1037:e9cf8284e576351c550c1ddad2f2b5f4add84aa63b2a06907c9088c2cc8e0b04",
    "agent:bionemo:dashboard:openclaw-skill-guidance": "623:5b4cbb56104322d84fe757ded7e4173b3ee4c45aabb1273b372afd8a7d594cc6",
    "agent:bionemo:dashboard:clawbio-readonly-catalog": "445:736e889573073dee8714040e0e0a7b7edfb9d791d6bfd6564352af5c2b414f88",
    "agent:bionemo:dashboard:clawbio-gwas-demo": "514:201ed46b345558de8c4562c23437c1e951d5a751757967f1682e84f1a40908ee",
    "agent:bionemo:dashboard:tavily-public-research": "986:27642822417fb264da4f3f495b783e351651e8de9f88883a61648aa3eddf5150",
    "agent:bionemo:dashboard:bionemo-model-inventory": "699:4c5276b18189ec69a59e7d19ba112d1b88186ba3768d2093542eafe5344f4a7b",
    "agent:bionemo:dashboard:molmim-direct-mcp": "753:fb4d7356a9a42d24532d3080cc5b51856773556aeeb746ebf205e21c714412bd",
  });
  var sha256RoundConstants = Object.freeze([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ]);
  var url = new URL(window.location.href);

  function rotateRight32(value, amount) {
    return (value >>> amount) | (value << (32 - amount));
  }

  // The legacy source prompts are ASCII. Hash them synchronously so this
  // classic bootstrap completes before the following OpenClaw module reads
  // local storage; Web Crypto would introduce an asynchronous startup race.
  function sha256Ascii(value) {
    if (typeof value !== "string") return "";
    var bytes = [];
    for (var characterIndex = 0; characterIndex < value.length; characterIndex += 1) {
      var characterCode = value.charCodeAt(characterIndex);
      if (characterCode > 0x7f) return "";
      bytes.push(characterCode);
    }

    var byteLength = bytes.length;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) bytes.push(0);
    var bitLengthHigh = Math.floor(byteLength / 0x20000000) >>> 0;
    var bitLengthLow = (byteLength * 8) >>> 0;
    bytes.push(
      (bitLengthHigh >>> 24) & 0xff,
      (bitLengthHigh >>> 16) & 0xff,
      (bitLengthHigh >>> 8) & 0xff,
      bitLengthHigh & 0xff,
      (bitLengthLow >>> 24) & 0xff,
      (bitLengthLow >>> 16) & 0xff,
      (bitLengthLow >>> 8) & 0xff,
      bitLengthLow & 0xff,
    );

    var hash = [
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    var words = new Array(64);
    for (var offset = 0; offset < bytes.length; offset += 64) {
      for (var wordIndex = 0; wordIndex < 16; wordIndex += 1) {
        var byteOffset = offset + (wordIndex * 4);
        words[wordIndex] = (
          (bytes[byteOffset] << 24)
          | (bytes[byteOffset + 1] << 16)
          | (bytes[byteOffset + 2] << 8)
          | bytes[byteOffset + 3]
        ) >>> 0;
      }
      for (var scheduleIndex = 16; scheduleIndex < 64; scheduleIndex += 1) {
        var previous15 = words[scheduleIndex - 15];
        var previous2 = words[scheduleIndex - 2];
        var sigma0 = (rotateRight32(previous15, 7) ^ rotateRight32(previous15, 18) ^ (previous15 >>> 3)) >>> 0;
        var sigma1 = (rotateRight32(previous2, 17) ^ rotateRight32(previous2, 19) ^ (previous2 >>> 10)) >>> 0;
        words[scheduleIndex] = (words[scheduleIndex - 16] + sigma0 + words[scheduleIndex - 7] + sigma1) >>> 0;
      }

      var a = hash[0];
      var b = hash[1];
      var c = hash[2];
      var d = hash[3];
      var e = hash[4];
      var f = hash[5];
      var g = hash[6];
      var h = hash[7];
      for (var round = 0; round < 64; round += 1) {
        var upperSigma1 = (rotateRight32(e, 6) ^ rotateRight32(e, 11) ^ rotateRight32(e, 25)) >>> 0;
        var choose = ((e & f) ^ ((~e) & g)) >>> 0;
        var temporary1 = (h + upperSigma1 + choose + sha256RoundConstants[round] + words[round]) >>> 0;
        var upperSigma0 = (rotateRight32(a, 2) ^ rotateRight32(a, 13) ^ rotateRight32(a, 22)) >>> 0;
        var majority = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
        var temporary2 = (upperSigma0 + majority) >>> 0;
        h = g;
        g = f;
        f = e;
        e = (d + temporary1) >>> 0;
        d = c;
        c = b;
        b = a;
        a = (temporary1 + temporary2) >>> 0;
      }
      hash[0] = (hash[0] + a) >>> 0;
      hash[1] = (hash[1] + b) >>> 0;
      hash[2] = (hash[2] + c) >>> 0;
      hash[3] = (hash[3] + d) >>> 0;
      hash[4] = (hash[4] + e) >>> 0;
      hash[5] = (hash[5] + f) >>> 0;
      hash[6] = (hash[6] + g) >>> 0;
      hash[7] = (hash[7] + h) >>> 0;
    }
    return hash.map(function toHex(valuePart) {
      return valuePart.toString(16).padStart(8, "0");
    }).join("");
  }

  function sourceOwnedPromptFingerprint(value) {
    var digest = sha256Ascii(value);
    return digest ? `${value.length}:${digest}` : "";
  }

  function gatewayUrlForPage() {
    var scheme = url.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}//${url.host}`;
  }

  function seedComposerDrafts() {
    if (!examples.length || !window.localStorage) return;
    var gatewayUrl = gatewayUrlForPage();
    var suffix = encodeURIComponent(gatewayUrl.trim() || "default").slice(0, 240);
    var storageKey = `openclaw.control.chatComposer.v1:${suffix}`;
    var markerKey = `bionemo.demoDraftSeed.v3:${suffix}`;
    var previousMarkerKey = `bionemo.demoDraftSeed.v2:${suffix}`;
    var legacyMarkerKey = `bionemo.demoDraftSeed.v1:${suffix}`;
    try {
      if (window.localStorage.getItem(markerKey) === "1") return;
      var upgradingFromV2 = window.localStorage.getItem(previousMarkerKey) === "1";
      var upgradingFromV1 = !upgradingFromV2 && window.localStorage.getItem(legacyMarkerKey) === "1";
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
        var sessionStorageKey = `${example.key}\u0000agent:${example.agentId}`;
        var hasExisting = Object.prototype.hasOwnProperty.call(parsed.sessions, sessionStorageKey);
        var existing = parsed.sessions[sessionStorageKey];
        var validExisting = existing && typeof existing === "object" && !Array.isArray(existing) ? existing : {};
        var previousSourcePromptFingerprint = previousSourceOwnedPromptFingerprints[example.key];
        var hasPreviousSourcePrompt = typeof previousSourcePromptFingerprint === "string";
        if (hasExisting) {
          // Replace only an exact prior image-owned value. Preserve edits,
          // queues, timestamps, malformed user-owned records, and explicit
          // empty drafts without trying to infer intent from whitespace.
          if ((upgradingFromV2 || upgradingFromV1)
            && hasPreviousSourcePrompt
            && sourceOwnedPromptFingerprint(validExisting.draft) === previousSourcePromptFingerprint) {
            parsed.sessions[sessionStorageKey] = { ...validExisting, draft: example.prompt };
          }
          return;
        }
        // A missing previously seeded record represents a draft the user
        // deliberately cleared. Only definitions genuinely introduced after
        // that seed generation may consume a free native composer slot.
        if ((upgradingFromV2 && hasPreviousSourcePrompt)
          || (upgradingFromV1 && example.draftSeedGeneration === 1)) return;
        // OpenClaw retains at most 20 composer records on its next native
        // write. Existing records are user-owned and always take precedence;
        // fill only genuinely free slots in deterministic catalog order.
        if (storedSessionCount >= nativeComposerSessionCap) return;
        parsed.sessions[sessionStorageKey] = {
          draft: example.prompt,
          // New image records are deliberately older than every preserved
          // native record, so OpenClaw evicts an example before user state if
          // a later user session takes the store over its retention cap.
          updatedAt: exampleUpdatedAtBase + index,
        };
        storedSessionCount += 1;
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
