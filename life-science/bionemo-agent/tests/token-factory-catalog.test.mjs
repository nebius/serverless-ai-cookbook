import assert from "node:assert/strict";
import test from "node:test";

import {
  configureOpenClaw,
  TOKEN_FACTORY_MODELS,
  TOKEN_FACTORY_QUALIFICATION,
  TOKEN_FACTORY_REJECTED_MODELS,
} from "../runtime/runtime-config.mjs";

test("only the two workflow-qualified Token Factory agents remain available", () => {
  const contextWindows = Object.fromEntries(
    TOKEN_FACTORY_MODELS.map(({ id, contextWindow }) => [id, contextWindow]),
  );

  assert.deepEqual(TOKEN_FACTORY_MODELS.map(({ alias }) => alias), [
    "Nemotron 3 Super",
    "GLM 5.2",
  ]);
  assert.equal(contextWindows["nvidia/nemotron-3-super-120b-a12b"], 262144);
  assert.equal(contextWindows["zai-org/GLM-5.2"], 90000);
});

test("the workflow gate excludes every known failed candidate and blocks explicit reintroduction", () => {
  assert.equal(TOKEN_FACTORY_QUALIFICATION.length, 12);
  assert.deepEqual(TOKEN_FACTORY_REJECTED_MODELS.map(({ alias }) => alias), [
    "Nemotron 3 Nano",
    "Nemotron 3.5 Lightning",
    "Nemotron 3 Ultra",
    "GPT-OSS 120B",
    "Qwen3 32B",
    "GLM 5.1",
    "DeepSeek V4 Pro",
    "DeepSeek V4 Flash",
    "MiniMax M3",
    "Kimi K3",
  ]);
  assert.equal(TOKEN_FACTORY_REJECTED_MODELS.every(({ reason }) => typeof reason === "string" && reason.length > 20), true);
  for (const { id } of TOKEN_FACTORY_REJECTED_MODELS) {
    const config = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
    assert.throws(
      () => configureOpenClaw(config, { AGENT_PROVIDER: "nebius", NEBIUS_API_KEY: "test-only", AGENT_MODEL: id.toLowerCase() }),
      /failed the BioNeMo workflow qualification gate/u,
    );
  }
});

test("the qualified Token Factory Super profile is selectable with safe request compatibility", () => {
  const config = {
    agents: { defaults: { model: {} } },
    models: {},
    tools: { alsoAllow: [], deny: ["bundle-mcp"] },
  };
  configureOpenClaw(config, { AGENT_PROVIDER: "nebius", NEBIUS_API_KEY: "test-only" });

  const tokenFactoryModels = config.models.providers.tokenfactory.models;
  const superModel = tokenFactoryModels.find(({ id }) => id === "nvidia/nemotron-3-super-120b-a12b");
  const glmModel = tokenFactoryModels.find(({ id }) => id === "zai-org/GLM-5.2");
  assert.ok(superModel);
  assert.ok(glmModel);
  assert.equal(tokenFactoryModels.length, 2);
  assert.equal(config.agents.defaults.model.primary, "tokenfactory/nvidia/nemotron-3-super-120b-a12b");
  assert.equal(superModel.contextWindow, 262_144);
  assert.equal(superModel.maxTokens, 8_192);
  assert.deepEqual(superModel.compat, {
    maxTokensField: "max_tokens",
    requiresStringContent: true,
  });
  assert.deepEqual(config.agents.defaults.models["tokenfactory/nvidia/nemotron-3-super-120b-a12b"].params, {
    chat_template_kwargs: { enable_thinking: false, force_nonempty_content: true },
  });
  assert.equal(glmModel.contextWindow, 90_000);
  assert.equal(glmModel.maxTokens, 8_192);
  assert.equal(glmModel.compat, undefined);
  assert.deepEqual(config.agents.defaults.models["tokenfactory/zai-org/GLM-5.2"], {
    alias: "GLM 5.2",
  });

  const selected = {
    agents: { defaults: { model: {} } },
    models: {},
    tools: { alsoAllow: [], deny: ["bundle-mcp"] },
  };
  configureOpenClaw(selected, {
    AGENT_PROVIDER: "nebius",
    NEBIUS_API_KEY: "test-only",
    AGENT_MODEL: "ZAI-ORG/glm-5.2",
  });
  assert.equal(selected.agents.defaults.model.primary, "tokenfactory/zai-org/GLM-5.2");
});
