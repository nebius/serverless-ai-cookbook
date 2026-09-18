const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const audit = require('./scientific-context-audit.cjs');
test('provider diagnostics retain counters, not private model text or credentials', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'scientific-audit-test-'));
  const destination = path.join(root, 'audit.jsonl');
  process.env.SCIENTIFIC_CONTEXT_AUDIT_PATH = destination;
  audit.response({ content: 'PRIVATE_TEXT', tool_calls: [{ args: 'PRIVATE_ARGS' }],
    usage_metadata: { input_tokens: 25, output_tokens: 8192, output_token_details: { reasoning: 8192 } },
    response_metadata: { finish_reason: 'length', api_key: 'PRIVATE_SECRET' } }, { agentId: 'fixture' });
  audit.response({ content: 'Next response', response_metadata: { finish_reason: 'stop' } }, {});
  const files = fs.readdirSync(destination + '.events');
  assert.equal(files.length, 2);
  const records = files.map(name => fs.readFileSync(path.join(destination + '.events', name), 'utf8'));
  assert.ok(records.every(record => !record.includes('PRIVATE_')));
  assert.ok(records.some(record => JSON.parse(record).finish_reason === 'length'));
  assert.equal(JSON.parse(fs.readFileSync(destination)).finish_reason, 'stop');
  delete process.env.SCIENTIFIC_CONTEXT_AUDIT_PATH;
});
