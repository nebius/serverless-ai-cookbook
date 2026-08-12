import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { CONTROL_UI_BOOTSTRAP_NAME, prepareControlUi } from "../runtime/prepare-control-ui.mjs";

const bootstrapUrl = new URL("../runtime/control-ui-default-session.js", import.meta.url);

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
  assert.deepEqual(await runBootstrap("https://workbench.example/"), [
    { state: { retained: true }, title: "", next: "/chat?session=agent%3Abionemo%3Amain" },
  ]);
  assert.deepEqual(await runBootstrap("https://workbench.example/?theme=dark#token=kept"), [
    { state: { retained: true }, title: "", next: "/chat?theme=dark&session=agent%3Abionemo%3Amain#token=kept" },
  ]);
  assert.deepEqual(await runBootstrap("https://workbench.example/chat?session=main&draft=kept"), [
    { state: { retained: true }, title: "", next: "/chat?session=agent%3Abionemo%3Amain&draft=kept" },
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
