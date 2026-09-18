/* Typed tools for the same durable workflows as the authenticated demo panels. */
const readline = require('node:readline');
const service = require('./service.cjs');
const owner = process.env.LIBRECHAT_USER_ID;
const key = process.env.SCIENTIFIC_MODELS_API_KEY;
const schema = (properties, required = []) => ({ type: 'object', additionalProperties: false, properties, required });
const string = { type: 'string' };
const array = { type: 'array', items: string, minItems: 1, maxItems: 20 };
const definitions = [
  ['workbench_list_apps', 'Compact caller-authorized Apps across native and batch models. Filter by query when choosing a model; no parameter schemas or large catalog records are returned. If the user already chose a known App, directly read its get_model_schema instead.', schema({ query: string })],
  ['workbench_track_operation', 'Save a Scientific AI operation in the user’s Runs panel after any model submission. Call this immediately with the returned operation ID; it is idempotent and verifies caller access.', schema({ operation_id: string, model_id: string, label: string }, ['operation_id'])],
  ['workbench_list_operations', 'Discover this caller’s durable model operations automatically, most recent first. Includes scientific batches and inference from chat or API. Follow next_cursor for older runs. Reconnect to existing IDs instead of resubmitting work.', schema({ cursor: string, limit: { type: 'integer', minimum: 1, maximum: 200, default: 50 } })],
  ['workbench_get_operation', 'Wait for an existing operation to finish, up to wait_seconds (default 15, maximum 30), then return its actual latest state and observed transitions. This never submits work. Prefer this bounded wait over repeated immediate polls; nonterminal work remains accessible in Runs.', schema({ operation_id: string, wait_seconds: { type: 'integer', minimum: 0, maximum: 30, default: 15 } }, ['operation_id'])],
  ['workbench_get_operation_result', 'Retrieve completed output, verify bounded JSON artifact size/SHA-256, save full raw JSON under /workspace/.scientific-runs/OPERATION_ID/result.json when mounted, and return compact metrics plus workspace_file. Analyze that file with execute_command; never copy coordinate arrays through chat. Treat evidence_guidance as normative. Poll status first; queued/running work is not complete.', schema({ operation_id: string }, ['operation_id'])],
  ['workbench_cancel_operation', 'Cancel one accessible Scientific AI operation and keep its terminal cancelled state visible in Runs.', schema({ operation_id: string }, ['operation_id'])],
  ['workbench_workspace', 'Describe the current user or team storage and whether this LibreChat deployment has it mounted for direct file access.', schema({})],
  ['workshop_catalog', 'Discover contract-qualified clinicians, fixed patient/judge, profile IDs and this team’s limits. Sword private clinician is unavailable until its event artifact arrives.', schema({})],
  ['workshop_create_runs', 'Start durable MindEval consultations for profile × clinician choices. A round is a patient/clinician pair. Preserve the idempotency key across retries and save returned run IDs. Hidden profiles and scoring stay in the backend.', schema({ profile_ids: array, clinician_models: { ...array, maxItems: 8 }, patient_model: string,
    idempotency_key: string, max_turns: { type: 'integer', minimum: 2, maximum: 30, default: 10 } }, ['profile_ids', 'clinician_models', 'patient_model', 'idempotency_key'])],
  ['workshop_list_runs', 'List this authenticated team’s saved consultations; reconnect without resubmitting work.', schema({})],
  ['workshop_get_run', 'Read one durable consultation status and five-axis judgment. Save its complete transcript, config and raw judgment as a hash-verified workspace_file; use that actual JSON with execute_command for exports and analysis, never reconstruct middle turns from chat. Scores are research evaluations, not clinical validation.', schema({ run_id: string }, ['run_id'])],
  ['workshop_intervene', 'Explicitly pause, nudge, take over, say a human turn, resume model control or abort a consultation. Interventions are recorded and excluded from untouched benchmark comparisons.', schema({ run_id: string, action: { type: 'string', enum: ['pause', 'nudge', 'takeover', 'say', 'resume', 'abort'] }, role: { type: 'string', enum: ['patient', 'clinician'], default: 'clinician' }, text: string }, ['run_id', 'action'])],
  ['clinical_report_from_transcript', 'Generate an evidence-linked German Arztbrief or English report draft from an available transcript. Source transcript, uncertainties, withheld facts and follow-up questions are retained. Physician review required. For audio/large files, upload in /demos?tab=clinical; never send base64. Choose a fresh idempotency key once, then poll the returned job.', schema({ transcript: { type: 'string', minLength: 1, maxLength: 100000 }, language: { type: 'string', enum: ['en', 'de'] }, idempotency_key: string }, ['transcript', 'language', 'idempotency_key'])],
  ['clinical_report_from_workspace', 'Generate a reviewable clinical draft from an existing full transcript .txt or ASR .json file in the authenticated workspace. The server reads the exact bytes directly and records source size/SHA-256; do not paste, shorten or reconstruct the transcript through model arguments. Prefer this for completed ASR results. Supply a workspace-relative path (without /workspace/), language and one idempotency key; poll the returned existing job. Does not transcribe audio again. Not clinically validated.', schema({ workspace_path: string, language: { type: 'string', enum: ['en', 'de'] }, idempotency_key: string }, ['workspace_path', 'language', 'idempotency_key'])],
  ['clinical_get_job', 'Read the status of a saved report job and its authenticated download location. An incomplete draft is not a completed report.', schema({ job_id: string }, ['job_id'])],
  ['clinical_read_output', 'Read one saved draft, source transcript or review file after checking job status, and retain the exact bytes as a hash-verified workspace_file. Use that path for downloads and analysis instead of guessing private job folders or reconstructing text from chat. Keep uncertainty and clinician-review requirements visible.', schema({ job_id: string, filename: { type: 'string', enum: service.FILES } }, ['job_id', 'filename'])],
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
    case 'workbench_list_apps': return service.listApps(key, args.query);
    case 'workbench_track_operation': return service.track(owner, key, args.operation_id, {
      model_id: args.model_id, label: args.label, source: 'agent',
    });
    case 'workbench_list_operations': return service.runs(owner, key, args);
    case 'workbench_get_operation': return service.waitOperation(owner, key, args.operation_id, args.wait_seconds);
    case 'workbench_get_operation_result': return service.operationResult(key, args.operation_id);
    case 'workbench_cancel_operation': return service.platform(key, 'POST', `/v1/operations/${args.operation_id}:cancel`);
    case 'workbench_workspace': return service.workspaceInfo(key);
    case 'workshop_catalog': return request('GET', 'catalog');
    case 'workshop_list_runs': return { data: (await request('GET', 'runs')).data.map((run) => compact(run)) };
    case 'workshop_get_run': {
      const { run, workspace_file } = await service.workshopRun(key, args.run_id);
      return { ...compact(run), workspace_file, transcript: {
        messages: run.state.transcript?.length || 0,
        content_location: workspace_file.saved ? workspace_file.path : `/api/scientific-demos/workshop/runs/${run.id}`,
        note: 'Full transcript and raw judgment are retained outside chat context; read the saved JSON rather than reconstructing them from summaries.',
      } };
    }
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
    case 'clinical_report_from_workspace':
      return service.clinicalFromWorkspace(owner, key, args.workspace_path, args.language, args.idempotency_key);
    case 'clinical_get_job': return service.status(owner, args.job_id);
    case 'clinical_read_output': {
      const { bytes, workspace_file } = await service.clinicalOutput(owner, key, args.job_id, args.filename);
      if (bytes.length > 100000) return { job_id: args.job_id, file: args.filename, requires_download: true,
        workspace_file, url: `/demos?tab=clinical&job=${args.job_id}`,
        message: 'Full output exceeds the chat tool budget. Read the verified workspace file or download it in the report panel; no content was silently truncated.' };
      return { job_id: args.job_id, file: args.filename, workspace_file,
        content: bytes.toString('utf8'), clinical_validation: false };
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
