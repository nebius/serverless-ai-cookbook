/* Seed the operator-owned, publicly selectable Scientific AI Platform agent. */
const { MongoClient, ObjectId } = require('mongodb');

const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat';
// LibreChat reserves the `agent_` prefix for persisted agents. Without it the
// request loader treats this as an ephemeral agent and discards its model.
const agentId = 'agent_scientific_ai_platform';
const serviceEmail = 'scientific-ai-platform@localhost.invalid';
const now = new Date();

const instructions = `You are the Scientific AI Platform assistant. Use the configured tools rather than guessing. Present the platform as a general scientific computing environment and base every answer on the current user's goal, live catalog, and available files.

For requests to list, compare, select, or invoke hosted models, query the bionemo-models MCP catalog for this user first. Call get_model_schema for the selected public model ID and protocol, then prefer the returned named typed tool with flat model fields. Do not send HTTP operation/payload wrappers to named MCP tools, add a model field to a named chat tool, or guess from vendor examples. Save the operation ID: submission is durable acceptance, not a final prediction. Poll get_operation/get_operation_result; for scientific batches poll get_scientific_status and the operation history, wait for result publication, then fetch the result and artifacts. Do not resubmit or cancel merely because a chat or tool wait timed out. For a demo request, first show the models currently available in the requested group, then give a bounded example based on each model's live input schema, and finish with a reproducible benchmark plan for comparable models. Demos are planning-first: do not submit model jobs, download public inputs, use Tavily, write files, poll jobs, or retry failed jobs unless the user explicitly selects a run. State that the example and benchmark are ready to run and ask the user which single workflow to execute. In a structure demo, distinguish prediction models (OpenFold2, OpenFold3, Boltz2) from supporting embedding models (ESM2 and ESMC); do not call embeddings structure predictors. For current literature or web evidence, call Tavily and cite the returned sources.

Never place PDB, mmCIF, response.json, base64 data, or an artifact chunk in chat. Keep large artifact bytes out of direct tool arguments too: use the file bridge and signed upload/download handles. When a model job succeeds, read its result document via the scientific-model gateway (get_operation_result / get_scientific_result) for the fields the selected runtime actually returns, download structure artifacts with download_scientific_artifact (or HTTP result/artifact endpoints), verify their digest and render locally with the structure viewer so large files stay outside the model context. Do not fabricate affinity or confidence fields that the selected runtime does not return.

The landing page presents four visual demo cards that create real chats. The instance-admin MCP is owner-authorized: it can write and execute code, install packages, download files, and convert artifacts. Its default working directory is /workspace/shared, a writable bucket mount that persists across instance restarts. Use it when the user asks for work on the instance, keep durable files in /workspace/shared, and report commands and generated paths. For a model input that already exists on the instance, upload the actual bytes to the Scientific AI gateway with begin_scientific_artifact_upload / put_scientific_artifact_bytes / finalize_scientific_artifact_upload and use the returned immutable artifact reference in the input_manifest; the remote gateway cannot see this instance’s filesystem. Use the installed structure, image, video, audio, and analysis workflows to present verified outputs clearly. Treat model outputs as research hypotheses and make benchmark inputs, models, timing, and failures explicit.`;

// `mcpServerNames` below attaches each complete live server through LibreChat's
// dynamic MCP wildcard. Do not pin stale tool IDs: the model catalog and each
// user's authorization-aware tool list can change independently of this image.
const tools = [];

const tutorialPrompts = [
  {
    command: 'scientific-ai-model-catalog',
    name: 'Live Model Catalog',
    oneliner: 'Explore the live catalog by scientific use case and choose a visual demo.',
    prompt: 'Show the live Scientific AI model catalog for this user. Group ready Apps by scientific use case, distinguish native, chat, and scientific-batch contracts, and recommend one visually compelling demo per group. Use focused live discovery and do not claim an App is available unless discovery returns it.',
  },
  {
    command: 'scientific-ai-protein-folding',
    name: 'Protein Folding & Structure',
    oneliner: 'List live structure models, show bounded examples, and prepare an opt-in benchmark.',
    prompt: 'Start the Protein Folding & Structure tutorial. Query the gateway discovery tools (list_models and list_scientific_models) and provide a concise planning-first lesson: (1) list the live structure prediction models separately from supporting embedding models, (2) show a bounded, schema-accurate example request for each predictor without submitting it, and (3) give a fixed-input benchmark design with metrics, failure criteria, and one optional single-run choice. Do not submit jobs, download a public sequence, write files, poll, retry, or render a protein until the user explicitly chooses a run. If they choose a successful structure run, read the result document and download the structure artifact via the gateway, then render it with the local structure viewer; never put CIF or PDB data in chat or a tool argument.',
  },
  {
    command: 'scientific-ai-docking-design',
    name: 'Docking & Molecular Design',
    oneliner: 'Explore live molecular-design models and build a comparable docking benchmark.',
    prompt: 'Start the Docking & Molecular Design tutorial. List the live models in this group with the gateway discovery tools (list_models / list_scientific_models), show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Explain appropriate scores, timing, inputs, and failure criteria.',
  },
  {
    command: 'scientific-ai-sequence-msa',
    name: 'Sequence & MSA',
    oneliner: 'Explore sequence, MSA, and embedding models with a reproducible comparison plan.',
    prompt: 'Start the Sequence & MSA tutorial. List the live models in this group with the gateway discovery tools (list_models / list_scientific_models), show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Include inputs, expected artifacts, comparable metrics, timings, and failure criteria.',
  },
  {
    command: 'scientific-ai-genomics-cell-biology',
    name: 'Genomics & Cell Biology',
    oneliner: 'Explore genomics, single-cell, imaging, and variant-calling models.',
    prompt: 'Start the Genomics & Cell Biology tutorial. List the live models in this group with the gateway discovery tools (list_models / list_scientific_models), show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Include data requirements, expected artifacts, comparable metrics, timings, and failure criteria.',
  },
  {
    command: 'scientific-ai-visual-imaging',
    name: 'Imaging & Segmentation',
    oneliner: 'Plan a visual demo with chest X-ray, CT, microscopy, SAM2, or single-cell data.',
    prompt: 'Plan a visual Scientific AI demo using one currently available imaging workflow: chest X-ray reasoning, CT segmentation, Cellpose microscopy masks, SAM2 image or video tracking, or scVI/scANVI UMAP. Discover the exact live App and schema, identify a suitable file already in /workspace when available, and explain the visual output. Do not submit compute until I choose the workflow.',
  },
  {
    command: 'scientific-ai-generative-media',
    name: 'Generative Media & Physical AI',
    oneliner: 'Plan generated video, physical-AI augmentation, or soundtrack workflows.',
    prompt: 'Plan a generative-media demo from the live catalog. Compare available Wan and Cosmos video Apps, identify physical-AI augmentation options, and include ACE-Step for an instrumental soundtrack only if it is currently discoverable and ready. Use each App’s exact schema and wait for my choice before submitting compute.',
  },
  {
    command: 'scientific-ai-speech',
    name: 'Speech Transcription',
    oneliner: 'Transcribe an uploaded recording and retain the complete timed result.',
    prompt: 'Plan a speech transcription demo for an audio file in /workspace. Discover the available ASR and diarization Apps, compare their exact supported inputs and outputs, and propose one run that retains the complete transcript, timing segments, provenance, and downloadable files. Do not submit compute until I choose the model and file.',
  },
];

async function seedTutorialPrompts(db, owner) {
  const promptGroups = db.collection('promptgroups');
  const prompts = db.collection('prompts');
  const aclEntries = db.collection('aclentries');
  for (const tutorial of tutorialPrompts) {
    await promptGroups.updateOne(
      { command: tutorial.command },
      {
        $set: {
          name: `Scientific AI Demo · ${tutorial.name}`,
          numberOfGenerations: 0,
          oneliner: tutorial.oneliner,
          category: 'Scientific AI',
          author: owner._id,
          authorName: 'Scientific AI Platform',
          command: tutorial.command,
          updatedAt: now,
        },
        $setOnInsert: { _id: new ObjectId(), productionId: new ObjectId(), createdAt: now },
      },
      { upsert: true },
    );
    const group = await promptGroups.findOne({ command: tutorial.command });
    if (!group) throw new Error(`Unable to establish tutorial prompt ${tutorial.command}`);
    await prompts.updateOne(
      { groupId: group._id, author: owner._id },
      {
        $set: { prompt: tutorial.prompt, type: 'text', updatedAt: now },
        $setOnInsert: { _id: new ObjectId(), groupId: group._id, author: owner._id, createdAt: now },
      },
      { upsert: true },
    );
    const prompt = await prompts.findOne({ groupId: group._id, author: owner._id }, { projection: { _id: 1 } });
    if (!prompt) throw new Error(`Unable to establish tutorial prompt content ${tutorial.command}`);
    await promptGroups.updateOne({ _id: group._id }, { $set: { productionId: prompt._id, updatedAt: now } });
    await aclEntries.updateOne(
      { principalType: 'public', resourceType: 'promptGroup', resourceId: group._id },
      {
        $set: { permBits: 1, grantedBy: owner._id, grantedAt: now, updatedAt: now },
        $setOnInsert: { _id: new ObjectId(), principalType: 'public', resourceType: 'promptGroup', resourceId: group._id, createdAt: now },
      },
      { upsert: true },
    );
  }
}

async function main() {
  const client = new MongoClient(uri);
  await client.connect();
  try {
    const db = client.db();
    const users = db.collection('users');
    const agents = db.collection('agents');
    const aclEntries = db.collection('aclentries');

    await users.updateOne(
      { email: serviceEmail },
      {
        $setOnInsert: {
          _id: new ObjectId(),
          email: serviceEmail,
          name: 'Scientific AI Platform',
          provider: 'local',
          emailVerified: true,
          role: 'USER',
          createdAt: now,
          updatedAt: now,
        },
      },
      { upsert: true },
    );
    const owner = await users.findOne({ email: serviceEmail }, { projection: { _id: 1 } });
    if (!owner) throw new Error('Unable to establish the Scientific AI Platform owner');

    const agentData = {
      id: agentId,
      name: 'Scientific AI Platform',
      description: 'GLM-5.3-Flash scientific assistant with Token Factory, Tavily, hosted model Apps, durable bucket workflows, and interactive result viewers.',
      instructions,
      provider: 'Nebius Token Factory',
      model: 'zai-org/GLM-5.3-Flash',
      model_parameters: { model: 'zai-org/GLM-5.3-Flash', max_tokens: 32768 },
      artifacts: 'default',
      tools,
      mcpServerNames: ['bionemo-models', 'tavily', 'instance-admin', 'protein-viewer', 'bionemo-artifacts'],
      skills_enabled: true,
      skills_scope: 'all',
      conversation_starters: [
        'Show me the live Scientific AI model catalog, grouped by use case, with the best visual demo for each group.',
        'Fold one protein with three available structure models, compare the results, and render the structures interactively. Plan first; wait for me before running compute.',
        'Build a molecular docking demo from a protein and ligand, including ranked poses, a comparison table, and an interactive 3D view. Plan first.',
        'Show the best visual workflows for microscopy, chest X-ray, single-cell UMAP, SAM2 video tracking, synthetic physical-AI data, and speech transcription.',
      ],
      category: 'scientific-ai',
      is_promoted: true,
      author: owner._id,
      authorName: 'Scientific AI Platform',
      updatedAt: now,
    };
    await agents.updateOne(
      { id: agentId },
      {
        $set: agentData,
        $setOnInsert: { _id: new ObjectId(), createdAt: now, versions: [] },
      },
      { upsert: true },
    );
    const agent = await agents.findOne({ id: agentId }, { projection: { _id: 1 } });
    if (!agent) throw new Error('Unable to establish the Scientific AI Platform agent');

    await aclEntries.updateOne(
      { principalType: 'public', resourceType: 'agent', resourceId: agent._id },
      {
        $set: { permBits: 1, grantedBy: owner._id, grantedAt: now, updatedAt: now },
        $setOnInsert: { _id: new ObjectId(), principalType: 'public', resourceType: 'agent', resourceId: agent._id, createdAt: now },
      },
      { upsert: true },
    );
    await seedTutorialPrompts(db, owner);
    process.stdout.write('Scientific AI Platform agent is ready.\n');
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  process.stderr.write(`Scientific AI Platform seed failed: ${error.message}\n`);
  process.exitCode = 1;
});
