const test = require('node:test');
const assert = require('node:assert/strict');
const options = require('./scientific-tool-options.cjs');
test('current and future typed model tools are deferred after mcp_all expansion', () => {
  const value = options({ tools: ['mcp_all_mcp_bionemo-models'], tool_options: {} });
  for (const name of ['cosmos3_nano_video_to_video', 'submit_cosmos3_lerobot_augmentation', 'future_typed_model']) {
    assert.equal(value[name + '_mcp_bionemo-models'].defer_loading, true);
  }
  assert.equal(value.get_model_schema_mcp_bionemo_models, undefined);
  assert.equal(value['get_model_schema_mcp_bionemo-models'], undefined);
  assert.equal(value['execute_command_mcp_environment-execution'], undefined);
});
test('existing tool options survive unchanged except deferred schema loading', () => {
  const name = 'future_typed_model_mcp_bionemo-models';
  const original = { allowed_callers: ['direct'], custom: 3 };
  const value = options({ tool_options: { [name]: original } });
  assert.deepEqual(value[name], { ...original, defer_loading: true });
  assert.deepEqual(original, { allowed_callers: ['direct'], custom: 3 });
});
