import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { NOTEBOOK_CATALOG } from "../openclaw-plugin/src/notebooks.mjs";
import { EXAMPLE_SESSIONS } from "../runtime/example-sessions.mjs";
import { CONTROL_UI_BOOTSTRAP_NAME, prepareControlUi, renderExampleSessionPrelude } from "../runtime/prepare-control-ui.mjs";

const bootstrapUrl = new URL("../runtime/control-ui-default-session.js", import.meta.url);
const defaultDemoPrompt = NOTEBOOK_CATALOG[0].prompt;

test("startup draft is the exact Tavily-enabled first notebook prompt", async () => {
  const firstNotebook = JSON.parse(await readFile(new URL(`../workspace/notebooks/${NOTEBOOK_CATALOG[0].file}`, import.meta.url), "utf8"));
  assert.equal(defaultDemoPrompt, firstNotebook.metadata.bionemo.prompt);
  assert.equal(firstNotebook.metadata.bionemo.optionalTavily, true);
  assert.match(defaultDemoPrompt, /use_tavily=true/u);
});

function composerStorageKey(href) {
  const url = new URL(href);
  const gatewayUrl = `${url.protocol === "https:" ? "wss:" : "ws:"}//${url.host}`;
  return `openclaw.control.chatComposer.v1:${encodeURIComponent(gatewayUrl).slice(0, 240)}`;
}

async function runBootstrap(href, { storage = new Map(), failWrites = false } = {}) {
  const source = `${renderExampleSessionPrelude()}${await readFile(bootstrapUrl, "utf8")}`;
  const location = new URL(href);
  const calls = [];
  const history = {
    state: { retained: true },
    replaceState(state, title, next) {
      calls.push({ state, title, next });
    },
  };
  const localStorage = {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) {
      if (failWrites) throw new Error("quota");
      storage.set(key, String(value));
    },
    removeItem(key) { storage.delete(key); },
  };
  vm.runInNewContext(source, { URL, window: { location, history, localStorage } });
  return { calls, storage };
}

async function runInteractiveBootstrap(href, { storage = new Map(), initialValue = "", sessionKey } = {}) {
  const source = `${renderExampleSessionPrelude()}${await readFile(bootstrapUrl, "utf8")}`;
  const location = new URL(href);
  const inputEvents = [];
  const listeners = new Map();
  const observerCallbacks = [];
  class FakeTextArea {
    constructor() { this.value = initialValue; }
    dispatchEvent(event) {
      inputEvents.push({ type: event.type, bubbles: event.bubbles, composed: event.composed, value: this.value });
      return true;
    }
  }
  class FakeEvent {
    constructor(type, options = {}) { this.type = type; this.bubbles = options.bubbles === true; this.composed = options.composed === true; }
  }
  class FakeMutationObserver {
    constructor(callback) { observerCallbacks.push(callback); }
    observe() {}
  }
  const textarea = new FakeTextArea();
  const pane = {
    state: { sessionKey: sessionKey || location.searchParams.get("session") },
    querySelector(selector) { return selector === ".agent-chat__composer-combobox > textarea" ? textarea : null; },
  };
  const document = {
    documentElement: {},
    querySelector(selector) { return selector === "openclaw-chat-pane" ? pane : null; },
  };
  const history = {
    state: null,
    pushState(_state, _title, next) { if (next) location.href = new URL(next, location).href; },
    replaceState(_state, _title, next) { if (next) location.href = new URL(next, location).href; },
  };
  const localStorage = {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); },
    removeItem(key) { storage.delete(key); },
  };
  const window = {
    location,
    history,
    localStorage,
    document,
    MutationObserver: FakeMutationObserver,
    HTMLTextAreaElement: FakeTextArea,
    Event: FakeEvent,
    queueMicrotask(callback) { callback(); },
    setTimeout(callback) { callback(); },
    addEventListener(type, callback) { listeners.set(type, callback); },
  };
  vm.runInNewContext(source, { URL, window });
  return { inputEvents, observerCallbacks, pane, storage, textarea };
}

test("default-session bootstrap canonicalizes only first-entry BioNeMo routes", async () => {
  const { calls: rootCalls } = await runBootstrap("https://workbench.example/");
  assert.equal(rootCalls.length, 1);
  assert.deepEqual(rootCalls[0].state, { retained: true });
  assert.equal(rootCalls[0].title, "");
  const rootUrl = new URL(rootCalls[0].next, "https://workbench.example");
  assert.equal(rootUrl.pathname, "/chat");
  assert.equal(rootUrl.searchParams.get("session"), "agent:bionemo:main");
  assert.equal(rootUrl.searchParams.get("draft"), defaultDemoPrompt);

  const { calls: themedCalls } = await runBootstrap("https://workbench.example/?theme=dark#token=kept");
  assert.equal(themedCalls.length, 1);
  const themedUrl = new URL(themedCalls[0].next, "https://workbench.example");
  assert.equal(themedUrl.pathname, "/chat");
  assert.equal(themedUrl.searchParams.get("theme"), "dark");
  assert.equal(themedUrl.searchParams.get("session"), "agent:bionemo:main");
  assert.equal(themedUrl.searchParams.get("draft"), defaultDemoPrompt);
  assert.equal(themedUrl.hash, "#token=kept");

  const { calls: legacyCalls } = await runBootstrap("https://workbench.example/chat?session=main");
  assert.equal(legacyCalls.length, 1);
  const legacyUrl = new URL(legacyCalls[0].next, "https://workbench.example");
  assert.equal(legacyUrl.pathname, "/chat");
  assert.equal(legacyUrl.searchParams.get("session"), "agent:bionemo:main");
  assert.equal(legacyUrl.searchParams.get("draft"), defaultDemoPrompt);

  assert.deepEqual((await runBootstrap("https://workbench.example/chat?session=main&draft=kept")).calls, [
    { state: { retained: true }, title: "", next: "/chat?session=agent%3Abionemo%3Amain&draft=kept" },
  ]);
  assert.deepEqual((await runBootstrap("https://workbench.example/?draft=kept&theme=light")).calls, [
    { state: { retained: true }, title: "", next: "/chat?draft=kept&theme=light&session=agent%3Abionemo%3Amain" },
  ]);
});

test("default-session bootstrap preserves explicit sessions and non-default routes", async () => {
  for (const href of [
    "https://workbench.example/?session=agent:other:main",
    "https://workbench.example/chat",
    "https://workbench.example/chat?session=agent:bionemo:research",
    "https://workbench.example/debug?session=main",
  ]) {
    assert.deepEqual((await runBootstrap(href)).calls, [], href);
  }
});

test("Control UI seeds four ready per-session drafts once without queues or sends", async () => {
  const href = "https://workbench.example/chat?session=agent:bionemo:dashboard:egfr-research-drug-demo";
  const storage = new Map();
  const first = await runBootstrap(href, { storage });
  assert.deepEqual(first.calls, []);
  const storageKey = composerStorageKey(href);
  const parsed = JSON.parse(storage.get(storageKey));
  assert.equal(parsed.version, 1);
  assert.equal(Object.keys(parsed.sessions).length, 4);
  for (const definition of EXAMPLE_SESSIONS) {
    const entry = parsed.sessions[`${definition.key}\u0000agent:bionemo`];
    assert.equal(entry.draft, definition.prompt);
    assert.equal(Object.hasOwn(entry, "queue"), false);
  }
  assert.equal(storage.get(storageKey.replace("openclaw.control.chatComposer.v1:", "bionemo.demoDraftSeed.v1:")), "1");

  const serialized = storage.get(storageKey);
  await runBootstrap(href, { storage });
  assert.equal(storage.get(storageKey), serialized, "a reload must not replace user-owned composer state");
});

test("Control UI draft seeding preserves existing edits and queues and fails closed on storage errors", async () => {
  const href = "https://workbench.example/chat?session=agent:bionemo:dashboard:compare-protein-structures";
  const storageKey = composerStorageKey(href);
  const firstKey = `${EXAMPLE_SESSIONS[0].key}\u0000agent:bionemo`;
  const storage = new Map([[storageKey, JSON.stringify({
    version: 1,
    sessions: {
      [firstKey]: { draft: "user edit", queue: [{ id: "preserved" }], updatedAt: 1 },
      "agent:bionemo:main\u0000agent:bionemo": { draft: "unrelated", updatedAt: 2 },
    },
  })]]);
  await runBootstrap(href, { storage });
  const parsed = JSON.parse(storage.get(storageKey));
  assert.equal(parsed.sessions[firstKey].draft, "user edit");
  assert.deepEqual(parsed.sessions[firstKey].queue, [{ id: "preserved" }]);
  assert.equal(parsed.sessions["agent:bionemo:main\u0000agent:bionemo"].draft, "unrelated");

  const malformed = new Map([[storageKey, "not-json"]]);
  await assert.doesNotReject(() => runBootstrap(href, { storage: malformed }));
  assert.equal(Object.keys(JSON.parse(malformed.get(storageKey)).sessions).length, 4);
  await assert.doesNotReject(() => runBootstrap(href, { failWrites: true }));
});

test("Control UI bridges a stored example draft through one native input event", async () => {
  const example = EXAMPLE_SESSIONS[0];
  const href = `https://workbench.example/chat?session=${encodeURIComponent(example.key)}`;
  const result = await runInteractiveBootstrap(href);
  assert.equal(result.textarea.value, example.prompt);
  assert.deepEqual(result.inputEvents, [{ type: "input", bubbles: true, composed: true, value: example.prompt }]);
  result.observerCallbacks[0]();
  assert.equal(result.inputEvents.length, 1, "subsequent UI mutations must not reapply the draft");
});

test("Control UI bridge preserves live edits and never resurrects removed or unrelated drafts", async () => {
  const example = EXAMPLE_SESSIONS[1];
  const href = `https://workbench.example/chat?session=${encodeURIComponent(example.key)}`;
  const edited = await runInteractiveBootstrap(href, { initialValue: "live user edit" });
  assert.equal(edited.textarea.value, "live user edit");
  assert.equal(edited.inputEvents.length, 0);

  const storageKey = composerStorageKey(href);
  const markerKey = storageKey.replace("openclaw.control.chatComposer.v1:", "bionemo.demoDraftSeed.v1:");
  const clearedStorage = new Map([
    [storageKey, JSON.stringify({ version: 1, sessions: {} })],
    [markerKey, "1"],
  ]);
  const cleared = await runInteractiveBootstrap(href, { storage: clearedStorage });
  assert.equal(cleared.textarea.value, "");
  assert.equal(cleared.inputEvents.length, 0);

  const unrelated = await runInteractiveBootstrap("https://workbench.example/chat?session=agent:other:main");
  assert.equal(unrelated.textarea.value, "");
  assert.equal(unrelated.inputEvents.length, 0);
});

test("Control UI preparation owns an unminified bootstrap loaded before OpenClaw", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-control-ui-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const sourceRoot = path.join(root, "source");
  const targetRoot = path.join(root, "target");
  await mkdir(path.join(sourceRoot, "assets"), { recursive: true });
  await writeFile(path.join(sourceRoot, "index.html"), '<html>\n  <head>\n    <script type="module" src="./assets/upstream.js"></script>\n  </head>\n</html>\n');
  await writeFile(path.join(sourceRoot, "assets", "upstream.js"), "export {};\n");

  await prepareControlUi({ sourceRoot, targetRoot, bootstrapPath: bootstrapUrl });

  const html = await readFile(path.join(targetRoot, "index.html"), "utf8");
  assert.ok(html.indexOf(`src="./${CONTROL_UI_BOOTSTRAP_NAME}"`) < html.indexOf('type="module"'));
  assert.equal((html.match(new RegExp(CONTROL_UI_BOOTSTRAP_NAME, "gu")) || []).length, 1);
  assert.equal(await readFile(path.join(targetRoot, "assets", "upstream.js"), "utf8"), "export {};\n");
  const preparedBootstrap = await readFile(path.join(targetRoot, CONTROL_UI_BOOTSTRAP_NAME), "utf8");
  assert.equal(preparedBootstrap, `${renderExampleSessionPrelude()}${await readFile(bootstrapUrl, "utf8")}`);
  assert.match(preparedBootstrap, /__BIONEMO_EXAMPLE_SESSIONS__/u);
  assert.doesNotMatch(preparedBootstrap, /tvly-[A-Za-z0-9]/u);
  assert.doesNotThrow(() => new vm.Script(preparedBootstrap));
});
