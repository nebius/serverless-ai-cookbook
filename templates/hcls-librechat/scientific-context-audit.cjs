// Opt-in qualification diagnostics: sizes and counters only, never prompts,
// reasoning, arguments, tool results, credentials or signed artifact URLs.
const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const bytes = (value) => Buffer.byteLength(typeof value === 'string' ? value : JSON.stringify(value ?? null));
function persist(destination, record) {
  // Append/rename are unreliable on an object-storage mount. Each event is a
  // complete immutable file, with a convenient directly-written latest view.
  const directory = destination + '.events';
  fs.mkdirSync(directory, { recursive: true });
  const serialized = JSON.stringify(record) + '\n';
  const target = path.join(directory, `${Date.now()}-${randomUUID()}.json`);
  fs.writeFileSync(target, serialized, { mode: 0o600 });
  if (fs.readFileSync(target, 'utf8') !== serialized) throw new Error('AuditReadbackMismatch');
  fs.writeFileSync(destination, serialized, { mode: 0o600 });
}
function audit(context) {
  const destination = process.env.SCIENTIFIC_CONTEXT_AUDIT_PATH;
  if (!destination) return;
  try {
    const rows = (context.getActiveToolDefinitions() || []).map((def) => ({
      name: def.name, bytes: bytes({ type: 'function', function: {
        name: def.name, description: def.description ?? '', parameters: def.parameters ?? {} } }),
      counted_tokens: context.toolTokenCounts?.[def.name],
    }));
    const record = { kind: 'context', at: new Date().toISOString(), agent_id: context.agentId,
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
    persist(destination, record);
  } catch (error) {
    console.error('Scientific context-size audit failed:', error.code || error.name);
  }
}
audit.response = function (message, context) {
  const destination = process.env.SCIENTIFIC_CONTEXT_AUDIT_PATH;
  if (!destination) return;
  try {
    const usage = message?.usage_metadata ?? {};
    const numbers = (value) => Object.fromEntries(Object.entries(value ?? {})
      .filter(([, count]) => typeof count === 'number' && Number.isFinite(count)));
    const metadata = message?.response_metadata ?? {};
    persist(destination, { kind: 'provider_response', at: new Date().toISOString(),
      agent_id: context?.agentId,
      finish_reason: typeof metadata.finish_reason === 'string' ? metadata.finish_reason.slice(0, 80) : null,
      usage: numbers(usage), input_token_details: numbers(usage.input_token_details),
      output_token_details: numbers(usage.output_token_details),
      content_bytes: bytes(message?.content ?? ''), tool_calls: message?.tool_calls?.length ?? 0 });
  } catch (error) { console.error('Scientific provider-size audit failed:', error.code || error.name); }
};
module.exports = audit;
