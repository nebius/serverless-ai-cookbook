/* Typed tools for the same durable workflows as the authenticated demo panels. */
const readline = require('node:readline');
const service = require('./service.cjs');
const owner = process.env.LIBRECHAT_USER_ID;
const key = process.env.SCIENTIFIC_MODELS_API_KEY;
const schema = (properties, required = []) => ({ type: 'object', additionalProperties: false, properties, required });
const string = { type: 'string' };
const array = { type: 'array', items: string, minItems: 1, maxItems: 20 };
const definitions = [
  ['workbench_track_operation', 'Save a Scientific AI operation in the user’s Runs panel after any model submission. Call this immediately with the returned operation ID; it is idempotent and verifies caller access.', schema({ operation_id: string, model_id: string, label: string }, ['operation_id'])],
  ['workbench_list_operations', 'Discover this caller’s durable model operations automatically, most recent first. Includes scientific batches and inference from chat or API. Follow next_cursor for older runs. Reconnect to existing IDs instead of resubmitting work.', schema({ cursor: string, limit: { type: 'integer', minimum: 1, maximum: 200, default: 50 } })],
  ['workbench_get_operation', 'Refresh one saved Scientific AI operation and return its current state.', schema({ operation_id: string }, ['operation_id'])],
  ['workbench_get_operation_result', 'Retrieve a terminal result for a completed saved operation. Artifact-backed JSON is downloaded with caller credentials, size/SHA-256 verified and compacted without losing scalar metrics. Treat evidence_guidance as normative: do not infer capabilities from absent fields or mislabel the outer artifact size. Poll status first; do not treat queued or running work as complete.', schema({ operation_id: string }, ['operation_id'])],
  ['workbench_cancel_operation', 'Cancel one accessible Scientific AI operation and keep its terminal cancelled state visible in Runs.', schema({ operation_id: string }, ['operation_id'])],
  ['workbench_workspace', 'Describe the current user or team storage and whether this LibreChat deployment has it mounted for direct file access.', schema({})],
  ['workshop_catalog', 'Discover contract-qualified clinicians, fixed patient/judge, profile IDs and this team’s limits. Sword private clinician is unavailable until its event artifact arrives.', schema({})],
  ['workshop_create_runs', 'Start durable MindEval consultations for profile × clinician choices. A round is a patient/clinician pair. Preserve the idempotency key across retries and save returned run IDs. Hidden profiles and scoring stay in the backend.', schema({ profile_ids: array, clinician_models: { ...array, maxItems: 8 }, patient_model: string,
    idempotency_key: string, max_turns: { type: 'integer', minimum: 2, maximum: 30, default: 10 } }, ['profile_ids', 'clinician_models', 'patient_model', 'idempotency_key'])],
  ['workshop_list_runs', 'List this authenticated team’s saved consultations; reconnect without resubmitting work.', schema({})],
  ['workshop_get_run', 'Read one durable consultation transcript, current state, timings and five-axis judgment. Scores are research evaluations, not clinical validation.', schema({ run_id: string }, ['run_id'])],
  ['workshop_intervene', 'Explicitly pause, nudge, take over, say a human turn, resume model control or abort a consultation. Interventions are recorded and excluded from untouched benchmark comparisons.', schema({ run_id: string, action: { type: 'string', enum: ['pause', 'nudge', 'takeover', 'say', 'resume', 'abort'] }, role: { type: 'string', enum: ['patient', 'clinician'], default: 'clinician' }, text: string }, ['run_id', 'action'])],
  ['clinical_report_from_transcript', 'Generate an evidence-linked German Arztbrief or English report draft from an available transcript. Source transcript, uncertainties, withheld facts and follow-up questions are retained. Physician review required. For audio/large files, upload in /demos?tab=clinical; never send base64. Choose a fresh idempotency key once, then poll the returned job.', schema({ transcript: { type: 'string', minLength: 1, maxLength: 100000 }, language: { type: 'string', enum: ['en', 'de'] }, idempotency_key: string }, ['transcript', 'language', 'idempotency_key'])],
  ['clinical_get_job', 'Read the status of a saved report job and its authenticated download location. An incomplete draft is not a completed report.', schema({ job_id: string }, ['job_id'])],
  ['clinical_read_output', 'Read one saved draft, source transcript or review file after checking job status. Keep uncertainty and clinician-review requirements visible; do not invent absent output.', schema({ job_id: string, filename: { type: 'string', enum: service.FILES } }, ['job_id', 'filename'])],
  ['clinical_list_jobs', 'List this LibreChat user’s report jobs and resume their UI after reconnecting.', schema({})],
  ['clinical_resume_job', 'Explicitly resume the same interrupted or incomplete report job and its cached stages, using the original platform key. Does not create a new transcription operation.', schema({ job_id: string }, ['job_id'])],
];
const tools = definitions.map(([name, description, inputSchema]) => ({ name, description, inputSchema }));
function compact(run, transcript = false) {
  return { id: run.id, batch_id: run.batch_id, status: run.status, created_at: run.created_at,
    config: run.state.config, intervened: run.state.intervened, benchmark_eligible: run.state.benchmark_eligible,
    turns: run.state.transcript?.length || 0, error: run.state.error,
    judgment: run.state.judgment && { model: run.state.judgment.model,
      scores: run.state.judgment.judgment, overall_score: run.state.judgment.overall_score },
    ...(transcript ? { transcript: run.state.transcript } : {}), url: `/demos?tab=mindeval&run=${run.id}` };
}
async function dispatch(name, args) {
  if (!owner) throw service.failure('LibreChat user identity is missing.');
  const request = (method, url, body, id) => service.platform(key, method, `/v1/workshop/${url}`, body, id);
  switch (name) {
    case 'workbench_track_operation': return service.track(owner, key, args.operation_id, {
      model_id: args.model_id, label: args.label, source: 'agent',
    });
    case 'workbench_list_operations': return service.runs(owner, key, args);
    case 'workbench_get_operation': return service.track(owner, key, args.operation_id, { source: 'agent' });
    case 'workbench_get_operation_result': return service.operationResult(key, args.operation_id);
    case 'workbench_cancel_operation': return service.platform(key, 'POST', `/v1/operations/${args.operation_id}:cancel`);
    case 'workbench_workspace': return service.workspaceInfo(key);
    case 'workshop_catalog': return request('GET', 'catalog');
    case 'workshop_list_runs': return { data: (await request('GET', 'runs')).data.map((run) => compact(run)) };
    case 'workshop_get_run': return compact(await request('GET', `runs/${args.run_id}`), true);
    case 'workshop_create_runs': {
      const { idempotency_key, ...body } = args;
      const result = await request('POST', 'runs', { ...body, mode: 'canonical', max_turns: args.max_turns || 10 }, idempotency_key);
      return { data: result.data.map((run) => compact(run)) };
    }
    case 'workshop_intervene': {
      const { run_id, ...body } = args;
      return request('POST', `runs/${run_id}/interventions`, { ...body, source: 'typed' });
    }
    case 'clinical_report_from_transcript':
      if (typeof args.transcript !== 'string' || args.transcript.length > 100000) throw service.failure('Use the file upload panel for long transcripts.');
      return service.clinical(owner, key, { kind: 'transcript', language: args.language, idempotency_key: args.idempotency_key,
        filename: 'transcript.txt', bytes: Buffer.from(args.transcript) });
    case 'clinical_get_job': return service.status(owner, args.job_id);
    case 'clinical_read_output': {
      const bytes = await service.output(owner, args.job_id, args.filename);
      if (bytes.length > 100000) return { job_id: args.job_id, file: args.filename, requires_download: true,
        url: `/demos?tab=clinical&job=${args.job_id}`, message: 'Full output exceeds the chat tool budget. Download it in the report panel; no content was silently truncated.' };
      return { job_id: args.job_id, file: args.filename, content: bytes.toString('utf8'), clinical_validation: false };
    }
    case 'clinical_list_jobs': return { data: await service.list(owner) };
    case 'clinical_resume_job': return service.start(owner, key, args.job_id);
    default: throw service.failure('Unknown demo tool.');
  }
}
async function main() {
  for await (const line of readline.createInterface({ input: process.stdin })) {
    let request;
    try {
      request = JSON.parse(line);
      if (request.id === undefined) continue;
      let result;
      if (request.method === 'initialize') result = { protocolVersion: '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'scientific-demos', version: '1.0' } };
      else if (request.method === 'ping') result = {};
      else if (request.method === 'tools/list') result = { tools };
      else if (request.method === 'tools/call') {
        try {
          const value = await dispatch(request.params.name, request.params.arguments || {});
          result = { content: [{ type: 'text', text: JSON.stringify(value) }], isError: false };
        } catch (error) {
          result = { isError: true, content: [{ type: 'text', text: JSON.stringify(service.publicError(error)) }] };
        }
      } else throw new Error('Unknown method');
      process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: request.id, result }) + '\n');
    } catch { process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: request?.id || null, error: { code: -32602, message: 'Invalid demo request.' } }) + '\n'); }
  }
}
if (require.main === module) main();
module.exports = { tools, dispatch };
