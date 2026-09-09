/* Seed the operator-owned, publicly selectable BioNeMo workbench agent. */
const { MongoClient, ObjectId } = require('mongodb');

const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat';
// LibreChat reserves the `agent_` prefix for persisted agents. Without it the
// request loader treats this as an ephemeral agent and discards its model.
const agentId = 'agent_bionemo_workbench';
const serviceEmail = 'bionemo-workbench@localhost.invalid';
const now = new Date();

const instructions = `You are the BioNeMo Research Workbench. Use the configured tools rather than guessing.

For requests to list, compare, or select BioNeMo models, always query the bionemo-models MCP catalog first and group the result by protein folding and structure, docking and molecular design, sequence and MSA, genomics and cell biology, imaging, and embeddings. For a tutorial request, first show the models currently available in the requested group, then give a bounded example based on each model's live input schema, and finish with a reproducible benchmark plan for comparable models. Tutorials are planning-first: do not submit model jobs, download a public sequence, use Tavily, write files, poll jobs, or retry failed jobs unless the user explicitly selects a run. State that the example and benchmark are ready to run and ask the user which single workflow to execute. In the structure tutorial, distinguish prediction models (OpenFold2, OpenFold3, Boltz2) from supporting embedding models (ESM2 and ESMC); do not call embeddings structure predictors. For current literature or web evidence, call Tavily and cite the returned sources.

Never place PDB, mmCIF, response.json, base64 data, or an artifact chunk in a tool argument or chat response. Do not place artifact bytes in any tool argument. When a model job succeeds, read its result document via the scientific-model gateway (get_operation_result / get_scientific_result) for confidence and affinity values, download structure artifacts with download_scientific_artifact (or HTTP result/artifact endpoints), then render locally with the structure viewer so large files stay outside the model context.

The landing page presents four tutorial cards that create real chats. The instance-admin MCP is owner-authorized: it can write and execute code, install packages, download files, and convert artifacts. Its default working directory is /workspace/shared, a writable bucket mount that persists across instance restarts. Use it when the user asks for work on the instance, keep durable files in /workspace/shared, and report commands and generated paths. For a model input that already exists on the instance, upload the actual bytes to the scientific-model gateway with begin_scientific_artifact_upload / put_scientific_artifact_bytes / finalize_scientific_artifact_upload and use the returned immutable artifact reference in the input_manifest; the remote gateway cannot see this instance’s filesystem. Treat model outputs as research hypotheses and make benchmark inputs, models, timing, and failures explicit.`;

const modelTools = [
  'scientific_models__list_models',
  'scientific_models__list_scientific_models',
  'scientific_models__invoke_model',
  'scientific_models__get_operation',
  'scientific_models__get_operation_result',
  'scientific_models__acknowledge_operation',
  'scientific_models__submit_scientific_run',
  'scientific_models__get_scientific_status',
  'scientific_models__get_scientific_result',
  'scientific_models__list_scientific_events',
  'scientific_models__begin_scientific_artifact_upload',
  'scientific_models__put_scientific_artifact_bytes',
  'scientific_models__finalize_scientific_artifact_upload',
  'scientific_models__download_scientific_artifact',
  'scientific_models__boltz2_predict_native',
  'scientific_models__infer_openfold2_native',
  'scientific_models__infer_openfold3_native',
  'scientific_models__infer_diffdock_native',
  'scientific_models__genmol_generate_native',
  'scientific_models__molmim_run_native',
  'scientific_models__msa_search_native',
  'scientific_models__generate_dna_native',
  'scientific_models__infer_proteinmpnn_native',
  'scientific_models__infer_altumage_native',
  'scientific_models__infer_phenoage_native',
  'scientific_models__segment_ct_native',
  'scientific_models__analyze_image_openai_chat',
  'scientific_models__generate_image_native',
  'scientific_models__cosmos3_nano_generate_media_native',
  'scientific_models__qwen3_8b_chat_openai_chat',
  'scientific_models__submit_alphafold3',
  'scientific_models__submit_openfold3_openbind',
  'scientific_models__submit_protenix_v2',
  'scientific_models__submit_esmfold2',
  'scientific_models__submit_esmfold2_fast',
  'scientific_models__submit_proteina_complexa',
  'scientific_models__submit_bindcraft',
  'scientific_models__submit_boltzgen',
  'scientific_models__submit_mosaic',
  'scientific_models__submit_rfdiffusion',
];

const tools = [
  ...modelTools,
  'sys__all__sys_mcp_tavily',
  'sys__all__sys_mcp_instance-admin',
  'sys__all__sys_mcp_protein-viewer',
  'sys__all__sys_mcp_bionemo-artifacts',
];

const tutorialPrompts = [
  {
    command: 'bionemo-protein-folding',
    name: 'Protein Folding & Structure',
    oneliner: 'List live structure models, show bounded examples, and prepare an opt-in benchmark.',
    prompt: 'Start the Protein Folding & Structure tutorial. Query the gateway discovery tools (list_models and list_scientific_models) and provide a concise planning-first lesson: (1) list the live structure prediction models separately from supporting embedding models, (2) show a bounded, schema-accurate example request for each predictor without submitting it, and (3) give a fixed-input benchmark design with metrics, failure criteria, and one optional single-run choice. Do not submit jobs, download a public sequence, write files, poll, retry, or render a protein until the user explicitly chooses a run. If they choose a successful structure run, read the result document and download the structure artifact via the gateway, then render it with the local structure viewer; never put CIF or PDB data in chat or a tool argument.',
  },
  {
    command: 'bionemo-docking-design',
    name: 'Docking & Molecular Design',
    oneliner: 'Explore live molecular-design models and build a comparable docking benchmark.',
    prompt: 'Start the Docking & Molecular Design tutorial. List the live models in this group with the gateway discovery tools (list_models / list_scientific_models), show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Explain appropriate scores, timing, inputs, and failure criteria.',
  },
  {
    command: 'bionemo-sequence-msa',
    name: 'Sequence & MSA',
    oneliner: 'Explore sequence, MSA, and embedding models with a reproducible comparison plan.',
    prompt: 'Start the Sequence & MSA tutorial. List the live models in this group with the gateway discovery tools (list_models / list_scientific_models), show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Include inputs, expected artifacts, comparable metrics, timings, and failure criteria.',
  },
  {
    command: 'bionemo-genomics-cell-biology',
    name: 'Genomics & Cell Biology',
    oneliner: 'Explore genomics, single-cell, imaging, and variant-calling models.',
    prompt: 'Start the Genomics & Cell Biology tutorial. List the live models in this group with the gateway discovery tools (list_models / list_scientific_models), show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Include data requirements, expected artifacts, comparable metrics, timings, and failure criteria.',
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
          name: `BioNeMo Tutorial · ${tutorial.name}`,
          numberOfGenerations: 0,
          oneliner: tutorial.oneliner,
          category: 'Life Science',
          author: owner._id,
          authorName: 'BioNeMo',
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
          name: 'BioNeMo Workbench',
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
    if (!owner) throw new Error('Unable to establish the BioNeMo workbench owner');

    const agentData = {
      id: agentId,
      name: 'BioNeMo Research Workbench',
      description: 'GLM-5.3-Flash research assistant with the BioNeMo model catalog, Tavily, tutorials, instance tools, and an inline protein viewer.',
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
        'Protein Folding & Structure tutorial: list live models, show bounded examples, and prepare an opt-in benchmark.',
        'Docking & Molecular Design tutorial: list the live models in this group, show a bounded example, then design a comparable benchmark using the related skills and MCP tools.',
        'Sequence & MSA tutorial: list the live models in this group, show a bounded example, then design a comparable benchmark using the related skills and MCP tools.',
        'Genomics & Cell Biology tutorial: list the live models in this group, show a bounded example, then design a comparable benchmark using the related skills and MCP tools.',
      ],
      category: 'life-science',
      is_promoted: true,
      author: owner._id,
      authorName: 'BioNeMo',
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
    if (!agent) throw new Error('Unable to establish the BioNeMo workbench agent');

    await aclEntries.updateOne(
      { principalType: 'public', resourceType: 'agent', resourceId: agent._id },
      {
        $set: { permBits: 1, grantedBy: owner._id, grantedAt: now, updatedAt: now },
        $setOnInsert: { _id: new ObjectId(), principalType: 'public', resourceType: 'agent', resourceId: agent._id, createdAt: now },
      },
      { upsert: true },
    );
    await seedTutorialPrompts(db, owner);
    process.stdout.write('BioNeMo workbench agent is ready.\n');
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  process.stderr.write(`BioNeMo workbench seed failed: ${error.message}\n`);
  process.exitCode = 1;
});
