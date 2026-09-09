import { writeFile } from 'node:fs/promises';

const outputPath = process.argv[2];
if (!outputPath) throw new Error('Expected the output config path');

const scientificModelsApiKey = process.env.SCIENTIFIC_MODELS_API_KEY
  ? "'${SCIENTIFIC_MODELS_API_KEY}'"
  : "'user_provided'";

const tokenFactoryApiKey = process.env.NEBIUS_API_KEY
  ? "'${NEBIUS_API_KEY}'"
  : "'user_provided'";

// Per-user gateway key (recommended baseline): each chat user supplies their own
// ordinary inference key in MCP Settings; startup stays false because discovery
// is caller-specific. Double braces resolve the current user's custom variable.
const scientificModelsMcpAuthentication = `    startup: false
    requiresOAuth: false
    headers:
      Authorization: 'Bearer {{SCIENTIFIC_MODELS_API_KEY}}'
    customUserVars:
      SCIENTIFIC_MODELS_API_KEY:
        title: 'Scientific platform API key'
        description: 'Your ordinary model-access key, without the Bearer prefix.'
        sensitive: true`;

const gromacsAuthentication = process.env.AUTH_TOKEN
  ? "    headers:\n      Authorization: 'Bearer ${AUTH_TOKEN}'"
  : `    headers:
      Authorization: 'Bearer {{GROMACS_MCP_TOKEN}}'
    customUserVars:
      GROMACS_MCP_TOKEN:
        title: 'GROMACS Serverless endpoint token'
        description: 'Paste the token generated when the GROMACS GPU endpoint was created.'
        sensitive: true`;

const config = `version: 1.3.15
cache: true
interface:
  customWelcome: 'Nebius Scientific AI Agent brings protein structure, molecular discovery, biomedical imaging, and GPU simulation into one guided workbench.'
  skills:
    use: true
    create: false
    share: false
    public: false
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
    allowedProviders: ['Nebius Token Factory', 'Nebius Scientific Models']
    capabilities: [skills, tools, artifacts, context, chain]
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
          - 'zai-org/GLM-5.3-Flash'
        fetch: false
      titleConvo: false
      titleModel: 'zai-org/GLM-5.3-Flash'
      modelDisplayLabel: 'Token Factory'
      dropParams: ['stop']
    - name: 'Nebius Scientific Models'
      apiKey: ${scientificModelsApiKey}
      baseURL: '\${SCIENTIFIC_MODELS_API_BASE_URL}'
      models:
        default:
          - 'qwen3-8b'
        fetch: true
      titleConvo: false
      titleModel: 'qwen3-8b'
      modelDisplayLabel: 'Nebius Scientific Models'
      dropParams: ['stop']
modelSpecs:
  prioritize: true
  list:
    - name: 'nebius-scientific-ai-agent'
      label: 'Nebius Scientific AI Agent'
      description: 'Your scientific AI workbench: choose a guided tutorial below or ask for a live model recommendation.'
      default: true
      showOnLanding: true
      preset:
        endpoint: agents
        agent_id: 'agent_nebius_scientific_ai'
    - name: 'protein-folding-and-structure'
      label: 'Protein Folding & Structure'
      description: 'Compare Boltz2, OpenFold2, and OpenFold3 through the live scientific model gateway.'
      showOnLanding: true
      preset:
        endpoint: agents
        agent_id: 'agent_protein_structure'
    - name: 'molecular-docking-and-design'
      label: 'Molecular Docking & Design'
      description: 'Use DiffDock, GenMol, MolMIM, and ProteinMPNN from the live scientific catalog.'
      showOnLanding: true
      preset:
        endpoint: agents
        agent_id: 'agent_molecular_design'
    - name: 'molecular-dynamics'
      label: 'Molecular Dynamics · GROMACS'
      description: 'Prepare, submit, monitor, and retrieve bounded GPU molecular-dynamics runs.'
      showOnLanding: true
      preset:
        endpoint: agents
        agent_id: 'agent_molecular_dynamics'
    - name: 'biomedical-imaging'
      label: 'Biomedical Imaging'
      description: 'Explore the live chest X-ray reasoning and CT segmentation models as research workflows.'
      showOnLanding: true
      preset:
        endpoint: agents
        agent_id: 'agent_biomedical_imaging'
    - name: 'genomics-and-aging'
      label: 'Genomics & Biological Age'
      description: 'Discover Evo2, AltumAge, and PhenoAge workflows from the live scientific catalog.'
      showOnLanding: true
      preset:
        endpoint: agents
        agent_id: 'agent_genomics_aging'
    - name: 'audio-transcription'
      label: 'Audio Transcription · Tutorial'
      description: 'A readiness checklist for a future real-time transcription service; no audio model is connected.'
      showOnLanding: true
      preset:
        endpoint: agents
        agent_id: 'agent_audio_transcription_tutorial'
mcpServers:
  bionemo-models:
    title: 'Nebius Scientific Model Gateway'
    description: 'Authorized scientific-model catalog and operations for this Nebius Scientific AI Agent deployment.'
    type: streamable-http
    url: '\${SCIENTIFIC_MODELS_MCP_URL}'
${scientificModelsMcpAuthentication}
    initTimeout: 30000
    timeout: 120000
    serverInstructions: true
  gromacs:
    title: 'GROMACS GPU Workflows'
    description: 'Bounded molecular-dynamics runs on the configured Nebius Serverless GPU endpoint.'
    type: streamable-http
    url: '\${GROMACS_MCP_URL}'
${gromacsAuthentication}
    initTimeout: 30000
    timeout: 900000
    serverInstructions: true
`;

await writeFile(outputPath, config, { mode: 0o600 });
process.stdout.write(
  `Nebius Scientific AI Agent config ready (scientific gateway key: ${process.env.SCIENTIFIC_MODELS_API_KEY ? 'server-managed' : 'per-user'}, Token Factory key: ${process.env.NEBIUS_API_KEY ? 'server-managed' : 'per-user'}, GROMACS token: ${process.env.AUTH_TOKEN ? 'server-managed' : 'per-user'}).\n`,
);
