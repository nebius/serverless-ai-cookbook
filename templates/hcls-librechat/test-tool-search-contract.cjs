// Run against the installed pinned package in the immutable workbench image.
// This proves existing search parameters; it does not replace its algorithm.
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const { performLocalSearch, ToolSearchToolSchema } = require(
  process.env.TOOL_SEARCH_MODULE || '/app/node_modules/@librechat/agents/dist/cjs/tools/ToolSearch.cjs');
const names = ['cosmos3_nano_transfer_video', 'cosmos3_nano_video_to_video',
  'cosmos3_nano_image_to_video', 'cosmos3_nano_text_to_video',
  'cosmos3_nano_generate_media_native', 'submit_cosmos3_lerobot_augmentation'];
const tools = names.map(name => ({ name: `${name}_mcp_bionemo-models`,
  description: 'Generate or transform scientific video and recorded robot media.',
  parameters: { type: 'object', properties: { input: { type: 'string' } } } }));

test('existing schema allows exact one-result name loading, unchanged defaults', () => {
  assert.equal(ToolSearchToolSchema.properties.max_results.minimum, 1);
  assert.equal(ToolSearchToolSchema.properties.max_results.default, 5);
  assert.equal(ToolSearchToolSchema.properties.max_results.maximum, 50);
  assert.ok(ToolSearchToolSchema.properties.mcp_server);
});

test('canonical and registered exact tool names import only the intended schema', () => {
  for (const name of names) {
    for (const query of [name, `${name}_mcp_bionemo-models`]) {
      const result = performLocalSearch(tools, query, ['name'], 1);
      assert.deepEqual(result.tool_references.map(row => row.tool_name), [`${name}_mcp_bionemo-models`]);
    }
  }
});

test('semantic discovery retains fuzzy multiple-result behavior', () => {
  const result = performLocalSearch(tools, 'recorded scientific video', ['name', 'description'], 5);
  assert.equal(result.tool_references.length, 5);
});

test('installed scientific guidance uses the existing bounded option', () => {
  const instructions = fs.readFileSync('/app/scientific-agent-instructions.md', 'utf8');
  // Set GUIDANCE_FILE when validating an unbuilt source candidate against the
  // pinned search dependency; fresh-image gate uses the actual installed file.
  const candidate = process.env.GUIDANCE_FILE ? fs.readFileSync(process.env.GUIDANCE_FILE, 'utf8') : instructions;
  assert.match(candidate, /max_results:1/);
  assert.match(candidate, /fields:\["name"\]/);
  assert.match(candidate, /known `mcp_server`/);
});
