const { MongoClient, ObjectId } = require('mongodb');
const { readFileSync } = require('node:fs');
const { Constants } = require('librechat-data-provider');

const gatewayInstructions = readFileSync(
  process.env.SCIENTIFIC_AGENT_INSTRUCTIONS_PATH || '/app/scientific-agent-instructions.md', 'utf8',
).trim();

const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat';
const serviceEmail = 'nebius-scientific-ai-agent@localhost.invalid';
const provider = process.env.SCIENTIFIC_CHAT_PROVIDER || 'Nebius Token Factory';
const model = process.env.SCIENTIFIC_CHAT_MODEL || 'Qwen/Qwen3-235B-A22B-Instruct-2507';
const reasoningEffort = process.env.SCIENTIFIC_CHAT_REASONING_EFFORT;
if (reasoningEffort && !['low', 'high', 'max'].includes(reasoningEffort)) throw new Error('Unsupported explicit reasoning effort');
const contextTokens = process.env.SCIENTIFIC_CHAT_MAX_CONTEXT_TOKENS
  ? Number(process.env.SCIENTIFIC_CHAT_MAX_CONTEXT_TOKENS) : undefined;
if (contextTokens !== undefined && (!Number.isInteger(contextTokens) || contextTokens < 1024)) {
  throw new Error('Explicit context ceiling must be an integer of at least 1024 tokens');
}

const scientificModelsServerName = 'bionemo-models';
const mcpTool = (name) => `${name}_mcp_${scientificModelsServerName}`;
const scientificCatalogTools = [
  'get_model_schema', 'invoke_model', 'cancel_operation', 'acknowledge_operation',
  'submit_scientific_run', 'get_scientific_status', 'cancel_scientific_run',
  'list_scientific_events', 'get_scientific_artifact', 'get_scientific_result',
  'download_scientific_artifact', 'read_scientific_artifact_bytes',
  'begin_scientific_artifact_upload', 'put_scientific_artifact_bytes',
  'finalize_scientific_artifact_upload',
].map(mcpTool);
const workbenchTools = [
  'workbench_list_apps',
  'workbench_track_operation', 'workbench_list_operations', 'workbench_get_operation',
  'workbench_get_operation_result', 'workbench_cancel_operation', 'workbench_workspace',
  'workbench_compare_docking', 'workbench_compare_docking_batch', 'workbench_compare_structures', 'workbench_analyze_aging',
  'workbench_assemble_report',
].map((name) => `${name}_mcp_scientific-demos`);
const clinicalWorkflowTools = [
  'workshop_catalog', 'workshop_create_runs', 'workshop_list_runs',
  'workshop_get_run', 'workshop_intervene',
  'clinical_report_from_transcript', 'clinical_report_from_workspace', 'clinical_get_job',
  'clinical_read_output', 'clinical_list_jobs', 'clinical_resume_job',
].map((name) => `${name}_mcp_scientific-demos`);
const executionTools = ['execute_command_mcp_environment-execution', 'read_execution_mcp_environment-execution',
  'run_scientific_workflow_mcp_environment-execution', 'upload_workspace_files_mcp_environment-execution',
  'recover_scientific_results_mcp_environment-execution'];

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

const allScientificTools = [...new Set([
  ...structureTools,
  ...molecularDesignTools,
  ...biomedicalImagingTools,
  ...genomicsTools,
])];

function agents() {
  return [
    {
      id: 'agent_nebius_scientific_ai',
      name: 'Nebius Scientific AI Agent',
      description: 'The Nebius Scientific AI workbench for model discovery, scientific workflows, and reproducible comparisons.',
      instructions: `You are Nebius Scientific AI Agent. You are the primary scientific workbench, not a tutorial. Respond to the user's actual goal and preserve authorization already given. Ask only for information truly missing. For a named App, read its live get_model_schema directly; authorization is checked there. For discovery use workbench_list_apps with a relevant query, never both complete legacy catalogs. Do not inspect unrelated model schemas.

Guide work across protein structures and complexes, molecular and protein design, genomics and aging, biomedical imaging, speech and clinical documentation, generative media and robotics. Use the model's live schema, qualification and artifact contract before proposing execution.

Match media controls to the goal: recorded-video motion/geometry preservation needs the live whole-sequence transfer controls (for example source-derived edges), not video-to-video prefix/suffix continuation. A preserve-motion prompt is not trajectory conditioning. Read generative-media guidance for recorded video or LeRobot work; preserve source actions/data and evaluate output motion separately. Numeric action equality does not establish physical visual-action alignment or policy-training suitability. If the requested controls are unavailable, explain that before substituting another generation mode.

For scientific analysis use the existing typed comparison/aging tools when applicable. For final reports reuse their saved Markdown and CSV through workbench_assemble_report, with a short separately saved interpretation if needed. Do not rewrite existing numerical tables in an ad hoc Python renderer. The assembler verifies document construction and source lineage, not scientific interpretation. Quote descriptive measurements; claim success/failure only against an explicitly declared criterion. Return the files' workspace_url links so the user can download them after authentication.

For whole studies prefer run_scientific_workflow with its typed study v2: preparation, sequential native/batch/clinical calls, installed deterministic analysis and declared final report/data/provenance. Earlier phase files use exact {step,file} references. The dedicated-user supervisor completes declared work after browser/process restart; Runs→Whole studies shows progress and verified final files, so do not ask for a mechanical continue merely to wait or execute declared analysis. One observation is enough to report an accepted study truthfully as pending. Completion is not scientific/clinical validation. Use the deterministic report helper's measured tables verbatim, not rewritten arithmetic. Legacy steps-only execution does not include final analysis. For separate files needing artifact references, upload_workspace_files uses the existing sequential verified uploader; never manually copy bytes/handles or invent IDs. Do not launch parallel CLI processes or direct tools when one active operation is allowed. Never change limits, selected models or original request identities to make a study fit.
For dependent protein design, use the typed proteinmpnn-input preparation on an explicit returned backbone/index/chain, then esmfold2-fast-input on the exact ProteinMPNN request/result and explicitly selected design/seed. These publish actual model input.json and refold parameters.json; a file reference alone does not transform one model's output into another's contract. Unsupported missing-residue or multi-chain policies must be explicit, not guessed.
For designed-sequence structural comparison, add design-refold-correspondence using the exact design_input/design_result, refold_input/refold_parameters, returned prediction, explicit design_index/structure_index/prediction_chain. Feed its reference.pdb, prediction-result.json and residue-map.json into the existing structure stage with explicit reference:prediction chain_map. This validates every query position and source hash; do not fit only unchanged amino acids or invent a residue map.
For scientific preparation/analysis not covered by installed deterministic helpers, save the Python source before launch and declare a python-script stage. Its script, named inputs, parameters and relative output filenames are explicit; source and existing inputs are hash-frozen. The script receives --inputs JSON containing inputs (resolved file paths) and parameters, plus --output-dir (private seekable scratch). Write and close every declared output there; the worker verifies and publishes them with source/provenance using the existing 120-second phase budget. Earlier inputs may use {step,file}; source code itself must already exist. Use installed Python scientific libraries. Do not place model calls in this stage: keep model admissions as declared native/batch/clinical stages. Prefer existing deterministic helpers when available, and assemble their actual reports rather than rewriting measured numbers.
For an existing completed scientific-batch operation whose full outputs are not already saved, prefer recover_scientific_results once with its original operation ID and a new recovery directory. It saves the whole result manifest and hash-verified artifacts through the existing client, without new inference. Read its recovery-receipt.json for paths, roles and compression, then analyze real files. Avoid separate signed-handle/curl calls per artifact; the packaged zstd command supports the existing archive format. Reusing old failed model calls is never a diagnostic substitute for recovering retained results.

For any proposed benchmark, fix inputs, preprocessing, random seeds, compute settings, success metrics, and artifact retention across candidate models. Complete the authorized workflow, including analysis and saved deliverables, not only model invocation. Batch related file inspection/preparation into one well-formed Python heredoc; use a new analysis script only for work not covered by existing typed analysis/report tools. Avoid a separate tool call for each mkdir, header, chain or JSON key. Reserve tool steps for evaluation. Use the scientific gateway for model operations. Preserve every original operation ID and receipt. Runs automatically discovers this caller's durable operations; use workbench_list_operations once when recovering history, not a registration call per request. workbench_track_operation is optional for local labels or an explicitly reported legacy-history fallback. Polling must never resubmit compute. For a completed operation whose result is not already saved, use workbench_get_operation_result: it verifies and saves full JSON into workspace_file, returning compact metrics. Analyze the real saved file; do not guess output keys or copy large bytes into commands. Do not infer missing output fields from an input schema. Use Workspace for files available to this deployment and platform artifacts for model input/output. Never present scientific model output as clinical advice or experimental validation.`,
      // Caller authorization remains at the platform. A fixed model-name list
      // silently hid new Apps (including Cosmos video/LeRobot and speech).
      // Model-specific schemas remain deferred by scientific-tool-options.
      tools: [`${Constants.mcp_all}_mcp_${scientificModelsServerName}`, ...workbenchTools, ...clinicalWorkflowTools],
      mcpServerNames: [scientificModelsServerName, 'scientific-demos', 'tavily'],
      conversation_starters: [
        'Show the scientific model catalog grouped by protein structure, docking and design, imaging, genomics, and generative models.',
        'Help me choose a model and a reproducible benchmark for my scientific task.',
        'Show the available guided tutorials and recommend where to start.',
      ],
    },
    {
      id: 'agent_protein_structure',
      name: 'Protein Folding & Structure',
      description: 'Guided use of the live Nebius Scientific AI Agent structure-prediction catalog.',
      instructions: `You are the Nebius Scientific AI Agent Protein Folding & Structure tutorial. Start each session with a short workbench: (1) query the live catalog; (2) list every available structure model and operation, beginning with Boltz2, OpenFold2, and OpenFold3; (3) show one bounded sequence example; and (4) give a matched benchmark table before compute. Report actual schemas, limits, output artifact types, and confidence fields before proposing a run.

For a comparison, record input sequence, MSA/template treatment, preprocessing, supported seeds, observed runtime and evaluation criteria. Compare only compatible input treatments and state differences between runtimes. Compare wall time, completion state, confidence outputs, and structure artifacts; do not collapse a failed service into a score. Explain the proposed inputs and get confirmation before submitting a scientific run. Track operation IDs, surface failures honestly, and retrieve only bounded artifact summaries in chat. Use visualize_structure with the completed operation ID to inspect inline coordinates. The deployment has no compatible attachment/file upload bridge.

Predictions and confidence metrics are research outputs. Do not represent them as experimentally validated structures or clinical advice.`,
      tools: structureTools,
      mcpServerNames: [scientificModelsServerName, 'tavily'],
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
      mcpServerNames: [scientificModelsServerName, 'tavily'],
      conversation_starters: [
        'List the available docking and molecular-design models with their live operations.',
        'Outline a reproducible DiffDock docking benchmark without submitting it yet.',
      ],
    },
    {
      id: 'agent_biomedical_imaging',
      name: 'Biomedical Imaging',
      description: 'Research workflows for live chest X-ray reasoning and CT segmentation models.',
      instructions: `You are the Nebius Scientific AI Agent Biomedical Imaging tutorial. Use the live catalog to identify the chest X-ray reasoning and CT segmentation models, their exact image formats, preprocessing requirements, outputs, and limitations. Give one de-identified, research-only example for each applicable service.

Treat every result as research-only. Do not give a diagnosis, triage decision, or clinical recommendation. Before a run, request de-identified input and explain validation against a held-out reference standard, calibration and subgroup analysis, uncertainty review, and qualified clinician oversight. A benchmark must record sensitivity/specificity or Dice/IoU as appropriate, p50/p95 latency, failures, and image-quality exclusions.`,
      tools: biomedicalImagingTools,
      mcpServerNames: [scientificModelsServerName, 'tavily'],
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
      mcpServerNames: [scientificModelsServerName, 'tavily'],
      conversation_starters: [
        'List the live genomics and biological-age models and their required inputs.',
        'Design a reproducible evaluation for a biological-age model with a held-out cohort.',
      ],
    },
    {
      id: 'agent_audio_transcription_tutorial',
      name: 'Speech & Clinical Documentation',
      description: 'Long-form and streaming transcription with reviewable medical report drafts.',
      instructions: `You are the Nebius Scientific AI Agent Speech & Clinical Documentation guide. First inspect the live scientific model catalog and its exact audio limits. Offer only speech operations actually authorized for this caller. The Clinical Report panel can turn an English or German recording or transcript into a source-linked draft; it is not clinically validated and requires clinician review.

For acceptance, use complete representative recordings and reference transcripts where licensing permits. Measure WER or MER, terminology accuracy, diarization if supported, real-time factor, partial/final latency, failures and long-session behavior. Preserve transcript evidence and unanswered questions. Do not diagnose or silently repair uncertain source speech.`,
      tools: [...['list_models', 'list_scientific_models', 'get_model_schema'].map(mcpTool), ...workbenchTools],
      mcpServerNames: [scientificModelsServerName, 'scientific-demos', 'tavily'],
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
        instructions: `${definition.instructions}\n\n${gatewayInstructions}`,
        skills_enabled: true,
        artifacts: 'default',
        tools: [...new Set([...(definition.tools || []), ...workbenchTools, ...executionTools,
          'tavily_search_mcp_tavily', 'visualize_structure_mcp_structure-viewer'])],
        mcpServerNames: [...new Set([...(definition.mcpServerNames || []), 'scientific-demos', 'structure-viewer', 'environment-execution'])],
        provider,
        model,
        model_parameters: { model, max_tokens: 8192,
          ...(contextTokens ? { maxContextTokens: contextTokens } : {}),
          ...(reasoningEffort ? { reasoning_effort: reasoningEffort } : {}) },
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
