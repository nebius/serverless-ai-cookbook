import { readFile, writeFile } from 'node:fs/promises';

const outputPath = process.argv[2];
if (!outputPath) throw new Error('Expected the output config path');
const instructionsPath = process.env.SCIENTIFIC_AGENT_INSTRUCTIONS_PATH || '/app/scientific-agent-instructions.md';
const gatewayInstructions = (await readFile(instructionsPath, 'utf8')).trim();
const instructions = `You are Nebius Scientific AI Agent, a scientific research assistant. Help the user move from a question to a clear plan and a bounded experiment. Respond directly to the current request; do not recite all tutorials or ask a fixed questionnaire. For a tutorial, explain the goal, required input, expected output and one useful next step. A tutorial card prepares a prompt; compute requires the user to choose a run. Preserve authorization already given for that run.

The selected chat LLM reasons about the user's task and calls scientific tools. Scientific models such as Evo2, Boltz2 and DiffDock are tools, never replacements for the conversational LLM. Model-specific tools are loaded on demand: use tool_search to find a named tool when it is not yet visible. Read get_model_schema for the chosen model before preparing inputs. Do not dump the entire catalog for a question about one known model. Use Tavily for current literature and cite its sources. Preserve the user's chosen chat model throughout a workflow.

${gatewayInstructions}

Result reporting: always include the operation ID, exact returned status and any error code. Quote numerical confidence and timing only from explicit result fields, with the field name and units. Do not invent aggregate confidence, residue counts, fold quality or inferred timing. If a quantity needs calculation and no calculator/file tool is connected, omit it or state it is uncomputed. High pLDDT is local model confidence, not proof of structural correctness, reliability, function or experimental validation. Keep the final result concise: outcome, supported measurements, limitations, and one useful next step.`;

// Chat models observed in authenticated Token Factory discovery on 2026-09-09.
// Only the 17 models passing the bounded tool-call probe are offered. Gemma did
// not emit a tool call, MiniCPM rejected tools, GPT OSS/Kimi Code timed out.
// Embeddings and dedicated endpoints are outside this picker.
const tokenFactoryModels = [
  ['zai-org/GLM-5.3-Flash', 'GLM 5.3 Flash'],
  ['deepseek-ai/DeepSeek-V4-Flash-0731', 'DeepSeek V4 Flash'],
  ['Qwen/Qwen3.5-397B-A17B', 'Qwen 3.5'],
  ['moonshotai/Kimi-K3', 'Kimi K3'],
  ['meta-llama/Llama-3.3-70B-Instruct', 'Llama 3.3 70B'],
  ['zai-org/GLM-5.2', 'GLM 5.2'],
  ['zai-org/GLM-5.1', 'GLM 5.1'],
  ['deepseek-ai/DeepSeek-V4-Pro', 'DeepSeek V4 Pro'],
  ['MiniMaxAI/MiniMax-M3', 'MiniMax M3'],
  ['moonshotai/Kimi-K2.6', 'Kimi K2.6'],
  ['Qwen/Qwen3-235B-A22B-Instruct-2507', 'Qwen 3 235B'],
  ['Qwen/Qwen3-30B-A3B-Instruct-2507', 'Qwen 3 30B'],
  ['NousResearch/Hermes-4-405B', 'Hermes 4 405B'],
  ['nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 'Nemotron 3 Nano'],
  ['nvidia/Nemotron-3_5-Lightning', 'Nemotron 3.5 Lightning'],
  ['nvidia/Nemotron-3-Ultra-550b-a55b', 'Nemotron 3 Ultra'],
  ['nvidia/nemotron-3-super-120b-a12b', 'Nemotron 3 Super'],
];

let availableTokenModels = tokenFactoryModels;
if (process.env.NEBIUS_API_KEY && process.env.NEBIUS_API_KEY !== 'user_provided'
    && process.env.SCIENTIFIC_DISCOVER_CHAT_MODELS !== 'false') {
  try {
    const response = await fetch('https://api.tokenfactory.nebius.com/v1/models', {
      headers: { Authorization: `Bearer ${process.env.NEBIUS_API_KEY}` },
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error('Model discovery unavailable');
    const catalog = await response.json();
    const ids = new Set(catalog.data.map((item) => item.id));
    const available = tokenFactoryModels.filter(([id]) => ids.has(id));
    if (available.length) availableTokenModels = available;
  } catch {
    process.stderr.write('Chat model discovery unavailable; using the configured chat catalog.\n');
  }
}

const providerModels = [
  { endpoint: 'Nebius Token Factory', group: 'Nebius Token Factory', models: availableTokenModels },
  { endpoint: 'openAI', group: 'OpenAI', models: [
    ['gpt-6-astra', 'GPT-6 Astra'], ['gpt-5.6', 'GPT-5.6 Sol'],
    ['gpt-5.6-terra', 'GPT-5.6 Terra'], ['gpt-5.6-luna', 'GPT-5.6 Luna'],
  ] },
  { endpoint: 'anthropic', group: 'Claude', models: [
    ['claude-opus-5', 'Claude Opus 5'], ['claude-sonnet-5', 'Claude Sonnet 5'],
    ['claude-haiku-4-5', 'Claude Haiku 4.5'],
  ] },
];

const modelSpecs = providerModels.flatMap(({ endpoint, group, models }) => models.map(([model, label], index) => {
  const isDefault = endpoint === 'Nebius Token Factory' && index === 0;
  return {
    name: isDefault ? 'nebius-scientific-ai-agent' : `science-${endpoint}-${model}`.replace(/[^a-zA-Z0-9-]/g, '-').toLowerCase(),
    label, group, groupIcon: endpoint === 'anthropic' ? 'anthropic' : endpoint === 'openAI' ? 'openAI' : '/assets/token-factory.svg',
    iconURL: endpoint === 'Nebius Token Factory' ? '/assets/token-factory.svg' : endpoint,
    default: isDefault, showOnLanding: false, showIconInHeader: true,
    description: endpoint === 'Nebius Token Factory' ? 'Scientific tools and web research' : 'Scientific tools · connect your provider key',
    mcpServers: ['bionemo-models', 'tavily', 'structure-viewer', 'environment-execution'], skills: true, artifacts: true,
    preset: { endpoint, model, modelLabel: label, promptPrefix: instructions,
      ...(endpoint === 'openAI' ? { useResponsesApi: true } : {}),
    },
  };
}));

const sharedGatewayKey = Boolean(process.env.SCIENTIFIC_MODELS_API_KEY);
const config = {
  version: '1.3.15', cache: true,
  interface: {
    customWelcome: 'Your scientific workspace',
    // Model specs remain selectable; hide raw endpoints and saved tutorial agents.
    modelSelect: false, parameters: true,
    skills: { use: true, create: false, share: false, public: false },
    agents: { use: true, create: true, share: false, public: false },
    prompts: { use: true, create: false, share: false, public: false },
    mcpServers: { use: true, create: false, share: false, public: false },
    fileSearch: false,
  },
  endpoints: {
    agents: {
      allowedProviders: ['Nebius Token Factory', 'openAI', 'anthropic'],
      capabilities: ['skills', 'tools', 'artifacts', 'context', 'chain', 'deferred_tools'],
      recursionLimit: 30, maxRecursionLimit: 50, toolApproval: { enabled: false },
    },
    openAI: { titleConvo: true, titleModel: 'gpt-5.6-luna' },
    anthropic: { titleConvo: true, titleModel: 'claude-haiku-4-5' },
    custom: [{
      name: 'Nebius Token Factory',
      iconURL: '/assets/token-factory.svg',
      apiKey: process.env.NEBIUS_API_KEY ? '${NEBIUS_API_KEY}' : 'user_provided',
      baseURL: 'https://api.tokenfactory.nebius.com/v1',
      models: { default: availableTokenModels.map(([id]) => id), fetch: false },
      titleConvo: true, titleModel: availableTokenModels.find(([id]) => id === 'Qwen/Qwen3-30B-A3B-Instruct-2507')?.[0] || availableTokenModels[0][0],
      modelDisplayLabel: 'Nebius', dropParams: ['stop'],
    }],
  },
  modelSpecs: { prioritize: true, enforce: false, list: modelSpecs },
  mcpServers: {
    'environment-execution': {
      title: 'Environment execution', description: 'Root shell, Python, packages, internet and mounted files.',
      type: 'stdio', command: 'python3', args: ['/opt/bionemo/execution-mcp.py'],
      startup: true, timeout: 30000,
      env: { SCIENTIFIC_WORKSPACE: '/workspace',
        ...(sharedGatewayKey ? { SCIENTIFIC_MODELS_API_KEY: '${SCIENTIFIC_MODELS_API_KEY}' } : {}),
        SCIENTIFIC_MODELS_API_BASE_URL: '${SCIENTIFIC_MODELS_API_BASE_URL}',
        SCIENTIFIC_MODELS_MCP_URL: '${SCIENTIFIC_MODELS_MCP_URL}' },
    },
    'structure-viewer': {
      title: 'Structure viewer', description: 'Read-only interactive protein and molecule visualization.',
      type: 'stdio', command: 'python3', args: ['/opt/bionemo/structure-mcp.py'],
      startup: sharedGatewayKey,
      env: { SCIENTIFIC_MODELS_API_BASE_URL: '${SCIENTIFIC_MODELS_API_BASE_URL}',
        SCIENTIFIC_MODELS_API_KEY: sharedGatewayKey ? '${SCIENTIFIC_MODELS_API_KEY}' : '{{SCIENTIFIC_MODELS_API_KEY}}' },
      ...(!sharedGatewayKey ? { customUserVars: { SCIENTIFIC_MODELS_API_KEY: {
        title: 'Scientific platform API key', description: 'Use your own scientific model-access key for result visualization.', sensitive: true,
      } } } : {}),
      timeout: 60000,
    },
    tavily: { type: 'stdio', command: 'node', args: ['/opt/bionemo/tavily-mcp.mjs'],
      env: { TAVILY_API_KEY: '${TAVILY_API_KEY}' } },
    'bionemo-models': {
      title: 'Scientific models', description: 'Protein, molecule, sequence, imaging and scientific batch tools.',
      type: 'streamable-http', url: '${SCIENTIFIC_MODELS_MCP_URL}',
      startup: sharedGatewayKey, requiresOAuth: false,
      headers: { Authorization: sharedGatewayKey ? 'Bearer ${SCIENTIFIC_MODELS_API_KEY}' : 'Bearer {{SCIENTIFIC_MODELS_API_KEY}}' },
      ...(!sharedGatewayKey ? { customUserVars: { SCIENTIFIC_MODELS_API_KEY: {
        title: 'Scientific platform API key', description: 'Your model-access key, without the Bearer prefix.', sensitive: true,
      } } } : {}),
      initTimeout: 30000, timeout: 120000, serverInstructions: true,
    },
  },
};

// JSON is valid YAML and preserves multiline instructions and literal key references.
await writeFile(outputPath, JSON.stringify(config, null, 2) + '\n', { mode: 0o600 });
process.stdout.write(`Scientific workspace config ready: ${modelSpecs.length} chat choices; gateway ${sharedGatewayKey ? 'server-managed' : 'per-user'}.\n`);
