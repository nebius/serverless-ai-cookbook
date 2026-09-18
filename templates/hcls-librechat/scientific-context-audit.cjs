// Opt-in qualification diagnostics: sizes and counters only, never prompts,
// reasoning, arguments, tool results, credentials or signed artifact URLs.
const fs = require('node:fs');
const path = require('node:path');
const bytes = (value) => Buffer.byteLength(typeof value === 'string' ? value : JSON.stringify(value ?? null));
module.exports = function audit(context) {
  const destination = process.env.SCIENTIFIC_CONTEXT_AUDIT_PATH;
  if (!destination) return;
  try {
    const rows = (context.getActiveToolDefinitions() || []).map((def) => ({
      name: def.name, bytes: bytes({ type: 'function', function: {
        name: def.name, description: def.description ?? '', parameters: def.parameters ?? {} } }),
      counted_tokens: context.toolTokenCounts?.[def.name],
    }));
    const record = { at: new Date().toISOString(), agent_id: context.agentId,
      instructions_bytes: bytes(context.instructions ?? ''),
      additional_instructions_bytes: bytes(context.additionalInstructions ?? ''),
      stable_bytes: bytes(context.buildStableInstructionsString()),
      dynamic_bytes: bytes(context.buildDynamicInstructionsString()),
      tool_bytes: rows.reduce((n, row) => n + row.bytes, 0), tools: rows,
      calibration_ratio: context.calibrationRatio,
      counted_tool_tokens: context.toolSchemaTokens,
      counted_instruction_tokens: context.instructionTokens,
      reported_input_tokens: context.lastCallUsage?.input_tokens,
      reported_output_tokens: context.lastCallUsage?.output_tokens,
    };
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.appendFileSync(destination, JSON.stringify(record) + '\n', { mode: 0o600 });
  } catch (error) {
    console.error('Scientific context-size audit failed:', error.code || error.name);
  }
};
