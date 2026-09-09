const { MongoClient, ObjectId } = require('mongodb');

const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat';
const serviceEmail = 'nebius-scientific-ai-agent@localhost.invalid';
const model = 'zai-org/GLM-5.3-Flash';

const scientificModelsServerName = 'scientific_models';
const mcpTool = (name) => `${name}_mcp_${scientificModelsServerName}`;
const scientificCatalogTools = [
  'list_models', 'list_scientific_models', 'invoke_model', 'get_operation',
  'get_operation_result', 'cancel_operation', 'acknowledge_operation',
  'submit_scientific_run', 'get_scientific_status', 'cancel_scientific_run',
  'list_scientific_events', 'get_scientific_artifact', 'get_scientific_result',
  'download_scientific_artifact', 'read_scientific_artifact_bytes',
].map(mcpTool);

const structureTools = [
  ...scientificCatalogTools,
  ...['boltz2_predict_native', 'infer_openfold2_native', 'infer_openfold3_native',
    'submit_alphafold3', 'submit_esmfold2', 'submit_esmfold2_fast', 'submit_openfold3_openbind'].map(mcpTool),
];

const molecularDesignTools = [
  ...scientificCatalogTools,
  ...['infer_diffdock_native', 'genmol_generate_native', 'molmim_run_native',
    'infer_proteinmpnn_native', 'submit_bindcraft', 'submit_boltzgen', 'submit_mosaic',
    'submit_proteina_complexa', 'submit_protenix_v2', 'submit_rfdiffusion'].map(mcpTool),
];

const biomedicalImagingTools = [
  ...scientificCatalogTools,
  ...['analyze_image_openai_chat', 'segment_ct_native'].map(mcpTool),
];

const genomicsTools = [
  ...scientificCatalogTools,
  ...['generate_dna_native', 'infer_altumage_native', 'infer_phenoage_native'].map(mcpTool),
];

const gromacsTools = [
  'get_capabilities_mcp_gromacs',
  'submit_run_mcp_gromacs',
  'get_run_mcp_gromacs',
  'list_runs_mcp_gromacs',
  'cancel_run_mcp_gromacs',
  'list_run_artifacts_mcp_gromacs',
];

const allScientificTools = [...new Set([
  ...structureTools,
  ...molecularDesignTools,
  ...biomedicalImagingTools,
  ...genomicsTools,
  ...gromacsTools,
])];

function agents() {
  return [
    {
      id: 'agent_nebius_scientific_ai',
      name: 'Nebius Scientific AI Agent',
      description: 'The Nebius Scientific AI workbench for model discovery, scientific workflows, and reproducible comparisons.',
      instructions: `You are Nebius Scientific AI Agent. You are the primary scientific workbench, not a tutorial. Start by asking about the user’s scientific goal, data, constraints, and evaluation target. Inspect the live scientific model catalog before stating which services are available.

Present the catalog in these six guided areas: Protein Folding & Structure; Molecular Docking & Design; Molecular Dynamics; Biomedical Imaging; Genomics & Biological Age; and Audio Transcription. The scientific gateway currently exposes models including AltumAge, Boltz2, Cosmos3 Nano, DiffDock, Evo2-40B, GenMol, MolMIM, MSA Search PDB70, chest X-ray reasoning, CT segmentation, OpenFold2, OpenFold3, PhenoAge, ProteinMPNN, Qwen3-8B, and SDXL. Verify this list live because availability can change.

For any proposed benchmark, fix inputs, preprocessing, random seeds, compute settings, success metrics, and artifact retention across candidate models. State limitations and ask before submitting compute. Use the GROMACS tools for molecular dynamics, the scientific gateway for model operations, and preserve operation IDs for reproducibility. Never present scientific model output as clinical advice or experimental validation.`,
      tools: allScientificTools,
      mcpServerNames: [scientificModelsServerName, 'gromacs'],
      conversation_starters: [
        'Show the scientific model catalog grouped by protein structure, docking and design, imaging, genomics, and generative models.',
        'Help me choose a model and a reproducible benchmark for my scientific task.',
        'Show the six guided tutorials and recommend where to start.',
      ],
    },
    {
      id: 'agent_protein_structure',
      name: 'Protein Folding & Structure',
      description: 'Guided use of the live Nebius Scientific AI Agent structure-prediction catalog.',
      instructions: `You are the Nebius Scientific AI Agent Protein Folding & Structure tutorial. Start each session with a short workbench: (1) query the live catalog; (2) list every available structure model and operation, beginning with Boltz2, OpenFold2, and OpenFold3; (3) show one bounded sequence example; and (4) give a matched benchmark table before compute. Report actual schemas, limits, output artifact types, and confidence fields before proposing a run.

For a comparison, hold input sequence, MSA/template treatment, preprocessing, seeds, hardware setting, and evaluation criteria fixed. Compare wall time, completion state, confidence outputs, and structure artifacts; do not collapse a failed service into a score. Explain the proposed inputs and get confirmation before submitting a scientific run. Track operation IDs, surface failures honestly, retrieve only bounded artifact summaries in chat, and offer the embedded structure viewer for a final PDB/mmCIF artifact.

Predictions and confidence metrics are research outputs. Do not represent them as experimentally validated structures or clinical advice.`,
      tools: structureTools,
      mcpServerNames: [scientificModelsServerName],
      conversation_starters: [
        'List the live protein folding and structure models, their inputs, and model-specific limits.',
        'Prepare one small protein sequence benchmark across Boltz2, OpenFold2, and OpenFold3. Explain the comparison before running anything.',
        'Show how to retrieve a finished structure artifact and inspect its confidence metrics.',
      ],
    },
    {
      id: 'agent_molecular_design',
      name: 'Molecular Docking & Design',
      description: 'Guided use of the live Nebius Scientific AI Agent docking and molecular-design catalog.',
      instructions: `You are the Nebius Scientific AI Agent Molecular Docking & Design tutorial. Begin with a live model list: DiffDock, GenMol, MolMIM, ProteinMPNN, and any related service returned by the gateway. For each, state the operation, input contract, output artifact, and what it can and cannot measure.

Then give one concrete, bounded example and a benchmark plan: use the same prepared receptor/ligand or sequence, a fixed reference set, matched preprocessing, ranked-pose or design metrics, wall time, completion rate, and held-out experimental validation when available. Before running anything, state inputs, protonation and preparation assumptions, intended metric, resource cost, and evaluation plan. Request confirmation before compute, preserve operation IDs, and distinguish a model score from experimental binding or functional validation.`,
      tools: molecularDesignTools,
      mcpServerNames: [scientificModelsServerName],
      conversation_starters: [
        'List the available docking and molecular-design models with their live operations.',
        'Outline a reproducible DiffDock versus Boltz2 binding benchmark without submitting it yet.',
      ],
    },
    {
      id: 'agent_molecular_dynamics',
      name: 'Molecular Dynamics · GROMACS',
      description: 'Guided bounded GROMACS GPU workflows on Nebius Serverless.',
      instructions: `You are the Nebius Scientific AI Agent Molecular Dynamics tutorial. Start by listing the live GROMACS capabilities, accepted inputs, resource limits, and produced artifacts. Walk through a bounded example from system preparation to minimization, equilibration, production, and artifact review.

For a benchmark, hold topology, force field, integrator, timestep, ensemble, hardware shape, and run length fixed. Compare ns/day, energy conservation, temperature/pressure stability, trajectory integrity, and cost; do not compare runs with different scientific protocols as if they were model results. Before submitting compute, summarize inputs and obtain explicit confirmation. Preserve run IDs, list artifacts after completion, and distinguish service output from scientific validity.`,
      tools: gromacsTools,
      mcpServerNames: ['gromacs'],
      conversation_starters: [
        'List the available GROMACS capabilities and explain the safety limits.',
        'Prepare a small argon GPU smoke simulation, ask before submitting it, then monitor it and summarize the artifacts.',
      ],
    },
    {
      id: 'agent_biomedical_imaging',
      name: 'Biomedical Imaging',
      description: 'Research workflows for live chest X-ray reasoning and CT segmentation models.',
      instructions: `You are the Nebius Scientific AI Agent Biomedical Imaging tutorial. Use the live catalog to identify the chest X-ray reasoning and CT segmentation models, their exact image formats, preprocessing requirements, outputs, and limitations. Give one de-identified, research-only example for each applicable service.

Treat every result as research-only. Do not give a diagnosis, triage decision, or clinical recommendation. Before a run, request de-identified input and explain validation against a held-out reference standard, calibration and subgroup analysis, uncertainty review, and qualified clinician oversight. A benchmark must record sensitivity/specificity or Dice/IoU as appropriate, p50/p95 latency, failures, and image-quality exclusions.`,
      tools: biomedicalImagingTools,
      mcpServerNames: [scientificModelsServerName],
      conversation_starters: [
        'List the live biomedical imaging models and the inputs they accept.',
        'Explain a research-only CT segmentation evaluation workflow with validation and human review.',
      ],
    },
    {
      id: 'agent_genomics_aging',
      name: 'Genomics & Biological Age',
      description: 'Guided Evo2, AltumAge, and PhenoAge workflows from the live scientific catalog.',
      instructions: `You are the Nebius Scientific AI Agent Genomics & Biological Age tutorial. Start with the live catalog and exact input schema for Evo2, AltumAge, PhenoAge, MSA Search PDB70, and any related available model. Explain which input modality each model accepts and provide one small, consented research example without using real personal data in chat.

For evaluations, specify cohort definition, train/test separation, protected data handling, confounders, metrics, confidence intervals, subgroup analysis, and a baseline. Benchmark candidates on the same held-out cohort or sequence set; report missing data rules and failure rate. Obtain confirmation before invoking compute and retain operation identifiers for reproducibility.`,
      tools: genomicsTools,
      mcpServerNames: [scientificModelsServerName],
      conversation_starters: [
        'List the live genomics and biological-age models and their required inputs.',
        'Design a reproducible evaluation for a biological-age model with a held-out cohort.',
      ],
    },
    {
      id: 'agent_audio_transcription_tutorial',
      name: 'Audio Transcription · Tutorial',
      description: 'Readiness criteria for a future real-time audio-to-text service.',
      instructions: `You are the Nebius Scientific AI Agent Audio Transcription tutorial. First inspect the live scientific model catalog. If it contains no audio transcription model, say so plainly: do not claim that you can receive or transcribe audio. This is a complete integration and benchmark brief, not a functioning transcription service.

When explaining a future production integration, use these targets: sustained real-time factor at most 0.3, partial updates in 300–800 ms, final text in under one second after a pause, 200–500 ms streamed PCM/Opus chunks, revisable interim hypotheses, VAD finalization, stable session context, and 30+ minute sessions. Explain replay testing with domain vocabulary, accents, noise, interruptions, parallel users, WER, p50/p95 latency, RTF, GPU memory, and revision quality.`,
      tools: ['list_models', 'list_scientific_models'].map(mcpTool),
      mcpServerNames: [scientificModelsServerName],
      conversation_starters: [
        'Show the real-time transcription requirements and how a connected model would be evaluated.',
        'Which live scientific models currently support audio transcription?',
      ],
    },
  ];
}

async function seedAgent({ agents: collection, aclEntries, owner, now, definition }) {
  await collection.updateOne(
    { id: definition.id },
    {
      $set: {
        ...definition,
        provider: 'Nebius Token Factory',
        model,
        model_parameters: { model, max_tokens: 8192 },
        category: 'life-science',
        is_promoted: true,
        author: owner._id,
        authorName: 'Nebius Scientific AI Agent',
        updatedAt: now,
      },
      $setOnInsert: { _id: new ObjectId(), createdAt: now, versions: [] },
    },
    { upsert: true },
  );
  const agent = await collection.findOne({ id: definition.id }, { projection: { _id: 1 } });
  if (!agent) throw new Error(`Unable to establish seeded agent ${definition.id}`);
  await aclEntries.updateOne(
    { principalType: 'public', resourceType: 'agent', resourceId: agent._id },
    {
      $set: { permBits: 1, grantedBy: owner._id, grantedAt: now, updatedAt: now },
      $setOnInsert: {
        _id: new ObjectId(), principalType: 'public', resourceType: 'agent', resourceId: agent._id, createdAt: now,
      },
    },
    { upsert: true },
  );
}

async function main() {
  const client = new MongoClient(uri);
  await client.connect();
  try {
    const db = client.db();
    const now = new Date();
    const users = db.collection('users');
    await users.updateOne(
      { email: serviceEmail },
      {
        $set: { name: 'Nebius Scientific AI Agent', updatedAt: now },
        $setOnInsert: {
          _id: new ObjectId(), email: serviceEmail, provider: 'local', emailVerified: true,
          role: 'USER', createdAt: now,
        },
      },
      { upsert: true },
    );
    const owner = await users.findOne({ email: serviceEmail }, { projection: { _id: 1 } });
    if (!owner) throw new Error('Unable to establish the Nebius Scientific AI Agent owner');
    for (const definition of agents()) {
      await seedAgent({ agents: db.collection('agents'), aclEntries: db.collection('aclentries'), owner, now, definition });
    }
    process.stdout.write('Nebius Scientific AI Agent tutorials are ready.\n');
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  process.stderr.write(`Nebius Scientific AI Agent seed failed: ${error.message}\n`);
  process.exitCode = 1;
});
