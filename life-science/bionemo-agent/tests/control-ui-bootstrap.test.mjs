import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { NOTEBOOK_CATALOG } from "../openclaw-plugin/src/notebooks.mjs";
import { CONTROL_UI_BOOTSTRAP_NAME, prepareControlUi } from "../runtime/prepare-control-ui.mjs";

const bootstrapUrl = new URL("../runtime/control-ui-default-session.js", import.meta.url);
const defaultDemoPrompt = NOTEBOOK_CATALOG[0].prompt;

test("startup draft is the exact Tavily-enabled first notebook prompt", async () => {
  const firstNotebook = JSON.parse(await readFile(new URL(`../workspace/notebooks/${NOTEBOOK_CATALOG[0].file}`, import.meta.url), "utf8"));
  assert.equal(defaultDemoPrompt, firstNotebook.metadata.bionemo.prompt);
  assert.equal(firstNotebook.metadata.bionemo.optionalTavily, true);
  assert.match(defaultDemoPrompt, /use_tavily=true/u);
});

async function runBootstrap(href) {
  const source = await readFile(bootstrapUrl, "utf8");
  const location = new URL(href);
  const calls = [];
  const history = {
    state: { retained: true },
    replaceState(state, title, next) {
      calls.push({ state, title, next });
    },
  };
  vm.runInNewContext(source, { URL, window: { location, history } });
  return calls;
}

test("default-session bootstrap canonicalizes only first-entry BioNeMo routes", async () => {
  const rootCalls = await runBootstrap("https://workbench.example/");
  assert.equal(rootCalls.length, 1);
  assert.deepEqual(rootCalls[0].state, { retained: true });
  assert.equal(rootCalls[0].title, "");
  const rootUrl = new URL(rootCalls[0].next, "https://workbench.example");
  assert.equal(rootUrl.pathname, "/chat");
  assert.equal(rootUrl.searchParams.get("session"), "agent:bionemo:main");
  assert.equal(rootUrl.searchParams.get("draft"), defaultDemoPrompt);

  const themedCalls = await runBootstrap("https://workbench.example/?theme=dark#token=kept");
  assert.equal(themedCalls.length, 1);
  const themedUrl = new URL(themedCalls[0].next, "https://workbench.example");
  assert.equal(themedUrl.pathname, "/chat");
  assert.equal(themedUrl.searchParams.get("theme"), "dark");
  assert.equal(themedUrl.searchParams.get("session"), "agent:bionemo:main");
  assert.equal(themedUrl.searchParams.get("draft"), defaultDemoPrompt);
  assert.equal(themedUrl.hash, "#token=kept");

  const legacyCalls = await runBootstrap("https://workbench.example/chat?session=main");
  assert.equal(legacyCalls.length, 1);
  const legacyUrl = new URL(legacyCalls[0].next, "https://workbench.example");
  assert.equal(legacyUrl.pathname, "/chat");
  assert.equal(legacyUrl.searchParams.get("session"), "agent:bionemo:main");
  assert.equal(legacyUrl.searchParams.get("draft"), defaultDemoPrompt);

  assert.deepEqual(await runBootstrap("https://workbench.example/chat?session=main&draft=kept"), [
    { state: { retained: true }, title: "", next: "/chat?session=agent%3Abionemo%3Amain&draft=kept" },
  ]);
  assert.deepEqual(await runBootstrap("https://workbench.example/?draft=kept&theme=light"), [
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
    assert.deepEqual(await runBootstrap(href), [], href);
  }
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
  assert.equal(await readFile(path.join(targetRoot, CONTROL_UI_BOOTSTRAP_NAME), "utf8"), await readFile(bootstrapUrl, "utf8"));
});
