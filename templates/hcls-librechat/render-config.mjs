import { writeFile } from 'node:fs/promises';

const outputPath = process.argv[2];
if (!outputPath) throw new Error('Expected the output config path');

const tokenFactoryApiKey = process.env.NEBIUS_API_KEY
  ? "'${NEBIUS_API_KEY}'"
  : "'user_provided'";

const mcpAuthentication = process.env.AUTH_TOKEN
  ? `    headers:\n      Authorization: 'Bearer \${AUTH_TOKEN}'`
  : `    headers:\n      Authorization: 'Bearer {{GROMACS_MCP_TOKEN}}'\n    customUserVars:\n      GROMACS_MCP_TOKEN:\n        title: 'GROMACS Serverless endpoint token'\n        description: 'Paste the token generated when the GPU REST/MCP endpoint was created.'\n        sensitive: true`;

const config = `version: 1.3.15
cache: true
interface:
  customWelcome: 'GROMACS Workbench: chat with Nebius Token Factory models and run bounded GPU molecular-dynamics workflows through the preconfigured MCP server.'
  modelSelect: true
  parameters: true
  defaultPinnedTools: ['mcp']
  agents:
    use: true
    create: true
    share: false
    public: false
  prompts:
    use: true
    create: false
    share: false
    public: false
  mcpServers:
    use: true
    create: false
    share: false
    public: false
  fileSearch: false
endpoints:
  agents:
    allowedProviders: ['Nebius Token Factory']
    capabilities: [tools, context, chain]
    recursionLimit: 20
    maxRecursionLimit: 40
    toolApproval:
      enabled: false
  custom:
    - name: 'Nebius Token Factory'
      apiKey: ${tokenFactoryApiKey}
      baseURL: 'https://api.tokenfactory.nebius.com/v1'
      models:
        default:
          - 'nvidia/nemotron-3-super-120b-a12b'
          - 'zai-org/GLM-5.2'
        fetch: false
      titleConvo: false
      titleModel: 'zai-org/GLM-5.2'
      modelDisplayLabel: 'Token Factory'
      dropParams: ['stop']
modelSpecs:
  prioritize: true
  list:
    - name: 'gromacs-workbench'
      label: 'GROMACS Workbench · GLM 5.2'
      description: 'Token Factory agent with bounded GROMACS REST/MCP tools on an NVIDIA GPU endpoint.'
      default: true
      showOnLanding: true
      conversation_starters:
        - 'List the available GROMACS capabilities and explain the safety limits.'
        - 'Prepare a small argon GPU smoke simulation, ask before submitting it, then monitor it and summarize the artifacts.'
        - 'Show recent GROMACS runs and explain which outputs are useful for validating an MD workflow.'
      preset:
        endpoint: agents
        agent_id: 'agent_gromacs_workbench'
mcpServers:
  gromacs:
    title: 'GROMACS GPU Workflows'
    description: 'Bounded molecular-dynamics runs on the configured Nebius Serverless GPU endpoint.'
    type: streamable-http
    url: '\${GROMACS_MCP_URL}'
${mcpAuthentication}
    initTimeout: 30000
    timeout: 900000
    serverInstructions: true
`;

await writeFile(outputPath, config, { mode: 0o600 });
process.stdout.write(
  `HCLS LibreChat config ready (Token Factory: ${process.env.NEBIUS_API_KEY ? 'server-managed' : 'per-user'}, GROMACS token: ${process.env.AUTH_TOKEN ? 'server-managed' : 'per-user'}).\n`,
);
