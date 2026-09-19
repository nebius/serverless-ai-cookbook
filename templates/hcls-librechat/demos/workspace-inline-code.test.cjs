const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.env.TYPESCRIPT_MODULE || 'typescript');
const jsx = (type, props) => ({ type, props });
const moduleUnderTest = { exports: {} };
const compiled = ts.transpileModule(fs.readFileSync(`${__dirname}/../WorkspaceInlineCode.tsx`, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
vm.runInNewContext(compiled, { module: moduleUnderTest, exports: moduleUnderTest.exports, URL,
  require: (name) => name === 'react/jsx-runtime' ? { jsx, jsxs: jsx } : {} });
const { workspaceCodeHref, workspaceCodeLinks, WorkspaceCodeBlockLinks, default: Component } = moduleUnderTest.exports;

test('exact natural code-span URL becomes a same-origin link without changing text', () => {
  const text = '/demos?tab=workspace&path=scientist-07%2Faging-study-v34%2Ffinal&file=scientist-07%2Faging-study-v34%2Ffinal%2Freport.md';
  const output = Component({ children: text, className: 'unchanged' });
  assert.equal(output.type, 'a');
  assert.equal(output.props.href, text);
  assert.equal(output.props.target, '_blank');
  assert.equal(output.props.children.type, 'code');
  assert.equal(output.props.children.props.children, text);
  assert.equal(output.props.children.props.className, 'unchanged');
});

test('documented absolute mount/basename and Unicode links use existing normalization', () => {
  const text = '/demos?' + new URLSearchParams({ tab: 'workspace', path: '/workspace/papers', file: 'Å & data.csv' });
  assert.equal(workspaceCodeHref(text), text);
  assert.equal(workspaceCodeHref([text.slice(0, 10), text.slice(10)]), text);
});

test('ordinary code, external URLs and malformed workspace paths remain plain code', () => {
  for (const text of ['https://', 'https://example.org/demos?tab=workspace&path=x&file=y',
    '//example.org/demos?tab=workspace&path=x&file=y', 'javascript:alert(1)',
    '/demos?tab=apps&path=x&file=y', '/demos?tab=workspace&path=x',
    '/demos?tab=workspace&path=x&file=y&redirect=https://example.org',
    '/demos?tab=workspace&path=x&file=y&file=z', '/demos?tab=workspace&path=x&file=..%2Fz',
    '/demos?tab=workspace&path=x&file=%2Fetc%2Fpasswd', '/demos?tab=workspace&path=x&file=%00x',
    '/demos?tab=workspace&path=x&file=y#anchor', '/demos?tab=workspace&path=x&file=y\n', 'print(1)']) {
    assert.equal(workspaceCodeHref(text), undefined, text);
    assert.equal(Component({ children: text }).type, 'code', text);
  }
});

test('renderer patch targets both inline and fenced branches without replacing CodeBlock', () => {
  const patch = fs.readFileSync(`${__dirname}/../patch-client.mjs`, 'utf8');
  assert.match(patch, /markdown\.split\(inlineCode\)\.length !== 3/);
  assert.match(patch, /markdown\.replaceAll\(inlineCode/);
  assert.match(patch, /markdown\.split\(executableBlock\)\.length !== 2/);
  assert.match(patch, /markdown\.split\(readOnlyBlock\)\.length !== 2/);
  assert.match(patch, /blockIndex=\{blockIndex\}/);
  assert.match(patch, /allowExecution=\{canRunCode\}/);
  assert.match(patch, /allowExecution=\{false\}/);
  assert.match(fs.readFileSync(`${__dirname}/../Dockerfile`, 'utf8'), /COPY templates\/hcls-librechat\/WorkspaceInlineCode.tsx/);
});

test('six real natural fenced URL lines gain adjacent links without altering code', () => {
  const names = ['aloha_recorded_nonvideo.npz', 'aloha_recorded_nonvideo.h5',
    'aloha_recorded_nonvideo.zip', 'aloha_recorded_nonvideo.sqlite', 'comparison_results.json', 'report.md'];
  const lines = names.map((name) => '/demos?tab=workspace&path=%2Fworkspace%2Fscientist-10%2Fanalysis-export-v43&file=' + name);
  const text = lines.join('\n') + '\n';
  const original = { type: 'CodeBlock', props: { codeChildren: text, allowExecution: false } };
  const output = WorkspaceCodeBlockLinks({ codeChildren: text, children: original });
  assert.equal(output.props.children[0], original);
  assert.equal(original.props.codeChildren, text);
  const nav = output.props.children[1];
  assert.equal(nav.type, 'nav');
  assert.equal(nav.props['aria-label'], 'Workspace files');
  const links = nav.props.children.props.children.map((li) => li.props.children);
  assert.deepEqual(Array.from(links, (link) => link.props.href), lines);
  assert.deepEqual(Array.from(links, (link) => link.props.children), names);
  for (const link of links) {
    assert.equal(link.type, 'a');
    assert.equal(link.props.target, '_blank');
    assert.equal(link.props.rel, 'noopener noreferrer');
  }
});

test('ordinary and mixed fenced code never expands URLs or rewrites text', () => {
  const valid = '/demos?tab=workspace&path=scientist-10&file=report.md';
  for (const text of ['print(1)\n', `print(1)\n${valid}\n`, `curl '${valid}'\n`,
    ` ${valid}\n`, `- ${valid}\n`, `https://example.org${valid}\n`,
    `${valid}\n/demos?tab=workspace&path=x&file=..%2Fy\n`,
    `${valid}\n/demos?tab=workspace&path=x&file=%2Fetc%2Fpasswd\n`,
    `${valid}\n/demos?tab=workspace&path=x&file=y&redirect=https://example.org\n`]) {
    assert.equal(workspaceCodeLinks(text).length, 0, text);
    const original = { type: 'CodeBlock', props: { codeChildren: text } };
    assert.equal(WorkspaceCodeBlockLinks({ codeChildren: text, children: original }).props.children, original);
  }
  assert.equal(workspaceCodeLinks({ props: { children: valid } }).length, 0);
});

test('CRLF, Unicode filenames and split string children retain exact authenticated href', () => {
  const url = '/demos?' + new URLSearchParams({ tab: 'workspace', path: '/workspace/papers', file: 'Å & data.csv' });
  const links = workspaceCodeLinks([url.slice(0, 20), url.slice(20), '\r\n']);
  assert.equal(links.length, 1);
  assert.equal(links[0].href, url);
  assert.equal(links[0].label, 'Å & data.csv');
});
