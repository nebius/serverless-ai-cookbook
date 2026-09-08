import { writeFile } from 'node:fs/promises';

const outputPath = process.argv[2];
if (!outputPath) throw new Error('Expected the output config path');

const scientificModelsApiKey = process.env.SCIENTIFIC_MODELS_API_KEY
  ? "'${SCIENTIFIC_MODELS_API_KEY}'"
  : "'user_provided'";

const tokenFactoryApiKey = process.env.NEBIUS_API_KEY
  ? "'${NEBIUS_API_KEY}'"
  : "'user_provided'";

const scientificModelsMcpAuthentication = process.env.SCIENTIFIC_MODELS_API_KEY
  ? "    headers:\n      Authorization: 'Bearer ${SCIENTIFIC_MODELS_API_KEY}'"
  : `    headers:
      Authorization: 'Bearer {{SCIENTIFIC_MODELS_API_KEY}}'
    customUserVars:
      SCIENTIFIC_MODELS_API_KEY:
        title: 'Scientific model gateway key'
        description: 'Paste the non-admin key issued for the scientific model gateway.'
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
    - name: 'protein-folding-and-structure'
      label: 'Protein Folding & Structure'
      description: 'Compare Boltz2, OpenFold2, and OpenFold3 through the live scientific model gateway.'
      default: true
      showOnLanding: true
      conversation_starters:
        - 'List live protein folding and structure models, their inputs, and model-specific limits.'
        - 'Prepare one small protein sequence benchmark across Boltz2, OpenFold2, and OpenFold3. Explain the comparison before running anything.'
        - 'Show how to retrieve a finished structure artifact and inspect its confidence metrics.'
      preset:
        endpoint: agents
        agent_id: 'agent_protein_structure'
    - name: 'molecular-docking-and-design'
      label: 'Molecular Docking & Design'
      description: 'Use DiffDock, GenMol, MolMIM, and ProteinMPNN from the live scientific catalog.'
      showOnLanding: true
      conversation_starters:
        - 'List the available docking and molecular-design models with their live operations.'
        - 'Outline a reproducible DiffDock versus Boltz2 binding benchmark without submitting it yet.'
      preset:
        endpoint: agents
        agent_id: 'agent_molecular_design'
    - name: 'molecular-dynamics'
      label: 'Molecular Dynamics · GROMACS'
      description: 'Prepare, submit, monitor, and retrieve bounded GPU molecular-dynamics runs.'
      showOnLanding: true
      conversation_starters:
        - 'List the available GROMACS capabilities and explain the safety limits.'
        - 'Prepare a small argon GPU smoke simulation, ask before submitting it, then monitor it and summarize the artifacts.'
      preset:
        endpoint: agents
        agent_id: 'agent_molecular_dynamics'
    - name: 'biomedical-imaging'
      label: 'Biomedical Imaging'
      description: 'Explore the live chest X-ray reasoning and CT segmentation models as research workflows.'
      showOnLanding: true
      conversation_starters:
        - 'List the live biomedical imaging models and the inputs they accept.'
        - 'Explain a research-only CT segmentation evaluation workflow with validation and human review.'
      preset:
        endpoint: agents
        agent_id: 'agent_biomedical_imaging'
    - name: 'genomics-and-aging'
      label: 'Genomics & Biological Age'
      description: 'Discover Evo2, AltumAge, and PhenoAge workflows from the live scientific catalog.'
      showOnLanding: true
      conversation_starters:
        - 'List the live genomics and biological-age models and their required inputs.'
        - 'Design a reproducible evaluation for a biological-age model with a held-out cohort.'
      preset:
        endpoint: agents
        agent_id: 'agent_genomics_aging'
    - name: 'audio-transcription'
      label: 'Audio Transcription · Tutorial'
      description: 'A readiness checklist for a future real-time transcription service; no audio model is connected.'
      showOnLanding: true
      conversation_starters:
        - 'Show the real-time transcription requirements and how a connected model would be evaluated.'
        - 'Which live scientific models currently support audio transcription?'
      preset:
        endpoint: agents
        agent_id: 'agent_audio_transcription_tutorial'
mcpServers:
  scientific_models:
    title: 'Nebius Scientific Model Gateway'
    description: 'Authorized scientific-model catalog and operations for this Nebius Scientific AI Agent deployment.'
    type: streamable-http
    url: '\${SCIENTIFIC_MODELS_MCP_URL}'
${scientificModelsMcpAuthentication}
    initTimeout: 30000
    timeout: 900000
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
