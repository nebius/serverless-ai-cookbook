const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.env.TYPESCRIPT_MODULE || 'typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const source = fs.readFileSync(`${__dirname}/Demos.tsx`, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exported = {};
vm.runInNewContext(compiled, { exports: exported,
  require: (name) => name === 'react' || name === 'react/jsx-runtime' ? require(name)
    : name === 'react-router-dom' ? { Link: ({ to, children, ...props }) => React.createElement('a', { href: to, ...props }, children) } : {} });
const render = (summaries) => renderToStaticMarkup(React.createElement(exported.CompletedStudySummaries, { summaries }));

test('actual React rendering retains exact keyed rows and verified source link', () => {
  const text = 'profile_id: profile-000 | clinician_model: GLM | run_id: first | overall_score: 4.325\n' +
    'profile_id: profile-032 | clinician_model: GLM | run_id: second | overall_score: 4.55\n';
  const result = render([{ source_step: 'analysis', state: 'verified', text,
    artifact_name: 'steps/analysis/customer-summary.json', sha256: 'a'.repeat(64),
    download_url: '/demos?tab=workspace&file=customer-summary.json' }]);
  assert.ok(result.includes(text));
  assert.match(result, /Saved measurements · not chat recomputation/);
  assert.match(result, /href="\/demos\?tab=workspace&amp;file=customer-summary.json"/);
  assert.match(result, /SHA256 a{64}/);
  assert.match(source, /<CompletedStudySummaries summaries=\{study\.completion_summaries\}/);
});
test('older studies have no new empty summary panel', () => {
  assert.equal(render(undefined), '');
  assert.equal(render([]), '');
});
test('unavailable or oversized preview exposes notice and full artifact, not unverified text', () => {
  const result = render([{ source_step: 'analysis', state: 'unavailable', text: 'MUST NOT DISPLAY',
    notice: 'No rows are truncated. Download full summary.', download_url: '/demos?tab=workspace&file=full.json' }]);
  assert.ok(!result.includes('MUST NOT DISPLAY'));
  assert.match(result, /No rows are truncated/);
  assert.match(result, /href=/);
});
test('literal measured text is rendered as text, never interpreted as markup', () => {
  const result = render([{ source_step: 'analysis', state: 'verified', text: '<script>unchanged</script>\noverall_score: unavailable' }]);
  assert.match(result, /&lt;script&gt;unchanged&lt;\/script&gt;/);
  assert.match(result, /overall_score: unavailable/);
});
