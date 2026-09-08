const { MongoClient, ObjectId } = require('mongodb');

const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat';
const agentId = 'agent_gromacs_workbench';
const serviceEmail = 'gromacs-workbench@localhost.invalid';

const instructions = `You are the GROMACS GPU Workbench. Use the configured GROMACS MCP tools instead of guessing service state or computational results.

For capability, run, or artifact questions, inspect the live service first. Before submitting compute, summarize the proposed inputs and obtain explicit confirmation from the user. Use only the bounded typed MCP tools; never construct shell commands, accept arbitrary paths, or claim that a run succeeded before its live status says so. Preserve run IDs in follow-up calls. When a run finishes, list its artifacts and distinguish service availability, computational output, and scientific validity.

All molecular-dynamics output is research-only. Remind users to validate topology, force field, ensemble, equilibration, constraints, and sampling before scientific use.`;

const tools = [
  'get_capabilities_mcp_gromacs',
  'submit_run_mcp_gromacs',
  'get_run_mcp_gromacs',
  'list_runs_mcp_gromacs',
  'cancel_run_mcp_gromacs',
  'list_run_artifacts_mcp_gromacs',
];

async function main() {
  const client = new MongoClient(uri);
  await client.connect();
  try {
    const db = client.db();
    const now = new Date();
    const users = db.collection('users');
    const agents = db.collection('agents');
    const aclEntries = db.collection('aclentries');

    await users.updateOne(
      { email: serviceEmail },
      {
        $setOnInsert: {
          _id: new ObjectId(),
          email: serviceEmail,
          name: 'GROMACS Workbench',
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
    if (!owner) throw new Error('Unable to establish the GROMACS workbench owner');

    await agents.updateOne(
      { id: agentId },
      {
        $set: {
          id: agentId,
          name: 'GROMACS GPU Workbench',
          description: 'Token Factory research assistant connected to bounded GROMACS REST/MCP tools on Nebius Serverless.',
          instructions,
          provider: 'Nebius Token Factory',
          model: 'zai-org/GLM-5.2',
          model_parameters: { model: 'zai-org/GLM-5.2', max_tokens: 8192 },
          tools,
          mcpServerNames: ['gromacs'],
          conversation_starters: [
            'List the available GROMACS capabilities and explain the safety limits.',
            'Prepare a small argon GPU smoke simulation, ask before submitting it, then monitor it and summarize the artifacts.',
            'Show recent GROMACS runs and explain which outputs are useful for validating an MD workflow.',
          ],
          category: 'life-science',
          is_promoted: true,
          author: owner._id,
          authorName: 'Nebius HCLS',
          updatedAt: now,
        },
        $setOnInsert: { _id: new ObjectId(), createdAt: now, versions: [] },
      },
      { upsert: true },
    );
    const agent = await agents.findOne({ id: agentId }, { projection: { _id: 1 } });
    if (!agent) throw new Error('Unable to establish the GROMACS workbench agent');

    await aclEntries.updateOne(
      { principalType: 'public', resourceType: 'agent', resourceId: agent._id },
      {
        $set: { permBits: 1, grantedBy: owner._id, grantedAt: now, updatedAt: now },
        $setOnInsert: {
          _id: new ObjectId(),
          principalType: 'public',
          resourceType: 'agent',
          resourceId: agent._id,
          createdAt: now,
        },
      },
      { upsert: true },
    );
    process.stdout.write('GROMACS workbench agent is ready.\n');
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  process.stderr.write(`GROMACS workbench seed failed: ${error.message}\n`);
  process.exitCode = 1;
});
