// Execute in the pinned LibreChat image, without network, keys or model calls.
const { createRequire } = require('node:module');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const appRequire = createRequire('/app/package.json');
const api = appRequire('@librechat/api');
const { Constants } = appRequire('librechat-data-provider');
const options = require('../scientific-tool-options.cjs');
const count = require('../scientific-token-count.cjs');
async function main() {
  const { tools } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const catalog = api.formatMCPServerTools('bionemo-models', tools);
  const loaded = await api.loadToolDefinitions({ userId: 'test', agentId: 'test',
    tools: [`${Constants.mcp_all}_mcp_bionemo-models`],
    toolOptions: options({ tools: [`${Constants.mcp_all}_mcp_bionemo-models`] }),
    provider: 'openAI', deferredToolsEnabled: true, programmaticToolsEnabled: false,
    codeExecutionEnabled: false, mcpServerNames: ['bionemo-models'],
  }, { isBuiltInTool: () => false, getOrFetchMCPServerTools: async () => catalog });
  for (const name of ['cosmos3_nano_video_to_video', 'submit_cosmos3_lerobot_augmentation',
    'infer_phenoage_native', 'infer_parakeet_realtime_eou_120m_v1_native']) {
    assert.equal(loaded.toolRegistry.get(name + '_mcp_bionemo-models')?.defer_loading, true, name);
  }
  assert.notEqual(loaded.toolRegistry.get('get_model_schema_mcp_bionemo-models')?.defer_loading, true);
  assert.equal(loaded.hasDeferredTools, true);
  assert.ok(loaded.toolDefinitions.some((tool) => tool.name === 'tool_search'));
  const { Tokenizer } = appRequire('ai-tokenizer');
  const tokenizer = new Tokenizer(await import(appRequire.resolve('ai-tokenizer/encoding/o200k_base')));
  const inputs = [JSON.stringify(catalog).slice(0, 32000), 'DNA structure and protein synthesis. '.repeat(800),
    '生物医学の研究と🧬蛋白質 '.repeat(1500), 'ACGTCCGATTGCAATG'.repeat(2000)];
  const started = performance.now();
  const checks = inputs.map((text) => {
    const full = tokenizer.count(text);
    const bounded = count(text, tokenizer);
    assert.ok(bounded >= full, 'Bounded estimate must cover whole-tokenizer count in qualification fixtures');
    return { bytes: Buffer.byteLength(text), full, bounded };
  });
  console.log(JSON.stringify({ tool_definitions: loaded.toolDefinitions.length,
    tokenizer_checks: checks, tokenizer_ms: performance.now() - started }));
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
