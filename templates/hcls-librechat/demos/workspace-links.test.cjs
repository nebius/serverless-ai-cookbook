const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.env.TYPESCRIPT_MODULE || 'typescript');

function render(query, entries) {
  const requests = [], downloads = [], navigation = [];
  const params = new URLSearchParams(query);
  const jsx = (type, props) => typeof type === 'function' ? type(props) : { type, props };
  const request = { getResponse: async (url) => {
    requests.push(url); return { data: 'exact bytes', headers: { 'content-type': 'text/plain' } };
  } };
  const dependencies = {
    react: { useState: (value) => [typeof value === 'function' ? value() : value, () => {}], useEffect: () => {} },
    'react/jsx-runtime': { jsx, jsxs: jsx, Fragment: 'fragment' },
    axios: {}, 'react-router-dom': { Link: 'Link', useSearchParams: () => [params, (value) => navigation.push(value)] },
    '@tanstack/react-query': { useQueryClient: () => ({ invalidateQueries: async () => {} }),
      useQuery: (key) => ({ isLoading: false, data: key[1] === 'settings' ? { configured: true }
        : key[1] === 'workspace' ? { info: { team_bucket_name: 'fixture' }, data: entries } : {} }) },
    '@librechat/client': { Button: 'Button', Input: 'Input' }, 'librechat-data-provider': { request },
    './scientific-comparison': {}, './scientific-run-display': {},
  };
  const module = { exports: {} };
  const source = ts.transpileModule(fs.readFileSync(`${__dirname}/Demos.tsx`, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(source, { module, exports: module.exports, require: (name) => dependencies[name],
    URLSearchParams, URL: { createObjectURL: () => 'blob:verified-download', revokeObjectURL: () => {} }, Blob,
    document: { createElement: () => ({ click() { downloads.push(this.download); } }) },
    setTimeout: (fn) => fn(), encodeURIComponent });
  const tree = module.exports.default();
  const elements = [];
  function visit(item) {
    if (!item || typeof item !== 'object') return;
    if (Array.isArray(item)) { item.forEach(visit); return; }
    elements.push(item); visit(item.props?.children);
  }
  visit(tree);
  return { elements, requests, downloads, navigation };
}

test('workspace deep-link selects the exact file and downloads through existing authenticated request client', async () => {
  const target = 'study/Å & data.csv';
  const page = render(new URLSearchParams({ tab: 'workspace', path: 'study', file: target }).toString(),
    [{ name: 'Å & data.csv', path: target, kind: 'file', size_bytes: 11 }]);
  const button = page.elements.find((item) => item.type === 'Button' && item.props.children === 'Download selected file');
  assert.ok(button);
  button.props.onClick();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(page.requests[0], '/api/scientific-demos/workspace/file?path=' + encodeURIComponent(target));
  assert.deepEqual(page.downloads, ['Å & data.csv']);
  assert.ok(page.elements.some((item) => item.type === 'code' && item.props.children === target));
});

test('missing selected files do not download and folder navigation preserves a usable deep-link', () => {
  const page = render('tab=workspace&path=study&file=study%2Fmissing.csv',
    [{ name: 'child', path: 'study/child', kind: 'directory' }]);
  assert.equal(page.elements.some((item) => item.props?.children === 'Download selected file'), false);
  assert.ok(page.elements.some((item) => item.props?.role === 'status'));
  const folder = page.elements.find((item) => item.type === 'button');
  folder.props.onClick();
  assert.equal(page.navigation[0].tab, 'workspace');
  assert.equal(page.navigation[0].path, 'study/child');
  assert.equal(page.navigation[0].file, undefined);
  assert.deepEqual(page.requests, []);
});
