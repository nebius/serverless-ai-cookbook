import { writeFile } from 'node:fs/promises';

const outputPath = process.argv[2];
if (!outputPath) throw new Error('Expected the output config path');

const scientificModelsApiKey = process.env.SCIENTIFIC_MODELS_API_KEY
  ? "'${SCIENTIFIC_MODELS_API_KEY}'"
  : "'user_provided'";

const tokenFactoryApiKey = process.env.NEBIUS_API_KEY
  ? "'${NEBIUS_API_KEY}'"
  : "'user_provided'";

// Two supported modes (see integrations/librechat handover):
// - Injected shared key (deliberately single-customer deployments): set
//   SCIENTIFIC_MODELS_API_KEY as a deployment env var; the server connects at
//   startup so agents have MCP tools immediately.
// - Per-user keys (recommended for multi-customer): leave the env unset; each
//   user supplies their own key in MCP Settings (startup: false because
//   discovery is caller-specific).
const scientificModelsMcpAuthentication = process.env.SCIENTIFIC_MODELS_API_KEY
  ? "    startup: true\n    requiresOAuth: false\n    headers:\n      Authorization: 'Bearer ${SCIENTIFIC_MODELS_API_KEY}'"
  : `    startup: false
    requiresOAuth: false
    headers:
      Authorization: 'Bearer {{SCIENTIFIC_MODELS_API_KEY}}'
    customUserVars:
      SCIENTIFIC_MODELS_API_KEY:
        title: 'Scientific platform API key'
        description: 'Your ordinary model-access key, without the Bearer prefix.'
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
`;

await writeFile(outputPath, config, { mode: 0o600 });
process.stdout.write(
  `Nebius Scientific AI Agent config ready (scientific gateway key: ${process.env.SCIENTIFIC_MODELS_API_KEY ? 'server-managed' : 'per-user'}, Token Factory key: ${process.env.NEBIUS_API_KEY ? 'server-managed' : 'per-user'}, GROMACS token: ${process.env.AUTH_TOKEN ? 'server-managed' : 'per-user'}).\n`,
);
