(function normalizeBioNemoDefaultSession() {
  "use strict";

  var defaultDemoPrompt = "Run the backend-neutral research-first EGFR demo. Call bionemo_research_drug_demo exactly once with use_tavily=true, ack_research_only=true, ack_non_clinical=true, ack_non_commercial=true, ack_aup_accepted=true, and ack_no_safety_or_therapeutic_claims=true. I explicitly accept those five research-only acknowledgements. Do not call its Tavily, OpenFold2, MolMIM, or OpenFold3 steps separately. Report whether optional Tavily research ran, cite its sources if present, summarize every model step and confidence value, include every artifact viewerMarkdown link verbatim, and state the scientific limitations.";
  var url = new URL(window.location.href);
  var requestedSession = url.searchParams.get("session");
  var isRootDefault = url.pathname === "/" && (!requestedSession || requestedSession === "main");
  var isLegacyChatDefault = url.pathname === "/chat" && requestedSession === "main";

  if (!isRootDefault && !isLegacyChatDefault) return;

  url.pathname = "/chat";
  url.searchParams.set("session", "agent:bionemo:main");
  if (!url.searchParams.has("draft")) url.searchParams.set("draft", defaultDemoPrompt);
  window.history.replaceState(
    window.history.state,
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
})();
