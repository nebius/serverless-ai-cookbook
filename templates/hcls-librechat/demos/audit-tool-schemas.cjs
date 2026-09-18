// Run inside the pinned LibreChat image; no credentials or model calls required.
const fs = require('node:fs');
const { createRequire } = require('node:module');
const appRequire = createRequire('/app/package.json');
const { formatMCPServerTools } = appRequire('@librechat/api');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const formatted = formatMCPServerTools('bionemo-models', input.tools);
const bytes = (value) => Buffer.byteLength(JSON.stringify(value));
const rows = input.tools.map((tool) => {
  const value = formatted[`${tool.name}_mcp_bionemo-models`];
  return { name: tool.name, original_bytes: bytes(tool.inputSchema),
    serialized_bytes: bytes(value), parameters_bytes: bytes(value.function.parameters),
    root_definitions: Object.keys(tool.inputSchema.$defs || {}).length };
}).sort((a, b) => b.serialized_bytes - a.serialized_bytes);
const output = { input_total_bytes: bytes(input), serialized_total_bytes: bytes(formatted), rows };
async function main() {
  const { createCachedTokenCounter } = appRequire('@librechat/api');
  const { SystemMessage } = appRequire('@langchain/core/messages');
  const counter = await createCachedTokenCounter('o200k_base');
  const { Tokenizer } = appRequire('ai-tokenizer');
  const encoding = await import(appRequire.resolve('ai-tokenizer/encoding/o200k_base'));
  const exact = new Tokenizer(encoding);
  const started = performance.now();
  for (const row of rows) {
    const serialized = JSON.stringify(formatted[`${row.name}_mcp_bionemo-models`]);
    row.pinned_token_count = counter(new SystemMessage(serialized));
    const fullStarted = performance.now();
    row.full_tokenizer_count = exact.count(serialized);
    row.full_tokenizer_ms = Math.round((performance.now() - fullStarted) * 1000) / 1000;
  }
  output.measurement_ms = Math.round((performance.now() - started) * 1000) / 1000;
  output.pinned_total_tokens_before_multiplier = rows.reduce((n, row) => n + row.pinned_token_count, 0);
  output.full_total_tokens = rows.reduce((n, row) => n + row.full_tokenizer_count, 0);
  if (process.argv[3]) fs.writeFileSync(process.argv[3], JSON.stringify(output, null, 2) + '\n');
  console.log(JSON.stringify(output, null, 2));
}
main().catch((error) => { console.error(error.message); process.exitCode = 1; });
