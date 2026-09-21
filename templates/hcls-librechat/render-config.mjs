import { readFile, writeFile } from 'node:fs/promises';

const outputPath = process.argv[2];
if (!outputPath) throw new Error('Expected the output config path');
const instructionsPath = process.env.SCIENTIFIC_AGENT_INSTRUCTIONS_PATH || '/app/scientific-agent-instructions.md';
const gatewayInstructions = (await readFile(instructionsPath, 'utf8')).trim();
const teamContext = process.env.TEAM_ID && process.env.TEAM_BUCKET_NAME
  ? `This is ${process.env.TEAM_ID}'s dedicated scientific workspace. Object Storage bucket ${process.env.TEAM_BUCKET_NAME} is mounted read-write at /workspace. Use /workspace for durable files and verify important writes before reporting them complete.`
  : 'Check workbench_workspace before promising direct file access. Shared deployments may expose caller-owned storage without mounting it into the container.';
const instructions = `You are Nebius Scientific AI Agent, a scientific research assistant. Help the user move from a question to a clear plan and a bounded experiment. Respond directly to the current request; do not recite all tutorials or ask a fixed questionnaire. For a tutorial, explain the goal, required input, expected output and one useful next step. A tutorial card prepares a prompt; compute requires the user to choose a run. Preserve authorization already given for that run.

The selected chat LLM reasons about the user's task and calls scientific tools. Scientific models such as Evo2, Boltz2 and DiffDock are tools, never replacements for the conversational LLM. Execution, analysis, lifecycle and model-specific tools are loaded on demand: use tool_search to find a named tool when it is not yet visible, and call its exact registered name including the MCP suffix. Read get_model_schema for the chosen model directly; this checks authorization without dumping both catalogs. When one request names several Apps, read every named App's live schema before submitting the first operation, then construct each request only from its own schema. Never infer one App's fields from another App or from memory. Use workbench_list_apps for compact discovery. Use Tavily for current literature and cite its sources. Preserve the user's chosen chat model throughout a workflow.

${teamContext}

Storage and context: /workspace is an object-storage mount, not a full POSIX disk. Use byte copies (shutil.copyfile or read_bytes/write_bytes), not copy2/copystat/chmod. The packaged file clients maintain resumable receipts there. Read their --help for arguments; do not dump implementation source or raw datasets into chat. Keep full inputs/results/logs in files and print only the fields needed for the next decision. Read a chosen App schema once per unchanged contract; do not repeat discovery during polling. A long-running job can remain in Runs between turns; preserve its operation ID rather than consuming the context with repeated status calls.

${gatewayInstructions}

Run continuity: immediately call workbench_track_operation for every submitted operation ID, including failures, then poll that same ID. Never resubmit because a poll or chat response timed out. Use workbench_get_operation_result for verified raw files plus compact metrics. Analyze its workspace_file.path, never move full coordinates through chat. Combine related preparation and analysis into coherent Python heredocs instead of many tiny execution calls. Complete the requested scientific deliverable, not only its model invocation. Direct the user to Apps, Runs and Workspace at /demos.

Result reporting: always include the operation ID, exact returned status and any error code. Quote numerical confidence and timing only from explicit result fields, with the field name and units. Do not invent aggregate confidence, residue counts, fold quality or inferred timing. If a quantity needs calculation and no calculator/file tool is connected, omit it or state it is uncomputed. High pLDDT is local model confidence, not proof of structural correctness, reliability, function or experimental validation. Finish the deliverables the user actually requested before adding optional work. Do not hold a requested table or viewer open merely to create an unrequested report, animation, or cosmetic artifact. Keep the final result concise: outcome, supported measurements, limitations, and one useful next step.`;

// Public chat models observed in authenticated Token Factory discovery on
// 2026-09-09. This is the conversational-LLM catalog, not the Scientific Apps
// catalog; Apps are discovered dynamically from the caller's platform key.
const publicTokenFactoryModels = [
  ['Qwen/Qwen3-235B-A22B-Instruct-2507', 'Qwen3 235B A22B Instruct'],
  ['Qwen/Qwen3-30B-A3B-Instruct-2507', 'Qwen3 30B A3B Instruct'],
  ['zai-org/GLM-5.3-Flash', 'GLM 5.3 Flash'],
  ['deepseek-ai/DeepSeek-V4-Flash-0731', 'DeepSeek V4 Flash'],
  ['moonshotai/Kimi-K3', 'Kimi K3'],
  ['meta-llama/Llama-3.3-70B-Instruct', 'Llama 3.3 70B'],
  ['zai-org/GLM-5.2', 'GLM 5.2'],
  ['zai-org/GLM-5.1', 'GLM 5.1'],
  ['deepseek-ai/DeepSeek-V4-Pro', 'DeepSeek V4 Pro'],
  ['MiniMaxAI/MiniMax-M3', 'MiniMax M3'],
  ['moonshotai/Kimi-K2.6', 'Kimi K2.6'],
  ['NousResearch/Hermes-4-405B', 'Hermes 4 405B'],
  ['nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 'Nemotron 3 Nano'],
  ['nvidia/Nemotron-3_5-Lightning', 'Nemotron 3.5 Lightning'],
  ['nvidia/Nemotron-3-Ultra-550b-a55b', 'Nemotron 3 Ultra'],
  ['nvidia/nemotron-3-super-120b-a12b', 'Nemotron 3 Super'],
];

// LibreChat cannot infer context sizes for several new Token Factory model IDs.
// An unknown model otherwise falls back to 32k, which is smaller than the
// scientific instructions plus tool schemas and causes every user message to
// be pruned before the request reaches Token Factory.
const tokenFactoryContext = new Map([
  ['Qwen/Qwen3-235B-A22B-Instruct-2507', 262144],
  ['Qwen/Qwen3-30B-A3B-Instruct-2507', 262144],
  ['zai-org/GLM-5.3-Flash', 1048576],
  ['deepseek-ai/DeepSeek-V4-Flash-0731', 1048576],
  ['moonshotai/Kimi-K3', 1048576],
  ['meta-llama/Llama-3.3-70B-Instruct', 127500],
  ['zai-org/GLM-5.2', 1048576],
  ['zai-org/GLM-5.1', 204800],
  ['deepseek-ai/DeepSeek-V4-Pro', 1048576],
  ['MiniMaxAI/MiniMax-M3', 1048576],
  ['moonshotai/Kimi-K2.6', 262144],
  ['NousResearch/Hermes-4-405B', 131072],
  ['nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 1048576],
  ['nvidia/Nemotron-3_5-Lightning', 1048576],
  ['nvidia/Nemotron-3-Ultra-550b-a55b', 1048576],
  ['nvidia/nemotron-3-super-120b-a12b', 1048576],
]);

const makeTokenConfig = (models) => Object.fromEntries(models.map(([id]) => [id, {
  prompt: 0, completion: 0, context: tokenFactoryContext.get(id) ?? 131072,
}]));

let availablePublicTokenModels = publicTokenFactoryModels;
let discoveredPublicTokenIds = null;
const configuredChatModel = process.env.SCIENTIFIC_CHAT_MODEL;
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
    discoveredPublicTokenIds = ids;
    const available = publicTokenFactoryModels.filter(([id]) => ids.has(id));
    availablePublicTokenModels = available;
  } catch {
    process.stderr.write('Chat model discovery unavailable; using the configured chat catalog.\n');
  }
}

// A positively discovered, explicitly configured planning model need not have
// existed when the curated display-name list was written. Preserve validation:
// never silently replace the selected model or admit an unknown fallback.
if (configuredChatModel) {
  if (discoveredPublicTokenIds && !discoveredPublicTokenIds.has(configuredChatModel)) {
    throw new Error(`Configured chat model ${configuredChatModel} is absent from the authenticated Token Factory catalog`);
  }
  if (!availablePublicTokenModels.some(([id]) => id === configuredChatModel)) {
    if (!discoveredPublicTokenIds?.has(configuredChatModel)) {
      throw new Error('The configured chat model is not in the curated catalog and live discovery could not verify it');
    }
    availablePublicTokenModels = [...availablePublicTokenModels, [configuredChatModel, configuredChatModel]];
  }
}

// The reusable client has no event-owned endpoints. A stale environment flag
// must not resurrect retired model IDs when an existing instance is upgraded.
const providerModels = [
  { endpoint: 'Nebius Token Factory', group: 'Public Token Factory', models: availablePublicTokenModels },
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
  return {
    name: `science-${endpoint}-${model}`.replace(/[^a-zA-Z0-9-]/g, '-').toLowerCase(),
    label, group, groupIcon: endpoint === 'anthropic' ? 'anthropic' : endpoint === 'openAI' ? 'openAI' : '/assets/token-factory.svg',
    iconURL: endpoint === 'anthropic' || endpoint === 'openAI' ? endpoint : '/assets/token-factory.svg',
    default: false, showOnLanding: false, showIconInHeader: true,
    description: endpoint === 'Nebius Token Factory'
        ? 'Public Token Factory · scientific tools and web research'
        : 'Scientific tools · connect your provider key',
    mcpServers: ['scientific-ai-apps', 'scientific-demos', 'tavily', 'structure-viewer', 'environment-execution'], skills: true, artifacts: true,
    preset: { endpoint, model, modelLabel: label, promptPrefix: instructions,
      ...(endpoint === 'openAI' ? { useResponsesApi: true } : {}),
    },
  };
}));

const sharedGatewayKey = Boolean(process.env.SCIENTIFIC_MODELS_API_KEY);
modelSpecs.push({ name: 'nebius-scientific-ai-agent', label: 'Nebius Scientific AI Agent',
  group: 'Scientific workspace', groupIcon: '/assets/token-factory.svg',
  iconURL: '/assets/token-factory.svg', showOnLanding: false, showIconInHeader: true,
  default: true, skills: true,
  mcpServers: ['scientific-ai-apps', 'scientific-demos', 'tavily', 'structure-viewer', 'environment-execution'],
  preset: { endpoint: 'agents', agent_id: 'agent_nebius_scientific_ai' } });
modelSpecs.push(...[
  ['clinical-report', 'Clinical Report Draft', 'agent_clinical_report'],
  ['mindeval-workshop', 'Conversation Evaluation', 'agent_mindeval_workshop'],
].map(([name, label, agent_id]) => ({ name, label, group: 'Research workflows',
  iconURL: '/assets/token-factory.svg', showOnLanding: false, default: false,
  skills: true, mcpServers: ['scientific-demos'],
  preset: { endpoint: 'agents', agent_id } })));
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
      recursionLimit: 50, maxRecursionLimit: 50, toolApproval: { enabled: false },
    },
    openAI: { titleConvo: true, titleModel: 'gpt-5.6-luna' },
    anthropic: { titleConvo: true, titleModel: 'claude-haiku-4-5' },
    custom: [{
      name: 'Nebius Token Factory',
      iconURL: '/assets/token-factory.svg',
      apiKey: process.env.NEBIUS_API_KEY ? '${NEBIUS_API_KEY}' : 'user_provided',
      baseURL: 'https://api.tokenfactory.nebius.com/v1',
      models: { default: availablePublicTokenModels.map(([id]) => id), fetch: false },
      tokenConfig: makeTokenConfig(availablePublicTokenModels),
      titleConvo: true, titleModel: availablePublicTokenModels[0][0],
      modelDisplayLabel: 'Nebius Public', dropParams: ['stop'],
    }],
  },
  modelSpecs: { prioritize: true, enforce: false, list: modelSpecs },
  mcpServers: {
    'scientific-demos': {
      title: 'Scientific workbench', description: 'Durable run tracking, workspace files, clinical drafts and conversation evaluation.',
      type: 'stdio', command: 'node', args: ['/opt/hcls-librechat/demos/mcp.cjs'],
      startup: false, timeout: 60000,
      env: { LIBRECHAT_USER_ID: '{{LIBRECHAT_USER_ID}}',
        SCIENTIFIC_MODELS_API_KEY: '{{SCIENTIFIC_MODELS_API_KEY}}',
        SCIENTIFIC_MODELS_API_BASE_URL: '${SCIENTIFIC_MODELS_API_BASE_URL}',
        NEBIUS_API_KEY: '${NEBIUS_API_KEY}' },
      customUserVars: { SCIENTIFIC_MODELS_API_KEY: {
        title: 'Scientific AI API key', description: 'Your personal platform key, also configurable in the Apps panel.', sensitive: true,
      } }, serverInstructions: true,
    },
    'environment-execution': {
      title: 'Environment execution', description: 'Root shell, Python, packages, internet and mounted files.',
      type: 'stdio', command: '/opt/scientific-client/bin/python', args: ['/opt/bionemo/execution-mcp.py'],
      startup: true, timeout: 30000,
      env: { SCIENTIFIC_WORKSPACE: '/workspace',
        // Stdio transports inherit only their safe default environment and
        // these explicit bindings, unlike the API/supervisor parent process.
        // Preserve the same owner precedence and stop-first decision; never
        // invent a default mode or use the transient LibreChat request ID.
        ...(process.env.SCIENTIFIC_STUDY_OWNER_MODE ? { SCIENTIFIC_STUDY_OWNER_MODE: '${SCIENTIFIC_STUDY_OWNER_MODE}' } : {}),
        ...(process.env.SCIENTIFIC_STUDY_OWNER ? { SCIENTIFIC_STUDY_OWNER: '${SCIENTIFIC_STUDY_OWNER}' } : {}),
        ...(process.env.SEED_DEFAULT_USER_EMAIL ? { SEED_DEFAULT_USER_EMAIL: '${SEED_DEFAULT_USER_EMAIL}' } : {}),
        ...(process.env.CLINICAL_REPORT_API_KEY ? { CLINICAL_REPORT_API_KEY: '${CLINICAL_REPORT_API_KEY}' } : {}),
        ...(process.env.NEBIUS_API_KEY ? { NEBIUS_API_KEY: '${NEBIUS_API_KEY}' } : {}),
        ...(process.env.CLINICAL_REPORT_API_KEY_FILE ? { CLINICAL_REPORT_API_KEY_FILE: '${CLINICAL_REPORT_API_KEY_FILE}' } : {}),
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
        title: 'Scientific AI API key', description: 'Use your own App-access key for result visualization.', sensitive: true,
      } } } : {}),
      timeout: 60000,
    },
    tavily: { type: 'stdio', command: 'node', args: ['/opt/bionemo/tavily-mcp.mjs'],
      env: { TAVILY_API_KEY: '${TAVILY_API_KEY}' } },
    'scientific-ai-apps': {
      title: 'Scientific AI Apps', description: 'Authorized model and workflow Apps for protein, molecule, sequence, imaging, speech, media, robotics and scientific batch work.',
      type: 'streamable-http', url: '${SCIENTIFIC_MODELS_MCP_URL}',
      startup: sharedGatewayKey, requiresOAuth: false,
      headers: { Authorization: sharedGatewayKey ? 'Bearer ${SCIENTIFIC_MODELS_API_KEY}' : 'Bearer {{SCIENTIFIC_MODELS_API_KEY}}' },
      ...(!sharedGatewayKey ? { customUserVars: { SCIENTIFIC_MODELS_API_KEY: {
        title: 'Scientific AI API key', description: 'Your App-access key, without the Bearer prefix.', sensitive: true,
      } } } : {}),
      initTimeout: 30000, timeout: 120000, serverInstructions: true,
    },
  },
};

// JSON is valid YAML and preserves multiline instructions and literal key references.
await writeFile(outputPath, JSON.stringify(config, null, 2) + '\n', { mode: 0o600 });
process.stdout.write(`Scientific workspace config ready: ${modelSpecs.length} chat choices; gateway ${sharedGatewayKey ? 'server-managed' : 'per-user'}.\n`);
