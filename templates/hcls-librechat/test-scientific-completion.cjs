const test = require('node:test');
const assert = require('node:assert/strict');
const mark = require('./scientific-completion.cjs');
test('reasoning-only or empty answers stay visibly incomplete', () => {
  for (const content of [[], [{ type: 'think', think: 'retained private reasoning' }],
    [{ type: 'text', text: '  ' }], [{ type: 'tool_call', tool_call: { name: 'submit', output: 'id' } }]]) {
    const response = { content };
    assert.equal(mark(response), true);
    assert.deepEqual(response.content.slice(0, -1), content);
    assert.match(response.content.at(-1).error, /open Runs/);
    assert.equal(response.finish_reason, undefined);
  }
});
test('visible answers, provider errors and actual media are unchanged', () => {
  for (const content of [[{ type: 'text', text: 'Saved report.' }],
    [{ type: 'error', error: 'Provider unavailable' }], [{ type: 'image_file', image_file: { file_id: 'x' } }]]) {
    const response = { content };
    assert.equal(mark(response), false);
    assert.equal(response.content, content);
  }
});
