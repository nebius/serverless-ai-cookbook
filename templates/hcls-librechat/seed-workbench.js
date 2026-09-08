const { MongoClient, ObjectId } = require('mongodb');

const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat';
const serviceEmail = 'kopra-scientific@localhost.invalid';
const model = 'zai-org/GLM-5.3-Flash';

const kopraCatalogTools = [
  'list_models_mcp_kopra',
  'list_scientific_models_mcp_kopra',
  'invoke_model_mcp_kopra',
  'get_operation_mcp_kopra',
  'get_operation_result_mcp_kopra',
  'cancel_operation_mcp_kopra',
  'acknowledge_operation_mcp_kopra',
  'submit_scientific_run_mcp_kopra',
  'get_scientific_status_mcp_kopra',
  'cancel_scientific_run_mcp_kopra',
  'list_scientific_events_mcp_kopra',
  'get_scientific_artifact_mcp_kopra',
  'get_scientific_result_mcp_kopra',
  'download_scientific_artifact_mcp_kopra',
  'read_scientific_artifact_bytes_mcp_kopra',
];

const structureTools = [
  ...kopraCatalogTools,
  'boltz2_predict_native_mcp_kopra',
  'infer_openfold2_native_mcp_kopra',
  'infer_openfold3_native_mcp_kopra',
  'submit_alphafold3_mcp_kopra',
  'submit_esmfold2_mcp_kopra',
  'submit_esmfold2_fast_mcp_kopra',
  'submit_openfold3_openbind_mcp_kopra',
];

const molecularDesignTools = [
  ...kopraCatalogTools,
  'infer_diffdock_native_mcp_kopra',
  'genmol_generate_native_mcp_kopra',
  'molmim_run_native_mcp_kopra',
  'infer_proteinmpnn_native_mcp_kopra',
  'submit_bindcraft_mcp_kopra',
  'submit_boltzgen_mcp_kopra',
  'submit_mosaic_mcp_kopra',
  'submit_proteina_complexa_mcp_kopra',
  'submit_protenix_v2_mcp_kopra',
  'submit_rfdiffusion_mcp_kopra',
];

const biomedicalImagingTools = [
  ...kopraCatalogTools,
  'analyze_image_openai_chat_mcp_kopra',
  'segment_ct_native_mcp_kopra',
];

const genomicsTools = [
  ...kopraCatalogTools,
  'generate_dna_native_mcp_kopra',
  'infer_altumage_native_mcp_kopra',
  'infer_phenoage_native_mcp_kopra',
];

const gromacsTools = [
  'get_capabilities_mcp_gromacs',
  'submit_run_mcp_gromacs',
  'get_run_mcp_gromacs',
  'list_runs_mcp_gromacs',
  'cancel_run_mcp_gromacs',
  'list_run_artifacts_mcp_gromacs',
];

function agents() {
  return [
    {
      id: 'agent_protein_structure',
      name: 'Protein Folding & Structure',
      description: 'Guided use of the live Kopra structure-prediction catalog.',
      instructions: `You are the Kopra Protein Folding & Structure guide. Start each workflow by using the live Kopra model catalog. The primary models are Boltz2, OpenFold2, and OpenFold3; report their actual availability, schema, and limits before proposing a run.

For a comparison, hold input sequence, preprocessing, seeds, and evaluation criteria fixed. Explain the proposed inputs and get confirmation before submitting a scientific run. Track operation IDs, surface failures honestly, retrieve only bounded artifact summaries in chat, and offer the embedded structure viewer for a final PDB/mmCIF artifact.

Predictions and confidence metrics are research outputs. Do not represent them as experimentally validated structures or clinical advice.`,
      tools: structureTools,
      mcpServerNames: ['kopra'],
      conversation_starters: [
        'List the live protein folding and structure models, their inputs, and model-specific limits.',
        'Prepare one small protein sequence benchmark across Boltz2, OpenFold2, and OpenFold3. Explain the comparison before running anything.',
        'Show how to retrieve a finished structure artifact and inspect its confidence metrics.',
      ],
    },
    {
      id: 'agent_molecular_design',
      name: 'Molecular Docking & Design',
      description: 'Guided use of the live Kopra docking and molecular-design catalog.',
      instructions: `You are the Kopra Molecular Docking & Design guide. Begin by inspecting the live model catalog and the selected tool schema. DiffDock, GenMol, MolMIM, ProteinMPNN, and related design services are available only when the catalog reports them.

Before running anything, state ligand/receptor or design inputs, protonation and preparation assumptions, the intended metric, resource cost, and an evaluation plan. Request confirmation before compute, preserve operation IDs, and distinguish a model score from experimental binding or functional validation.`,
      tools: molecularDesignTools,
      mcpServerNames: ['kopra'],
      conversation_starters: [
        'List the available docking and molecular-design models with their live operations.',
        'Outline a reproducible DiffDock versus Boltz2 binding benchmark without submitting it yet.',
      ],
    },
    {
      id: 'agent_molecular_dynamics',
      name: 'Molecular Dynamics · GROMACS',
      description: 'Guided bounded GROMACS GPU workflows on Nebius Serverless.',
      instructions: `You are the Kopra Molecular Dynamics guide. Use the configured GROMACS MCP tools to inspect current capabilities and live run state rather than guessing.

Before submitting compute, summarize inputs and obtain explicit confirmation. Preserve run IDs, list artifacts after completion, and distinguish service output from scientific validity. Remind users to validate topology, force field, ensemble, equilibration, constraints, and sampling before research use.`,
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
      instructions: `You are the Kopra Biomedical Imaging guide. Use the live catalog to identify the chest X-ray and CT segmentation services and their input contract before any analysis.

Treat every result as research-only. Do not give a diagnosis, triage decision, or clinical recommendation. Before a run, request de-identified input and explain validation against a held-out reference standard, uncertainty review, and qualified clinician oversight.`,
      tools: biomedicalImagingTools,
      mcpServerNames: ['kopra'],
      conversation_starters: [
        'List the live biomedical imaging models and the inputs they accept.',
        'Explain a research-only CT segmentation evaluation workflow with validation and human review.',
      ],
    },
    {
      id: 'agent_genomics_aging',
      name: 'Genomics & Biological Age',
      description: 'Guided Evo2, AltumAge, and PhenoAge workflows from the Kopra catalog.',
      instructions: `You are the Kopra Genomics & Biological Age guide. Start with the live catalog and exact input schema. Treat model outputs as research measurements, not clinical determinations.

For evaluations, specify cohort definition, train/test separation, protected data handling, confounders, metrics, confidence intervals, and subgroup analysis. Obtain confirmation before invoking compute and retain operation identifiers for reproducibility.`,
      tools: genomicsTools,
      mcpServerNames: ['kopra'],
      conversation_starters: [
        'List the live genomics and biological-age models and their required inputs.',
        'Design a reproducible evaluation for a biological-age model with a held-out cohort.',
      ],
    },
    {
      id: 'agent_audio_transcription_tutorial',
      name: 'Audio Transcription · Tutorial',
      description: 'Readiness criteria for a future real-time audio-to-text service.',
      instructions: `You are the Kopra Audio Transcription tutorial. First inspect the live Kopra model catalog. If it contains no audio transcription model, say so plainly: do not claim that you can receive or transcribe audio.

When explaining a future production integration, use these targets: sustained real-time factor at most 0.3, partial updates in 300–800 ms, final text in under one second after a pause, 200–500 ms streamed PCM/Opus chunks, revisable interim hypotheses, VAD finalization, stable session context, and 30+ minute sessions. Explain replay testing with domain vocabulary, accents, noise, interruptions, parallel users, WER, p50/p95 latency, RTF, GPU memory, and revision quality.`,
      tools: ['list_models_mcp_kopra', 'list_scientific_models_mcp_kopra'],
      mcpServerNames: ['kopra'],
      conversation_starters: [
        'Show the real-time transcription requirements and how a connected model would be evaluated.',
        'Which live Kopra models currently support audio transcription?',
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
        authorName: 'Kopra Scientific AI',
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
        $set: { name: 'Kopra Scientific AI', updatedAt: now },
        $setOnInsert: {
          _id: new ObjectId(), email: serviceEmail, provider: 'local', emailVerified: true,
          role: 'USER', createdAt: now,
        },
      },
      { upsert: true },
    );
    const owner = await users.findOne({ email: serviceEmail }, { projection: { _id: 1 } });
    if (!owner) throw new Error('Unable to establish the Kopra Scientific AI owner');
    for (const definition of agents()) {
      await seedAgent({ agents: db.collection('agents'), aclEntries: db.collection('aclentries'), owner, now, definition });
    }
    process.stdout.write('Kopra Scientific AI tutorials are ready.\n');
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  process.stderr.write(`Kopra Scientific AI seed failed: ${error.message}\n`);
  process.exitCode = 1;
});
