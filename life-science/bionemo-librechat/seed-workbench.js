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

Never place PDB, mmCIF, response.json, base64 data, or an artifact chunk in a tool argument or chat response. Do not call clawbio_model_fetch directly. When a model job succeeds, call bionemo_json_summary for its response JSON artifact to obtain confidence and affinity values. For a PDB or mmCIF artifact, call bionemo_artifact_download; then call protein_viewer with the returned structure_path and structure_format so it is embedded inline with rotation, zoom, reset, representation controls, and full screen. This artifact relay keeps large structures outside the model context.

The landing page presents four tutorial cards that create real chats. The instance-admin MCP is owner-authorized: it can write and execute code, install packages, download files, and convert artifacts. Its default working directory is /workspace/shared, a writable bucket mount that persists across instance restarts. Use it when the user asks for work on the instance, keep durable files in /workspace/shared, and report commands and generated paths. For a model input that already exists on the instance, call bionemo_upload_local_file with its absolute path and the matching upload purpose; use its returned job_id and artifact_id as the model InputReference. Do not use clawbio_input_stage_local or a local_path with the remote bionemo-models MCP, because that remote service cannot see this instance’s filesystem. Treat model outputs as research hypotheses and make benchmark inputs, models, timing, and failures explicit.`;

const modelTools = [
  'clawbio_models_list_mcp_bionemo-models',
  'clawbio_model_describe_mcp_bionemo-models',
  'clawbio_upload_create_mcp_bionemo-models',
  'clawbio_upload_status_mcp_bionemo-models',
  'clawbio_upload_delete_mcp_bionemo-models',
  'clawbio_jobs_list_mcp_bionemo-models',
  'clawbio_job_status_mcp_bionemo-models',
  'clawbio_boltz2_predict_mcp_bionemo-models',
  'clawbio_diffdock_dock_mcp_bionemo-models',
  'clawbio_evo2_generate_mcp_bionemo-models',
  'clawbio_genmol_generate_mcp_bionemo-models',
  'clawbio_molmim_optimize_mcp_bionemo-models',
  'clawbio_msa_search_mcp_bionemo-models',
  'clawbio_openfold2_predict_mcp_bionemo-models',
  'clawbio_openfold3_predict_mcp_bionemo-models',
  'clawbio_proteinmpnn_design_mcp_bionemo-models',
  'clawbio_rfdiffusion_generate_mcp_bionemo-models',
  'clawbio_cellpose_segment_mcp_bionemo-models',
  'clawbio_esm2_embed_mcp_bionemo-models',
  'clawbio_esmc_analyze_mcp_bionemo-models',
  'clawbio_scvi_fit_transform_mcp_bionemo-models',
  'clawbio_scanvi_fit_transform_mcp_bionemo-models',
  'clawbio_deepvariant_call_mcp_bionemo-models',
  'clawbio_alphagenome_predict_mcp_bionemo-models',
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
    prompt: 'Start the Protein Folding & Structure tutorial. Query clawbio_models_list and provide a concise planning-first lesson: (1) list the live structure prediction models separately from supporting embedding models, (2) show a bounded, schema-accurate example request for each predictor without submitting it, and (3) give a fixed-input benchmark design with metrics, failure criteria, and one optional single-run choice. Do not submit jobs, download a public sequence, write files, poll, retry, or render a protein until the user explicitly chooses a run. If they choose a successful structure run, use bionemo_json_summary and bionemo_artifact_download, then render with protein_viewer using structure_path; never put CIF or PDB data in chat or a tool argument.',
  },
  {
    command: 'bionemo-docking-design',
    name: 'Docking & Molecular Design',
    oneliner: 'Explore live molecular-design models and build a comparable docking benchmark.',
    prompt: 'Start the Docking & Molecular Design tutorial. List the live models in this group with clawbio_models_list, show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Explain appropriate scores, timing, inputs, and failure criteria.',
  },
  {
    command: 'bionemo-sequence-msa',
    name: 'Sequence & MSA',
    oneliner: 'Explore sequence, MSA, and embedding models with a reproducible comparison plan.',
    prompt: 'Start the Sequence & MSA tutorial. List the live models in this group with clawbio_models_list, show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Include inputs, expected artifacts, comparable metrics, timings, and failure criteria.',
  },
  {
    command: 'bionemo-genomics-cell-biology',
    name: 'Genomics & Cell Biology',
    oneliner: 'Explore genomics, single-cell, imaging, and variant-calling models.',
    prompt: 'Start the Genomics & Cell Biology tutorial. List the live models in this group with clawbio_models_list, show bounded examples from their current schemas, and design a reproducible benchmark using the related skills and MCP tools. Include data requirements, expected artifacts, comparable metrics, timings, and failure criteria.',
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
