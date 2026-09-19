const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { pathToFileURL } = require('node:url');
const modules = process.env.LIBRECHAT_NODE_MODULES || '/app/node_modules';
const ts = require(modules + '/typescript');
const React = require(modules + '/react');
const { renderToStaticMarkup } = require(modules + '/react-dom/server');
const compiled = ts.transpileModule(fs.readFileSync(`${__dirname}/../WorkspaceInlineCode.tsx`, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
}).outputText;
const moduleUnderTest = { exports: {} };
vm.runInNewContext(compiled, { module: moduleUnderTest, exports: moduleUnderTest.exports, URL,
  require: (name) => require(modules + '/' + name) });
const { workspaceCodeLinks, WorkspaceCodeBlockLinks } = moduleUnderTest.exports;

test('actual pinned auto-highlighting pipeline retains all six and seven workspace links', async () => {
  const { default: Markdown } = await import(pathToFileURL(modules + '/react-markdown/index.js'));
  const { default: highlight } = await import(pathToFileURL(modules + '/rehype-highlight/index.js'));
  const source = ts.createSourceFile('languages.ts', fs.readFileSync('/app/client/src/utils/languages.ts', 'utf8'), ts.ScriptTarget.Latest);
  let subset;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'langSubset') {
      subset = Array.from(node.initializer.elements, (entry) => entry.text);
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert(subset?.includes('perl'));
  const config = fs.readFileSync('/app/client/src/components/Chat/Messages/Content/markdownConfig.ts', 'utf8');
  assert.match(config, /rehypeHighlight, \{ detect: true, ignoreMissing: true, subset: langSubset \}/);
  const originalNames = ['aloha_recorded_nonvideo.npz', 'aloha_recorded_nonvideo.h5',
    'aloha_recorded_nonvideo.zip', 'aloha_recorded_nonvideo.sqlite', 'comparison_results.json', 'report.md'];
  const finalNames = [...originalNames.slice(0, 4), 'source_reference.npz', 'comparison_results.final.json', 'report.final.md'];
  for (const names of [originalNames, finalNames]) {
    const text = names.map((name) => '/demos?tab=workspace&path=%2Fworkspace%2Fscientist-10%2Fanalysis-export-v43&file=' + name).join('\n') + '\n';
    let observed;
    function Code({ children, className }) {
      observed = { children, className };
      return React.createElement(WorkspaceCodeBlockLinks, { codeChildren: children },
        React.createElement('code', { className }, children));
    }
    const html = renderToStaticMarkup(React.createElement(Markdown, {
      rehypePlugins: [[highlight, { detect: true, ignoreMissing: true, subset }]], components: { code: Code },
    }, '```\n' + text + '```'));
    assert.match(observed.className, /language-perl/);
    assert(observed.children.some((child) => React.isValidElement(child) && child.type === 'span'));
    assert.equal(workspaceCodeLinks(observed.children).length, names.length);
    assert.equal((html.match(/<a /g) || []).length, names.length);
    const original = renderToStaticMarkup(React.createElement('code', { className: observed.className }, observed.children));
    assert(html.includes(original), 'original highlighted content is unchanged');
    assert(html.includes('aria-label="Workspace files"'));
  }
});

test('recognition refuses arbitrary React elements and mixed highlighted code', () => {
  const url = '/demos?tab=workspace&path=scientist-10&file=report.md';
  for (const child of [React.createElement('a', { href: url }, url),
    React.createElement('span', { onClick: () => {} }, url),
    React.createElement('span', { dangerouslySetInnerHTML: { __html: url } }),
    React.createElement(() => url, {}), [React.createElement('span', {}, 'print(1)\n'), url]]) {
    assert.equal(workspaceCodeLinks(child).length, 0);
  }
});
