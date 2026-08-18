import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import vm from "node:vm";
import plugin from "../openclaw-plugin/index.mjs";
import {
  createNotebookHandler,
  NOTEBOOK_CATALOG,
  NOTEBOOK_MAX_BYTES,
  NOTEBOOK_ROUTE_PREFIX,
  notebookChatPath,
  publicNotebookCatalog,
  __test as notebookInternals,
} from "../openclaw-plugin/src/notebooks.mjs";
import { __test as uiInternals } from "../openclaw-plugin/src/ui.mjs";

const recipe = new URL("../", import.meta.url);
const notebookRoot = new URL("workspace/notebooks/", recipe);

function fakeApi() {
  const captured = { routes: [], controls: [], tools: [], hooks: [] };
  return {
    captured,
    logger: { info() {}, error() {} },
    registerTool(value) { captured.tools.push(value); },
    registerHttpRoute(value) { captured.routes.push(value); },
    on(event, handler) { captured.hooks.push({ event, handler }); },
    session: { controls: { registerControlUiDescriptor(value) { captured.controls.push(value); } } },
  };
}

function response() {
  const chunks = [];
  return {
    chunks,
    writeHead(status, headers) { this.status = status; this.headers = headers; },
    end(value) { if (value) chunks.push(Buffer.from(value)); },
    body() { return Buffer.concat(chunks); },
  };
}

function request(method, pathname) {
  return { method, url: `https://workbench.example${pathname}` };
}

test("four fixed image-baked notebooks are nbformat 4, empty-output, bounded, and catalog-synchronized", async () => {
  assert.equal(NOTEBOOK_CATALOG.length, 4);
  assert.equal(new Set(NOTEBOOK_CATALOG.map(({ slug }) => slug)).size, 4);
  assert.equal(new Set(NOTEBOOK_CATALOG.map(({ file }) => file)).size, 4);
  assert.equal(new Set(NOTEBOOK_CATALOG.map(({ sessionKey }) => sessionKey)).size, 4);
  assert.equal(new Set(NOTEBOOK_CATALOG.map(({ sessionLabel }) => sessionLabel)).size, 4);
  assert.equal(NOTEBOOK_CATALOG.every(({ sessionKey }) => sessionKey.startsWith("agent:bionemo:dashboard:")), true);
  assert.equal(NOTEBOOK_CATALOG.filter(({ optionalTavily }) => optionalTavily).length, 1);
  assert.equal(NOTEBOOK_CATALOG.at(-1).slug, "bulk-openfold2-five-proteins");

  for (const definition of NOTEBOOK_CATALOG) {
    const body = await readFile(new URL(definition.file, notebookRoot));
    assert.ok(body.length < NOTEBOOK_MAX_BYTES, definition.file);
    const value = JSON.parse(body);
    const validated = notebookInternals.validatedNotebook(value, definition);
    assert.equal(value.nbformat, 4);
    assert.equal(validated.metadata.id, definition.slug);
    assert.equal(validated.metadata.title, definition.title);
    assert.equal(validated.metadata.prompt, definition.prompt);
    assert.deepEqual(validated.metadata.steps, definition.steps);
    assert.ok(value.cells.length >= 3);
    assert.equal(value.cells.every((cell) => cell.cell_type !== "code" || (Array.isArray(cell.outputs) && cell.outputs.length === 0)), true);
    assert.equal(body.includes(Buffer.from("tvly-")), false);
  }
});

test("dashboard shows all four open notebooks first with view, run, and download actions", () => {
  const html = uiInternals.dashboardHtml("notebook-nonce");
  const publicCatalog = publicNotebookCatalog();
  assert.match(html, /<section class="panel"><h2>4 open demo notebooks<\/h2>/u);
  assert.ok(html.indexOf("4 open demo notebooks") < html.indexOf("Start an end-to-end demo"));
  assert.match(html, /Open notebook/u);
  assert.match(html, /Run in chat/u);
  assert.match(html, /Download \.ipynb/u);
  for (const definition of NOTEBOOK_CATALOG) {
    const publicEntry = publicCatalog.find(({ slug }) => slug === definition.slug);
    assert.ok(publicEntry);
    assert.ok(html.includes(publicEntry.viewPath));
    assert.ok(html.includes(publicEntry.downloadPath));
    assert.ok(html.includes(publicEntry.chatPath.replaceAll("&", "\\u0026")) || html.includes(publicEntry.chatPath));
    assert.ok(html.includes(definition.title));
    assert.ok(html.includes(definition.prompt));
  }
  const script = html.match(/<script nonce="[^"]+">([\s\S]+)<\/script>/u)?.[1];
  assert.ok(script);
  assert.doesNotThrow(() => new vm.Script(script));
});

test("plugin publishes the notebook surface as a public same-origin prefix route", () => {
  const api = fakeApi();
  plugin.register(api);
  const route = api.captured.routes.find(({ path: routePath }) => routePath === NOTEBOOK_ROUTE_PREFIX);
  assert.deepEqual({ auth: route.auth, match: route.match }, { auth: "plugin", match: "prefix" });
});

test("notebook viewer escapes cells, omits execution, and links exact download and chat draft", async () => {
  const handler = createNotebookHandler({ root: fileURLToPath(notebookRoot), nonceFactory: () => "fixed-notebook-nonce" });
  for (const definition of NOTEBOOK_CATALOG) {
    const res = response();
    await handler(request("GET", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}`), res);
    const html = res.body().toString("utf8");
    assert.equal(res.status, 200);
    assert.match(res.headers["Content-Type"], /^text\/html/u);
    assert.match(res.headers["Content-Security-Policy"], /default-src 'none'/u);
    assert.match(res.headers["Content-Security-Policy"], /style-src 'nonce-fixed-notebook-nonce'/u);
    assert.doesNotMatch(res.headers["Content-Security-Policy"], /script-src/u);
    assert.match(html, /Read-only guided notebook/u);
    assert.match(html, /Cells are not executed in this page/u);
    assert.ok(html.includes(notebookChatPath(definition).replaceAll("&", "&#38;")));
    assert.ok(html.includes(`${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}.ipynb`));
    assert.doesNotMatch(html, /<script/iu);
    assert.doesNotMatch(html, /<iframe/iu);
  }
});

test("notebook downloads round-trip exactly and HEAD emits headers without a body", async () => {
  const handler = createNotebookHandler({ root: fileURLToPath(notebookRoot), nonceFactory: () => "nonce" });
  for (const definition of NOTEBOOK_CATALOG) {
    const source = await readFile(new URL(definition.file, notebookRoot));
    const download = response();
    await handler(request("GET", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}.ipynb`), download);
    assert.equal(download.status, 200);
    assert.equal(download.headers["Content-Type"], "application/x-ipynb+json; charset=utf-8");
    assert.equal(download.headers["Content-Disposition"], `attachment; filename="${definition.file}"`);
    assert.deepEqual(download.body(), source);

    const head = response();
    await handler(request("HEAD", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}.ipynb`), head);
    assert.equal(head.status, 200);
    assert.equal(head.headers["Content-Length"], source.length);
    assert.equal(head.body().length, 0);
  }
});

test("HEAD viewer responses preserve representation headers without emitting HTML", async () => {
  const handler = createNotebookHandler({ root: fileURLToPath(notebookRoot), nonceFactory: () => "head-nonce" });
  const definition = NOTEBOOK_CATALOG[0];
  const get = response();
  await handler(request("GET", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}`), get);
  const head = response();
  await handler(request("HEAD", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}`), head);
  assert.equal(head.status, 200);
  assert.equal(head.headers["Content-Type"], "text/html; charset=utf-8");
  assert.equal(head.headers["Content-Length"], get.body().length);
  assert.equal(head.body().length, 0);
});

test("notebook route rejects unknown paths, traversal, methods, stored output, links, and oversize content", async (t) => {
  const handler = createNotebookHandler({ root: fileURLToPath(notebookRoot) });
  for (const pathname of [
    `${NOTEBOOK_ROUTE_PREFIX}/unknown`,
    `${NOTEBOOK_ROUTE_PREFIX}/../AGENTS.md`,
    `${NOTEBOOK_ROUTE_PREFIX}/egfr-research-drug-demo.json`,
    `${NOTEBOOK_ROUTE_PREFIX}/egfr-research-drug-demo/extra`,
  ]) {
    const res = response();
    await handler(request("GET", pathname), res);
    assert.equal(res.status, 404, pathname);
  }
  const method = response();
  await handler(request("POST", `${NOTEBOOK_ROUTE_PREFIX}/egfr-research-drug-demo`), method);
  assert.equal(method.status, 405);
  assert.equal(method.headers.Allow, "GET, HEAD");

  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-notebooks-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const definition = NOTEBOOK_CATALOG[0];
  const valid = JSON.parse(await readFile(new URL(definition.file, notebookRoot), "utf8"));
  valid.cells.push({
    cell_type: "code",
    execution_count: null,
    id: "injected-stored-output",
    metadata: {},
    outputs: [{ output_type: "stream", name: "stdout", text: ["unsafe"] }],
    source: ["print('must not render')"],
  });
  await writeFile(path.join(root, definition.file), `${JSON.stringify(valid)}\n`);
  let res = response();
  await createNotebookHandler({ root })(request("GET", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}`), res);
  assert.equal(res.status, 503);

  await rm(path.join(root, definition.file));
  await symlink(fileURLToPath(new URL(definition.file, notebookRoot)), path.join(root, definition.file));
  res = response();
  await createNotebookHandler({ root })(request("GET", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}`), res);
  assert.equal(res.status, 503);

  await rm(path.join(root, definition.file));
  await writeFile(path.join(root, definition.file), Buffer.alloc(NOTEBOOK_MAX_BYTES + 1, 32));
  res = response();
  await createNotebookHandler({ root })(request("GET", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}`), res);
  assert.equal(res.status, 503);

  const linkedRoot = `${root}-link`;
  t.after(() => rm(linkedRoot, { force: true }));
  await symlink(root, linkedRoot);
  res = response();
  await createNotebookHandler({ root: linkedRoot })(request("GET", `${NOTEBOOK_ROUTE_PREFIX}/${definition.slug}`), res);
  assert.equal(res.status, 503);
});

test("cell rendering treats notebook HTML and script content only as escaped text", () => {
  const definition = NOTEBOOK_CATALOG[0];
  const parsed = notebookInternals.validatedNotebook({
    nbformat: 4,
    nbformat_minor: 5,
    metadata: { bionemo: { id: definition.slug, title: definition.title, prompt: definition.prompt, steps: definition.steps } },
    cells: [{ cell_type: "markdown", metadata: {}, source: ["<script>alert('x')</script> & content"] }],
  }, definition);
  const html = notebookInternals.notebookHtml("nonce", definition, parsed);
  assert.doesNotMatch(html, /<script>alert/iu);
  assert.match(html, /&#60;script&#62;alert\(&#39;x&#39;\)&#60;\/script&#62; &#38; content/u);
});
