import assert from "node:assert/strict";
import test from "node:test";

import {
  configureOpenClaw,
  TOKEN_FACTORY_MODELS,
  TOKEN_FACTORY_QUALIFICATION,
  TOKEN_FACTORY_REJECTED_MODELS,
} from "../runtime/runtime-config.mjs";

test("qualified Nemotron agent models retain their effective Token Factory context windows", () => {
  const contextWindows = Object.fromEntries(
    TOKEN_FACTORY_MODELS.map(({ id, contextWindow }) => [id, contextWindow]),
  );

  assert.equal(contextWindows["nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"], 262144);
  assert.equal(contextWindows["nvidia/nemotron-3-super-120b-a12b"], 262144);
  assert.deepEqual(TOKEN_FACTORY_MODELS.map(({ alias }) => alias), [
    "Nemotron 3 Nano",
    "Nemotron 3 Super",
    "GLM 5.1",
    "DeepSeek V4 Pro",
  ]);
});

test("the eight-model workflow gate excludes every failed candidate and blocks explicit reintroduction", () => {
  assert.equal(TOKEN_FACTORY_QUALIFICATION.length, 8);
  assert.deepEqual(TOKEN_FACTORY_REJECTED_MODELS.map(({ alias }) => alias), [
    "Nemotron 3.5 Lightning",
    "Nemotron 3 Ultra",
    "GPT-OSS 120B",
    "Qwen3 32B",
  ]);
  assert.equal(TOKEN_FACTORY_REJECTED_MODELS.every(({ reason }) => typeof reason === "string" && reason.length > 20), true);
  const config = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
  assert.throws(
    () => configureOpenClaw(config, { AGENT_PROVIDER: "nebius", NEBIUS_API_KEY: "test-only", AGENT_MODEL: "nvidia/nemotron-3_5-lightning" }),
    /failed the BioNeMo workflow qualification gate/u,
  );
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
