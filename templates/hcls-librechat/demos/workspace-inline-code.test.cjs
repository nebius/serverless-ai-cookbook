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
const { workspaceCodeHref, default: Component } = moduleUnderTest.exports;

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

test('renderer patch targets both existing inline branches and leaves code blocks intact', () => {
  const patch = fs.readFileSync(`${__dirname}/../patch-client.mjs`, 'utf8');
  assert.match(patch, /markdown\.split\(inlineCode\)\.length !== 3/);
  assert.match(patch, /markdown\.replaceAll\(inlineCode/);
  assert.match(fs.readFileSync(`${__dirname}/../Dockerfile`, 'utf8'), /COPY templates\/hcls-librechat\/WorkspaceInlineCode.tsx/);
});
