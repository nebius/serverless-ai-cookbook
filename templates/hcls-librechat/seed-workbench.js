const { MongoClient, ObjectId } = require('mongodb');
const { readFile, readdir } = require('node:fs/promises');
const path = require('node:path');

const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat';
const serviceEmail = 'gromacs-workbench@localhost.invalid';
const model = 'zai-org/GLM-5.2';
const tokenFactoryModelsUrl = 'https://api.tokenfactory.nebius.com/v1/models';

const AUDIO_TERMS = /audio|speech|asr|transcrib|whisper|voice|tts/i;
const IMAGING_TERMS = /image|vision|radiolog|medical.?imag|x.?ray|ct\b|dicom/i;

const gromacsTools = [
  'get_capabilities_mcp_gromacs',
  'submit_run_mcp_gromacs',
  'get_run_mcp_gromacs',
  'list_runs_mcp_gromacs',
  'cancel_run_mcp_gromacs',
  'list_run_artifacts_mcp_gromacs',
];

async function matchingSkillPaths(root, matcher) {
  const matches = [];
  const pending = [root];
  while (pending.length > 0 && matches.length < 40) {
    const directory = pending.pop();
    let entries;
    try {
      entries = await readdir(directory, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        pending.push(target);
      } else if (entry.isFile()) {
        const relative = path.relative(root, target);
        if (matcher.test(entry.name)) {
          matches.push(relative);
        } else if (entry.name === 'SKILL.md') {
          try {
            const contents = await readFile(target, 'utf8');
            if (matcher.test(contents)) matches.push(relative);
          } catch {
            // A malformed or unreadable optional skill cannot block startup.
          }
        }
      }
    }
  }
  return matches.sort();
}

function modelText(entry) {
  if (typeof entry === 'string') return entry;
  if (!entry || typeof entry !== 'object') return '';
  return [entry.id, entry.name, entry.description, entry.modalities, entry.capabilities]
    .flatMap((value) => (Array.isArray(value) ? value : [value]))
    .filter((value) => typeof value === 'string')
    .join(' ');
}

async function matchingModels(matcher) {
  if (!process.env.NEBIUS_API_KEY) return [];
  try {
    const response = await fetch(tokenFactoryModelsUrl, {
      headers: { Authorization: `Bearer ${process.env.NEBIUS_API_KEY}` },
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) return [];
    const body = await response.json();
    const entries = Array.isArray(body) ? body : Array.isArray(body?.data) ? body.data : [];
    return entries
      .filter((entry) => matcher.test(modelText(entry)))
      .map((entry) => (typeof entry === 'string' ? entry : entry.id || entry.name))
      .filter(Boolean)
      .sort()
      .slice(0, 20);
  } catch {
    return [];
  }
}

function catalogLine(label, values) {
  return values.length > 0 ? `${label}: ${values.join(', ')}.` : `${label}: none discovered at startup.`;
}

async function discoverCatalog() {
  const skillsRoot = process.env.DEPLOYMENT_SKILLS_DIR || '/app/skill';
  const [audioSkills, imagingSkills, audioModels, imagingModels] = await Promise.all([
    matchingSkillPaths(skillsRoot, AUDIO_TERMS),
    matchingSkillPaths(skillsRoot, IMAGING_TERMS),
    matchingModels(AUDIO_TERMS),
    matchingModels(IMAGING_TERMS),
  ]);
  return {
    audio: `${catalogLine('Installed matching skills', audioSkills)} ${catalogLine('Matching Token Factory models', audioModels)}`,
    imaging: `${catalogLine('Installed matching skills', imagingSkills)} ${catalogLine('Matching Token Factory models', imagingModels)}`,
  };
}

function agents(catalog) {
  return [
    {
      id: 'agent_gromacs_workbench',
      name: 'Nebius Scientific AI Agent',
      description: 'Scientific AI guide connected to bounded GROMACS REST/MCP tools on Nebius Serverless.',
      instructions: `You are Nebius Scientific AI Agent. Use the configured GROMACS MCP tools instead of guessing service state or computational results.

For capability, run, or artifact questions, inspect the live service first. Before submitting compute, summarize the proposed inputs and obtain explicit confirmation from the user. Use only the bounded typed MCP tools; never construct shell commands, accept arbitrary paths, or claim that a run succeeded before its live status says so. Preserve run IDs in follow-up calls. When a run finishes, list its artifacts and distinguish service availability, computational output, and scientific validity.

All molecular-dynamics output is research-only. Remind users to validate topology, force field, ensemble, equilibration, constraints, and sampling before scientific use.`,
      tools: gromacsTools,
      mcpServerNames: ['gromacs'],
      conversation_starters: [
        'List the available GROMACS capabilities and explain the safety limits.',
        'Prepare a small argon GPU smoke simulation, ask before submitting it, then monitor it and summarize the artifacts.',
        'Show recent GROMACS runs and explain which outputs are useful for validating an MD workflow.',
      ],
    },
    {
      id: 'agent_audio_transcription_tutorial',
      name: 'Audio Transcription · Placeholder',
      description: 'Guided starter for a future audio-to-text workflow. No transcription model is connected yet.',
      instructions: `You are the Audio Transcription tutorial. This is a placeholder, not an audio-to-text service: do not claim to receive, process, or transcribe audio. Explain the intended future workflow: supported audio input, consent and data handling, model selection, transcript with timestamps, confidence review, and human verification.

At startup, this workbench scanned its installed skills and the authenticated Token Factory model catalog for relevant names. Report this discovery result when asked: ${catalog.audio}

If a suitable tool or model is not configured, say so plainly and explain what would need to be connected.`,
      tools: [],
      mcpServerNames: [],
      conversation_starters: [
        'Show the planned audio-to-text workflow and the inputs a future transcription model will require.',
        'What audio skills and Token Factory models were discovered when this workbench started?',
      ],
    },
    {
      id: 'agent_medical_image_analysis_tutorial',
      name: 'Medical Image Analysis · Placeholder',
      description: 'Guided starter for a future CT/X-ray workflow. No image analysis or diagnostic model is connected.',
      instructions: `You are the Medical Image Analysis tutorial. This is a placeholder, not a medical-image service: do not claim to inspect CT, X-ray, DICOM, or other images, and do not provide a diagnosis, triage decision, or clinical recommendation. Explain the intended future research workflow: de-identified input, image quality checks, model selection, uncertainty display, evaluation against a held-out reference standard, and clinician review.

At startup, this workbench scanned its installed skills and the authenticated Token Factory model catalog for relevant names. Report this discovery result when asked: ${catalog.imaging}

If a suitable tool or model is not configured, say so plainly and explain what would need to be connected.`,
      tools: [],
      mcpServerNames: [],
      conversation_starters: [
        'Show the planned CT/X-ray analysis workflow and its validation requirements.',
        'What imaging skills and Token Factory models were discovered when this workbench started?',
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
        authorName: 'Nebius HCLS',
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
        _id: new ObjectId(),
        principalType: 'public', resourceType: 'agent', resourceId: agent._id, createdAt: now,
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
    const catalog = await discoverCatalog();
    for (const definition of agents(catalog)) {
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
