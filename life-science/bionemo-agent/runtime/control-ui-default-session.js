(function normalizeBioNemoDefaultSession() {
  "use strict";

  var url = new URL(window.location.href);
  var requestedSession = url.searchParams.get("session");
  var isRootDefault = url.pathname === "/" && (!requestedSession || requestedSession === "main");
  var isLegacyChatDefault = url.pathname === "/chat" && requestedSession === "main";

  if (!isRootDefault && !isLegacyChatDefault) return;

  url.pathname = "/chat";
  url.searchParams.set("session", "agent:bionemo:main");
  window.history.replaceState(
    window.history.state,
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
})();
