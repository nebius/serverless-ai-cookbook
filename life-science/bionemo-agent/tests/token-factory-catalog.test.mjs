import assert from "node:assert/strict";
import test from "node:test";

import { configureOpenClaw, TOKEN_FACTORY_MODELS } from "../runtime/runtime-config.mjs";

test("Nemotron agent models retain their effective Token Factory context windows", () => {
  const contextWindows = Object.fromEntries(
    TOKEN_FACTORY_MODELS.map(({ id, contextWindow }) => [id, contextWindow]),
  );

  assert.equal(contextWindows["nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"], 262144);
  assert.equal(contextWindows["nvidia/Nemotron-3_5-Lightning"], 1048576);
  assert.equal(contextWindows["nvidia/nemotron-3-super-120b-a12b"], 262144);
  assert.equal(contextWindows["nvidia/Nemotron-3-Ultra-550b-a55b"], 1048576);
});

test("Nemotron 3 Super uses max_tokens on Token Factory and NVIDIA Build", () => {
  const config = {
    agents: { defaults: { model: {} } },
    models: {},
    tools: { alsoAllow: [], deny: ["bundle-mcp"] },
  };
  configureOpenClaw(config, { AGENT_PROVIDER: "nebius", NEBIUS_API_KEY: "test-only" });

  const tokenFactoryModels = config.models.providers.tokenfactory.models;
  const superModel = tokenFactoryModels.find(({ id }) => id === "nvidia/nemotron-3-super-120b-a12b");
  assert.deepEqual(superModel.compat, { maxTokensField: "max_tokens" });
  assert.equal(tokenFactoryModels.filter(({ compat }) => compat).length, 1);
  assert.deepEqual(config.models.providers.nvidia.models[0].compat, {
    maxTokensField: "max_tokens",
    requiresStringContent: true,
  });
});
