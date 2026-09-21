const test = require('node:test');
const assert = require('node:assert/strict');
const { patchFactory, ROUTING_NOTICE } = require('./scientific-tool-search-patch.cjs');

const fixture = `
const toolsListSection = \`Deferred tools (search to load; \\u2026 = has params, search first):\`;
const serverFilters = normalizeServerFilter(rawServerFilter);
const hasServerFilter = serverFilters.length > 0;
if (toolRegistry == null) return [];
`;

test('blocks only an empty scientific-ai-apps server enumeration', () => {
  const patched = patchFactory(fixture);
  assert.match(patched, /query\.trim\(\) === ""/);
  assert.match(patched, /serverFilters\.includes\("scientific-ai-apps"\)/);
  assert.match(patched, /scientific_catalog_listing_disabled: true/);
  assert.ok(patched.includes(ROUTING_NOTICE));
  assert.equal(patchFactory(patched), patched);
});

test('rejects an unknown pinned ToolSearch build', () => {
  assert.throws(() => patchFactory('const hasServerFilter = true;'), /Unsupported pinned/);
});
