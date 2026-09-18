const test = require('node:test');
const assert = require('node:assert/strict');
const count = require('./scientific-token-count.cjs');
test('long text uses bounded calls, not its byte length', () => {
  const sizes = [];
  const text = 'Scientific tool schema with properties. '.repeat(5000);
  const measured = count(text, { count(chunk) { sizes.push(chunk.length); return Math.ceil(chunk.length / 4); } });
  assert.ok(sizes.length > 1);
  assert.ok(sizes.every((size) => size <= 4096));
  assert.ok(measured < text.length / 2);
  assert.ok(measured >= text.length / 4);
});
test('Unicode surrogate pairs are never split between tokenizer calls', () => {
  const text = 'a'.repeat(4095) + '🧬'.repeat(9000);
  count(text, { count(chunk) {
    assert.ok(!/[\uD800-\uDBFF]$/.test(chunk));
    assert.ok(!/^[\uDC00-\uDFFF]/.test(chunk));
    return chunk.length;
  } });
});
test('unavailable or failing tokenizer retains conservative byte fallback', () => {
  const text = 'Ä🧬'.repeat(5000);
  assert.equal(count(text), Buffer.byteLength(text));
  assert.equal(count(text, { count() { throw new Error('unavailable'); } }), Buffer.byteLength(text));
});
