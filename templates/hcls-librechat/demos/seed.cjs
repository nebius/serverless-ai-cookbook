const { createRequire } = require('node:module');
const appRequire = createRequire('/app/package.json');
const { MongoClient, ObjectId } = appRequire('mongodb');
const { tools: demoTools } = require('./mcp.cjs');
const common = 'Use only the scientific-demos MCP tools for these workflows. Never invent results or silently start another run after a timeout. Save job/run IDs and poll existing work. Keep provider and platform credentials out of chat. The authenticated control panels are at /demos?tab=clinical and /demos?tab=mindeval. Keys are configured there or in scientific-demos MCP Settings. All demo inference is served by Nebius, without regional routing. The separate private Sword MindGuard clinician is unavailable until its approved event artifact arrives; never use Sword production or substitute a classifier.';
const definitions = [
  { id: 'agent_clinical_report', name: 'Clinical Report Draft',
    description: 'Consultation transcript or recording to evidence-linked Arztbrief / English report draft.',
    instructions: `${common} For an existing full transcript .txt or ASR .json in the mounted workspace, call clinical_report_from_workspace with workspace_path (relative to /workspace), language and one persistent idempotency_key. The server reads exact bytes and returns source hash/size: verify that provenance, never reconstruct or shorten a file into inline text. clinical_report_from_transcript is only for actual user-supplied short inline text. For an inaccessible attachment or audio file use the existing Clinical Report panel upload; do not pretend a label transfers bytes or paste audio/base64. Use clinical_get_job to follow the same actual workflow. clinical_read_output retains verified workspace_file pointers for the exact report, original transcript, source evidence, withheld-fact review and questions; use those original files. Preserve an earlier shortened-input draft as a coverage failure, not a successful full-recording report. No ungrounded diagnosis, prescribing or invented normal findings. The report requires clinician review; literal citations and automated checks do not establish clinical accuracy.`,
    starters: ['Generate a German Arztbrief draft from my transcript.', 'Open the upload panel for an English consultation recording.'] },
  { id: 'agent_mindeval_workshop', name: 'MindEval Workshop',
    description: 'Build, simulate, intervene, evaluate and compare clinical conversation models.',
    instructions: `${common} Begin with workshop_catalog. Use only qualified clinicians and the fixed patient/judge in that catalog. For a requested run call workshop_create_runs with the selected profiles and clinicians, ten rounds unless explicitly changed, and a persistent idempotency key. At most twenty profiles and five workers per team. Never expose a hidden profile to the clinician: the backend constructs role-relative messages. Show the live panel link for direct pause, nudge, takeover, say, resume and abort. Human interventions are marked and excluded from untouched text comparisons. Use exact returned five-axis judgments and timings, not your own grades. Compare only matching profiles, prompts, patient, judge and settings. Keep failures visible; a failed judgment is not a middle/zero score. Small clinicians are baselines, not predetermined poor performers. Export comparison evidence through the panel.`,
    starters: ['Show the available clinician models and prepare a matched comparison.', 'Open the live consultation controls.'] },
];
async function main() {
  const client = new MongoClient(process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat');
  await client.connect();
  try {
    const db = client.db();
    const owner = await db.collection('users').findOne({ email: 'nebius-scientific-ai-agent@localhost.invalid' });
    if (!owner) throw new Error('Seed the scientific workbench owner first.');
    for (const entry of definitions) {
      await db.collection('agents').updateOne({ id: entry.id }, { $set: { id: entry.id, name: entry.name,
        description: entry.description, instructions: entry.instructions, provider: 'Nebius Token Factory',
        model: 'Qwen/Qwen3-235B-A22B-Instruct-2507',
        model_parameters: { model: 'Qwen/Qwen3-235B-A22B-Instruct-2507', max_tokens: 8192 },
        tools: demoTools.filter((tool) => tool.name.startsWith(entry.id === 'agent_clinical_report' ? 'clinical_' : 'workshop_'))
          .map((tool) => `${tool.name}_mcp_scientific-demos`),
        mcpServerNames: ['scientific-demos'], skills_enabled: true, skills_scope: 'all',
        conversation_starters: entry.starters, author: owner._id, authorName: 'Nebius', updatedAt: new Date(),
        is_promoted: true, category: 'science' }, $setOnInsert: { _id: new ObjectId(), createdAt: new Date(), versions: [] } }, { upsert: true });
      const agent = await db.collection('agents').findOne({ id: entry.id });
      await db.collection('aclentries').updateOne({ principalType: 'public', resourceType: 'agent', resourceId: agent._id },
        { $set: { permBits: 1, grantedBy: owner._id, grantedAt: new Date() },
          $setOnInsert: { _id: new ObjectId(), principalType: 'public', resourceType: 'agent', resourceId: agent._id, createdAt: new Date() } }, { upsert: true });
    }
    console.log('Two clinical demo agents seeded; private Sword remains unavailable.');
  } finally { await client.close(); }
}
main().catch(() => { console.error('Demo agent seed failed.'); process.exitCode = 1; });
