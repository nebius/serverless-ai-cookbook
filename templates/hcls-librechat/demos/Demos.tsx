import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input } from '@librechat/client';
import { request } from 'librechat-data-provider';
import { compareBatch, comparisonCsv } from './scientific-comparison';
import type { WorkshopRun as Run } from './scientific-comparison';
import { runDisplay } from './scientific-run-display';

type Job = { id: string; status: string; created_at: string; error?: string; files: string[] };
type Catalog = { catalog: { judge_model: string; data: { id: string; clinician_eligible: boolean; patient_eligible: boolean }[] };
  profiles: { data: { id: string; profile_id?: string; name?: string }[] }; limits: { profiles: number; workers_per_team: number } };
type AppRow = { id: string; native?: { display_name?: string; enabled?: boolean; capabilities?: string[]; protocols?: string[];
  execution_mode?: string; gpu_class?: string; gpu_count?: number; license?: string; qualification?: { state?: string } };
  scientific?: { display_name?: string; operations?: string[]; service_classes?: string[]; mcp_tool_name?: string;
    mcp_tool_description?: string; runtime?: { state?: string } } };
type RunRow = { id: string; model_id?: string; protocol?: string; status?: string; label?: string; source?: string;
  first_seen_at: string; accepted_at?: string; started_at?: string; completed_at?: string; refresh_error?: string;
  operation?: { protocol?: string; error_code?: string; error_detail?: string; result_available?: boolean; accepted_at?: string;
    activation_started_at?: string; ready_at?: string; started_at?: string; completed_at?: string;
    cold_start_seconds?: number; attempt?: number; max_attempts?: number } };
type RunPage = { data: RunRow[]; next_cursor?: string; history_available?: boolean; history_notice?: string };
type WorkspaceEntry = { name: string; path: string; kind: 'directory' | 'file'; size_bytes?: number; updated_at: string };
const BASE = '/api/scientific-demos';
const field = 'rounded-lg border border-border-medium bg-surface-primary p-2 text-text-primary';
const errorText = (error: Error) => {
  const detail = (error as Error & { response?: { data?: { error?: string; durable_admission?: boolean;
    retryable?: boolean; retry_after_seconds?: number; operation_id?: string } } }).response?.data;
  const message = detail?.error || error.message;
  if (detail?.operation_id) return `${message} Existing run: ${detail.operation_id}. Refresh its status before retrying.`;
  if (detail?.durable_admission === false && detail.retryable) {
    return `${message} No new run was accepted. Retry the same request${detail.retry_after_seconds ? ` after ${detail.retry_after_seconds}s` : ' when capacity is available'}.`;
  }
  return message;
};
function elapsed(start?: string, end?: string, active = false) {
  if (!start || (!end && !active)) return '—';
  const seconds = ((end ? Date.parse(end) : Date.now()) - Date.parse(start)) / 1000;
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  return seconds < 60 ? `${seconds.toFixed(1)}s` : `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
}
function download(name: string, data: BlobPart, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Chat/files use the documented /workspace mount while the authenticated API
// uses bucket-relative paths. Accept either, without resolving traversal or
// changing the server's existing ownership/path validation.
function workspaceSelection(params: URLSearchParams) {
  const relative = (value: string) => value.replace(/^\/workspace(?:\/|$)/, '').replace(/^\/+/, '');
  const directory = relative(params.get('path') || '');
  const suppliedFile = relative(params.get('file') || '');
  const file = suppliedFile && !suppliedFile.includes('/') && directory
    ? `${directory}/${suppliedFile}` : suppliedFile;
  return { directory, file };
}

const workbenchTabs = [['apps', 'Apps'], ['runs', 'Runs'], ['workspace', 'Workspace'],
  ['clinical', 'Clinical Report'], ['mindeval', 'MindEval']] as const;
function WorkbenchHeader({ tab, choose }: { tab: string; choose: (tab: string) => void }) {
  return <><header className="mb-6 flex flex-wrap items-center justify-between gap-4">
    <div><p className="text-xs text-text-secondary">NEBIUS SCIENTIFIC AI</p><h1 className="text-2xl font-semibold">Scientific AI Workbench</h1></div>
    <Link to="/c/new" className="underline">Back to chat</Link>
  </header><nav aria-label="Workbench selection" className="mb-5 flex flex-wrap gap-2">
    {workbenchTabs.map(([id, label]) => <Button key={id} variant={tab === id ? 'default' : 'outline'} onClick={() => choose(id)}>{label}</Button>)}
  </nav></>;
}

function CoreWorkbench({ tab, choose }: { tab: string; choose: (tab: string) => void }) {
  const [params, setParams] = useSearchParams();
  const cache = useQueryClient();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [operationId, setOperationId] = useState('');
  const [selectedRun, setSelectedRun] = useState('');
  const [runResult, setRunResult] = useState('');
  const [runPages, setRunPages] = useState<string[]>(['']);
  const { directory: workspacePath, file: selectedWorkspaceFile } = workspaceSelection(params);
  const setWorkspacePath = (next: string) => setParams({ tab: 'workspace', ...(next ? { path: next } : {}) });
  const [workspaceFile, setWorkspaceFile] = useState<File | null>(null);
  const [workspaceName, setWorkspaceName] = useState('');
  const [copied, setCopied] = useState('');
  const settings = useQuery(['scientific-demos', 'settings'], () => request.get<{ configured: boolean }>(`${BASE}/settings`));
  const enabled = settings.data?.configured === true;
  const apps = useQuery(['scientific-demos', 'apps'], () => request.get<{ data: AppRow[] }>(`${BASE}/apps`), { enabled: enabled && tab === 'apps', retry: false });
  const runCursor = runPages[runPages.length - 1];
  const runs = useQuery(['scientific-demos', 'runs', runCursor], () => request.get<RunPage>(`${BASE}/runs${runCursor ? `?cursor=${encodeURIComponent(runCursor)}` : ''}`), { enabled: enabled && tab === 'runs', retry: false, refetchInterval: tab === 'runs' ? 5000 : false });
  const workspace = useQuery(['scientific-demos', 'workspace', workspacePath], () => request.get<{ info: Record<string, unknown>; prefix: string; data: WorkspaceEntry[] }>(`${BASE}/workspace?path=${encodeURIComponent(workspacePath)}`), { enabled: enabled && tab === 'workspace', retry: false });
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('');
    try { await work(); await cache.invalidateQueries(['scientific-demos']); }
    catch (problem) { setError(errorText(problem as Error)); }
    finally { setBusy(false); }
  }
  const selectedEntry = workspace.data?.data.find((entry) => entry.kind === 'file' && entry.path === selectedWorkspaceFile);
  const downloadWorkspaceFile = (entry: WorkspaceEntry) => act(async () => {
    const response = await request.getResponse<Blob>(`${BASE}/workspace/file?path=${encodeURIComponent(entry.path)}`, { responseType: 'blob' });
    download(entry.name, response.data, response.headers['content-type'] || 'application/octet-stream');
  });
  const sessionError = [settings.error, apps.error, runs.error, workspace.error].find(Boolean);
  return <main className="mx-auto h-full w-full max-w-6xl overflow-y-auto p-4 text-text-primary sm:p-8">
    <WorkbenchHeader tab={tab} choose={choose} />
    <details open={!enabled} className="mb-5 rounded-xl border border-border-medium p-4">
      <summary>Platform connection · {enabled ? 'key configured for your account' : 'your API key is required'}</summary>
      <p className="my-2 text-sm text-text-secondary">Use your ordinary Scientific AI key. It controls which Apps and runs this account can access.</p>
      <form onSubmit={(event) => { event.preventDefault(); void act(async () => {
        await request.put(`${BASE}/settings`, { api_key: apiKey }); setApiKey('');
        await request.post('/api/mcp/scientific-demos/reinitialize').catch(() => undefined);
      }); }} className="flex gap-2"><Input aria-label="Scientific AI API key" type="password" autoComplete="off" value={apiKey} onChange={(event) => setApiKey(event.target.value)} /><Button type="submit" disabled={busy || !apiKey}>Save key</Button></form>
    </details>
    {Boolean(error || sessionError) && <p role="alert" className="mb-4 rounded border border-border-medium p-3">{error || errorText(sessionError as Error)}</p>}
    {tab === 'apps' && <section>
      <h2 className="text-xl font-semibold">Apps you can use</h2><p className="my-2 text-sm text-text-secondary">Live, caller-scoped discovery. Scaled-to-zero Apps remain listed when your key may start them.</p>
      <div className="grid gap-3 md:grid-cols-2">{(apps.data?.data || []).map((app) => {
        const title = app.scientific?.display_name || app.native?.display_name || app.id;
        const operations = app.scientific?.operations || app.native?.capabilities || [];
        const ready = app.native?.enabled !== false;
        return <article key={app.id} className="rounded-xl border border-border-medium p-4">
          <div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">{title}</h3><code className="text-xs text-text-secondary">{app.id}</code></div><span className="rounded-full border border-border-light px-2 py-1 text-xs">{ready ? 'Available' : 'Disabled'}</span></div>
          <p className="mt-3 text-sm">{app.scientific?.mcp_tool_description || 'Inspect the live schema before submitting data.'}</p>
          <p className="mt-2 text-xs text-text-secondary">{operations.length ? operations.join(' · ') : 'Native inference'}{app.native?.gpu_class ? ` · ${app.native.gpu_count || 1}× ${app.native.gpu_class}` : ''}</p>
          <div className="mt-3 flex gap-2"><Button size="sm" variant="outline" onClick={async () => {
            const prompt = `I want to use the Scientific AI App ${app.id}. Discover its live schema, explain the required input and evaluation limits, and do not submit compute until I confirm.`;
            await navigator.clipboard.writeText(prompt); setCopied(app.id);
          }}>{copied === app.id ? 'Prompt copied' : 'Copy chat prompt'}</Button></div>
        </article>;
      })}</div>
      {enabled && !apps.isLoading && !(apps.data?.data.length) && <p role="status">This key currently has no authorized Apps.</p>}
    </section>}
    {tab === 'runs' && <section>
      <h2 className="text-xl font-semibold">Runs</h2><p className="my-2 text-sm text-text-secondary">Your model operations and input uploads from chat and API appear automatically. Reconnect to follow their actual status without submitting duplicate work.</p>
      {runs.data?.history_notice && <p role="status" className="my-3 rounded border border-border-medium p-3 text-sm">{runs.data.history_notice}</p>}
      <form className="mb-4 flex gap-2" onSubmit={(event) => { event.preventDefault(); void act(async () => {
        const value = await request.post<RunRow>(`${BASE}/runs`, { operation_id: operationId }); setSelectedRun(value.id); setOperationId('');
      }); }}><Input aria-label="Operation ID" placeholder="operation UUID" value={operationId} onChange={(event) => setOperationId(event.target.value)} /><Button type="submit" disabled={!enabled || !operationId || busy}>Add run</Button></form>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>App / run</th><th>Status</th><th>Elapsed</th><th>Submitted</th><th>Actions</th></tr></thead><tbody>{(runs.data?.data || []).map((run) => {
        const display = runDisplay(run);
        return <tr key={run.id} className="border-t border-border-light"><td className="max-w-sm py-3 pr-3"><strong>{run.model_id || 'Unknown App'}</strong>{display.upload && <p className="text-xs">Input upload · no GPU inference</p>}{run.label && <p className="text-xs">{run.label}</p>}<code className="text-xs">{run.id}</code>{run.refresh_error && <p className="text-xs">Refresh: {run.refresh_error}</p>}</td>
          <td className="pr-3">{display.status}{display.description && <p className="text-xs text-text-secondary">{display.description}</p>}{run.operation?.error_code && <p className="max-w-xs text-xs">{run.operation.error_code}: {run.operation.error_detail || 'See details'}</p>}{(run.operation?.attempt || 0) > 1 && <p className="text-xs">Attempt {run.operation?.attempt} / {run.operation?.max_attempts || '—'}</p>}</td>
          <td className="pr-3">{elapsed(run.accepted_at, run.completed_at, !display.terminal)}{display.showComputeTiming && <><p className="text-xs text-text-secondary">Wait {elapsed(run.accepted_at, run.started_at, !display.terminal && !run.started_at)}</p>{run.operation?.cold_start_seconds !== undefined && run.operation.cold_start_seconds !== null && <p className="text-xs text-text-secondary">Activation {run.operation.cold_start_seconds.toFixed(1)}s</p>}</>}</td>
          <td className="pr-3">{run.accepted_at ? new Date(run.accepted_at).toLocaleString() : 'Unknown'}</td><td><div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void act(async () => { const value = await request.get(`${BASE}/runs/${run.id}`); setSelectedRun(run.id); setRunResult(JSON.stringify(value, null, 2)); })}>Details</Button>
            {display.showResult && <Button size="sm" variant="outline" disabled={busy} onClick={() => void act(async () => { const value = await request.get(`${BASE}/runs/${run.id}/result`); setSelectedRun(run.id); setRunResult(JSON.stringify(value, null, 2)); })}>Result</Button>}
            {!display.terminal && <Button size="sm" variant="outline" disabled={busy} onClick={() => void act(async () => { await request.post(`${BASE}/runs/${run.id}/cancel`); })}>{display.upload ? 'Cancel upload' : 'Cancel'}</Button>}
          </div></td></tr>;
      })}</tbody></table></div>
      {enabled && !runs.isLoading && !runs.error && !(runs.data?.data.length) && <p role="status" className="my-4">No runs on this page yet.</p>}
      <div className="mt-4 flex gap-2"><Button variant="outline" disabled={runPages.length < 2} onClick={() => setRunPages((pages) => pages.slice(0, -1))}>Newer runs</Button><Button variant="outline" disabled={!runs.data?.next_cursor} onClick={() => { if (runs.data?.next_cursor) setRunPages((pages) => [...pages, runs.data!.next_cursor!]); }}>Older runs</Button></div>
      {selectedRun && runResult && <section className="mt-4 rounded-xl border border-border-medium p-4"><h3 className="font-semibold">Result · {selectedRun}</h3><pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-xs">{runResult}</pre></section>}
    </section>}
    {tab === 'workspace' && <section>
      <h2 className="text-xl font-semibold">Workspace</h2><p className="my-2 text-sm text-text-secondary">Files in the bucket mounted for this deployment. Model inputs should be uploaded as immutable platform artifacts before a run.</p>
      {workspace.data && <p className="mb-3 text-xs">Bucket: <strong>{String(workspace.data.info.team_bucket_name || workspace.data.info.bucket_name || 'configured by platform')}</strong> · {String(workspace.data.info.mode || 'mounted')} storage</p>}
      {selectedWorkspaceFile && <div className="mb-4 rounded-xl border border-border-medium p-4">
        <p className="mb-2 text-sm">Selected file: <code>{selectedWorkspaceFile}</code></p>
        {selectedEntry ? <Button disabled={busy} onClick={() => void downloadWorkspaceFile(selectedEntry)}>Download selected file</Button>
          : !workspace.isLoading && workspace.data && <p role="status">This file was not found in the selected folder. No download was started.</p>}
      </div>}
      <form className="mb-4 grid gap-2 rounded-xl border border-border-medium p-4 sm:grid-cols-[1fr_1fr_auto]" onSubmit={(event) => { event.preventDefault(); void act(async () => {
        if (!workspaceFile) return; const data = new FormData(); data.append('file', workspaceFile); data.append('path', workspaceName || workspaceFile.name); await request.postMultiPart(`${BASE}/workspace`, data); setWorkspaceFile(null); setWorkspaceName('');
      }); }}><input type="file" onChange={(event) => { const file = event.target.files?.[0] || null; setWorkspaceFile(file); if (file) setWorkspaceName([workspacePath, file.name].filter(Boolean).join('/')); }} /><Input aria-label="Workspace object path" value={workspaceName} onChange={(event) => setWorkspaceName(event.target.value)} /><Button type="submit" disabled={!workspaceFile || busy}>Upload</Button></form>
      <div className="mb-3 flex items-center gap-2"><Button size="sm" variant="outline" disabled={!workspacePath} onClick={() => setWorkspacePath(workspacePath.split('/').slice(0, -1).join('/'))}>Up</Button><code className="text-xs">/{workspacePath}</code></div>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Name</th><th>Kind</th><th>Size</th><th>Updated</th></tr></thead><tbody>{(workspace.data?.data || []).map((entry) => <tr key={entry.path} className="border-t border-border-light"><td className="py-3">{entry.kind === 'directory' ? <button className="underline" onClick={() => setWorkspacePath(entry.path)}>{entry.name}/</button> : <button className="underline" onClick={() => void downloadWorkspaceFile(entry)}>{entry.name}</button>}</td><td>{entry.kind}</td><td>{entry.size_bytes?.toLocaleString() || '—'}</td><td>{new Date(entry.updated_at).toLocaleString()}</td></tr>)}</tbody></table></div>
    </section>}
  </main>;
}

export default function Demos() {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') || 'apps';
  if (['apps', 'runs', 'workspace'].includes(tab)) return <CoreWorkbench tab={tab} choose={(next) => setParams({ tab: next })} />;
  return <ClinicalAndMindEval />;
}

function ClinicalAndMindEval() {
  const [params, setParams] = useSearchParams();
  const clinical = params.get('tab') !== 'mindeval';
  const cache = useQueryClient();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [input, setInput] = useState<File | null>(null);
  const [language, setLanguage] = useState('en');
  const [kind, setKind] = useState('transcript');
  const [submission, setSubmission] = useState(() => crypto.randomUUID());
  const [clinicians, setClinicians] = useState<string[]>([]);
  const [profiles, setProfiles] = useState<string[]>([]);
  const [runId, setRunId] = useState(params.get('run') || '');
  const [batchId, setBatchId] = useState('');
  const [replay, setReplay] = useState(false);
  const [role, setRole] = useState('clinician');
  const [intervention, setIntervention] = useState('');
  const [preview, setPreview] = useState('');
  const settings = useQuery(['scientific-demos', 'settings'], () => request.get<{ configured: boolean; report_model: string }>(`${BASE}/settings`));
  const enabled = settings.data?.configured === true;
  const jobs = useQuery(['scientific-demos', 'clinical'], () => request.get<{ data: Job[] }>(`${BASE}/clinical`), { enabled, refetchInterval: clinical ? 3000 : false });
  const catalog = useQuery(['scientific-demos', 'catalog'], () => request.get<Catalog>(`${BASE}/workshop/catalog`), { enabled: enabled && !clinical, retry: false });
  const runs = useQuery(['scientific-demos', 'runs'], () => request.get<{ data: Run[] }>(`${BASE}/workshop/runs`), { enabled: enabled && !clinical && !replay, refetchInterval: replay ? false : 2000, retry: false });
  const example = useQuery(['scientific-demos', 'example'], () => request.get<{ data: Run[] }>(`${BASE}/workshop/example`), { enabled: replay });
  const visibleRuns = (replay ? example.data?.data : runs.data?.data) || [];
  const selected = visibleRuns.find((run) => run.id === runId);
  const batches = [...new Set(visibleRuns.map((run) => run.batch_id))];
  const comparison = compareBatch(visibleRuns, batchId || batches[0] || '');
  useEffect(() => {
    if (!profiles.length && catalog.data?.profiles.data.length) {
      const first = catalog.data.profiles.data[0];
      setProfiles([first.id || first.profile_id || '']);
    }
  }, [catalog.data]);
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('');
    try { await work(); await cache.invalidateQueries(['scientific-demos']); }
    catch (problem) { setError(errorText(problem as Error)); }
    finally { setBusy(false); }
  }
  const toggle = (list: string[], value: string) => list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
  const sessionError = [settings.error, catalog.error, runs.error, jobs.error].find(Boolean);
  return <main className="mx-auto h-full w-full max-w-6xl overflow-y-auto p-4 text-text-primary sm:p-8">
    <WorkbenchHeader tab={clinical ? 'clinical' : 'mindeval'} choose={(tab) => setParams({ tab })} />
    <details open={!enabled} className="mb-5 rounded-xl border border-border-medium p-4">
      <summary>Platform connection · {enabled ? 'key configured for your account' : 'your API key is required'}</summary>
      <p className="my-2 text-sm text-text-secondary">Use your ordinary Scientific AI key, not a Token Factory or admin key. This connection is shared with the scientific-demos MCP tools. Provider credentials stay on the server.</p>
      <form onSubmit={(event) => { event.preventDefault(); void act(async () => {
        await request.put(`${BASE}/settings`, { api_key: apiKey }); setApiKey('');
        try { await request.post('/api/mcp/scientific-demos/reinitialize'); }
        catch { throw new Error('Key saved for the panels. Reconnect scientific-demos in MCP Settings before using the chat agent.'); }
      }); }} className="flex gap-2">
        <Input aria-label="Scientific AI API key" type="password" autoComplete="off" value={apiKey} onChange={(event) => setApiKey(event.target.value)} />
        <Button type="submit" disabled={busy || !apiKey}>Save key</Button>
      </form>
    </details>
    {Boolean(error || sessionError) && <p role="alert" className="mb-4 rounded border border-border-medium p-3">{error || errorText(sessionError as Error)}</p>}
    {clinical ? <>
      <h2 className="text-xl font-semibold">Transcript or recording → report draft</h2>
      <p className="my-3 text-sm text-text-secondary">English or German · Nemotron speech when needed → Qwen-235B. A clinician must review the transcript, citations, withheld facts and questions. This is not a clinically validated report generator.</p>
      <form className="grid gap-3 rounded-xl border border-border-medium p-4" onSubmit={(event) => { event.preventDefault(); void act(async () => {
        if (!input) return;
        const data = new FormData(); data.append('file', input); data.append('language', language); data.append('kind', kind); data.append('idempotency_key', submission);
        const job = await request.postMultiPart(`${BASE}/clinical`, data) as Job;
        setParams({ tab: 'clinical', job: job.id });
      }); }}>
        <label>Input type <select className={field} value={kind} onChange={(event) => { setKind(event.target.value); setSubmission(crypto.randomUUID()); }}><option value="transcript">Transcript</option><option value="audio">Recording</option></select></label>
        <label>Language <select className={field} value={language} onChange={(event) => { setLanguage(event.target.value); setSubmission(crypto.randomUUID()); }}><option value="en">English</option><option value="de">German</option></select></label>
        <label>Consultation file <input className="block py-2" type="file" accept={kind === 'audio' ? '.wav,.flac,.mp3,.ogg,.m4a,.mp4,.webm' : '.txt,.json'} onChange={(event) => { setInput(event.target.files?.[0] || null); setSubmission(crypto.randomUUID()); }} /></label>
        <Button type="submit" disabled={!enabled || !input || busy}>Generate draft</Button>
        <p className="text-xs text-text-secondary">Up to 512 MiB. Closing this page does not cancel the job. If the connection fails, retry unchanged input; the same request ID prevents duplicate admission.</p>
      </form>
      <h3 className="my-4 font-semibold">Your report jobs</h3>
      {(jobs.data?.data || []).map((job) => <article key={job.id} className="mb-3 rounded-xl border border-border-medium p-4">
        <p><strong>{job.status === 'completed' ? 'Draft ready for review' : job.status}</strong> · <code>{job.id}</code></p>
        {job.error && <p role="status">{job.error}</p>}
        {['incomplete', 'interrupted', 'prepared'].includes(job.status) && <Button variant="outline" disabled={busy} onClick={() => void act(async () => { await request.post(`${BASE}/clinical/${job.id}/resume`); })}>Resume same job</Button>}
        <div className="mt-3 flex flex-wrap gap-2">{job.files.map((name) => <Button key={name} variant="outline" size="sm" onClick={() => void act(async () => {
          const response = await request.getResponse<string>(`${BASE}/clinical/${job.id}/files/${encodeURIComponent(name)}`, { responseType: 'text' });
          download(name, response.data, 'text/plain');
          if (name.endsWith('.md')) setPreview(response.data);
        })}>{name}</Button>)}</div>
      </article>)}
      {preview && <pre className="whitespace-pre-wrap rounded-xl border border-border-medium p-4 text-sm">{preview}</pre>}
    </> : <>
      <h2 className="text-xl font-semibold">Build · Simulate · Evaluate</h2>
      <p className="my-3 text-sm text-text-secondary">Sword AI Summit · Porto · 3 October 2026. Fixed patient and judge; change only the clinician for comparable text runs. Private MindGuard v2 is awaiting its event artifact and is not selectable.</p>
      <Button className="mb-3" variant="outline" onClick={() => { setReplay(!replay); setBatchId(''); setRunId(''); }}>{replay ? 'Return to live runs' : 'Open recorded example (no inference)'}</Button>
      {replay && <p role="status" className="my-2 rounded border border-border-medium p-3">RECORDED EXAMPLE · 16 September 2026 · Six clinicians, one synthetic profile. This is not live traffic or a full benchmark; use it to practice reading judgments if live inference is unavailable.</p>}
      {catalog.data && !replay && <>
        <p className="mb-3 text-sm">Judge: <strong>{catalog.data.catalog.judge_model}</strong> · {catalog.data.limits.workers_per_team} workers per team · global Token Factory</p>
        <div className="grid gap-4 md:grid-cols-2">
          <fieldset className="rounded-xl border border-border-medium p-4"><legend>Clinicians to compare</legend>
            {catalog.data.catalog.data.filter((item) => item.clinician_eligible).map((item) => <label key={item.id} className="mb-2 flex items-start gap-2 text-sm"><input type="checkbox" checked={clinicians.includes(item.id)} onChange={() => { setClinicians(toggle(clinicians, item.id)); setSubmission(crypto.randomUUID()); }} /><span className="break-all">{item.id}</span></label>)}
          </fieldset>
          <fieldset className="max-h-72 overflow-y-auto rounded-xl border border-border-medium p-4"><legend>Patient profiles · {profiles.length}/20</legend>
            {catalog.data.profiles.data.map((item) => { const id = item.id || item.profile_id || ''; return <label key={id} className="mb-2 flex gap-2 text-sm"><input type="checkbox" checked={profiles.includes(id)} disabled={!profiles.includes(id) && profiles.length >= 20} onChange={() => { setProfiles(toggle(profiles, id)); setSubmission(crypto.randomUUID()); }} />{id} {item.name || ''}</label>; })}
          </fieldset>
        </div>
        <Button className="my-4" disabled={busy || !profiles.length || !clinicians.length} onClick={() => void act(async () => {
          const patient = catalog.data.catalog.data.find((item) => item.patient_eligible)?.id;
          const response = await axios.post<{ data: Run[] }>(`${BASE}/workshop/runs`, { profile_ids: profiles, clinician_models: clinicians, patient_model: patient, mode: 'canonical', max_turns: 10 }, { headers: { 'Idempotency-Key': submission } });
          setRunId(response.data.data[0]?.id || '');
          setBatchId(response.data.data[0]?.batch_id || '');
          setParams({ tab: 'mindeval', run: response.data.data[0]?.id || '' });
        })}>Run 10-round comparison ({profiles.length * clinicians.length} consultations)</Button>
      </>}
      <p className="mb-2 text-xs text-text-secondary">A comparison is only valid for identical profiles, patient, judge and settings. Failed, unfinished and human-intervened runs stay visible; they are not zero scores.</p>
      {batches.length > 0 && <section className="my-4 rounded-xl border border-border-medium p-4">
        <label>Comparison batch <select className={`${field} max-w-full`} value={batchId || batches[0]} onChange={(event) => setBatchId(event.target.value)}>{batches.map((id) => <option key={id} value={id}>{id}</option>)}</select></label>
        <p className="my-2 text-sm">{comparison.matched_profiles.length}/{comparison.profiles.length} profiles completed by every selected clinician without human intervention. Paired means below use only that shared set.</p>
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Clinician</th><th>Completed / planned</th><th>Failed / aborted</th><th>Intervened</th><th>Paired mean / 6</th></tr></thead><tbody>
          {comparison.summaries.map((row) => <tr key={row.model}><td className="max-w-sm break-all py-2">{row.model}</td><td>{row.completed} / {row.planned}</td><td>{row.failed}</td><td>{row.intervened}</td><td>{row.mean?.toFixed(2) || '—'}</td></tr>)}
        </tbody></table></div>
        {comparison.summaries.some((row) => row.missing > 0) && <p role="status">Some batch rows are outside the latest 200 runs. This is an incomplete view; do not interpret it as a full benchmark.</p>}
        <div className="mt-3 flex gap-2"><Button variant="outline" onClick={() => download(`${replay ? 'recorded-' : ''}mindeval-${comparison.batch_id}.json`, JSON.stringify({ replay, ...comparison }, null, 2))}>Export batch evidence</Button><Button variant="outline" onClick={() => download(`${replay ? 'recorded-' : ''}mindeval-${comparison.batch_id}.csv`, comparisonCsv(comparison), 'text/csv')}>Export comparison CSV</Button></div>
      </section>}
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Profile / clinician</th><th>Status</th><th>Mean score / 6</th><th>Comparison</th><th>Evidence</th></tr></thead><tbody>
        {visibleRuns.map((run) => <tr key={run.id} className="border-t border-border-light"><td className="max-w-sm py-2"><button className="break-all text-left underline" onClick={() => { setRunId(run.id); setParams({ tab: 'mindeval', run: run.id }); }}>{run.state.config.profile_id} · {run.state.config.clinician_model}</button></td><td>{run.status}</td><td>{run.state.judgment?.overall_score?.toFixed(2) || '—'}</td><td>{run.state.intervened ? 'Human intervention' : run.state.benchmark_eligible ? 'Untouched text run' : 'Not complete'}</td><td><Button size="sm" variant="outline" onClick={() => void act(async () => { const report = replay ? { replay: true, run } : await request.get(`${BASE}/workshop/runs/${run.id}/report`); download(`${run.id}.json`, JSON.stringify(report, null, 2)); })}>JSON</Button></td></tr>)}
      </tbody></table></div>
      {selected && <section className="mt-4 rounded-xl border border-border-medium p-4">
        <h3 className="font-semibold">Consultation · {selected.id}</h3>
        <p role="status">{selected.status}{selected.state.error?.message ? ` · ${selected.state.error.message}` : ''}</p>
        <div className="my-3 flex flex-wrap items-center gap-2">
          <label>Role <select className={field} value={role} onChange={(event) => setRole(event.target.value)}><option value="clinician">Clinician</option><option value="patient">Patient</option></select></label>
          {['pause', 'takeover', 'resume', 'abort'].map((action) => <Button key={action} variant="outline" disabled={busy || ['completed', 'failed', 'aborted'].includes(selected.status)} onClick={() => void act(async () => { await request.post(`${BASE}/workshop/runs/${selected.id}/interventions`, { action, role }); })}>{action}</Button>)}
        </div>
        <label className="block">Human turn or nudge<textarea className={`${field} mt-2 block w-full`} value={intervention} onChange={(event) => setIntervention(event.target.value)} /></label>
        <div className="my-2 flex gap-2">{['nudge', 'say'].map((action) => <Button key={action} variant="outline" disabled={!intervention || busy || ['completed', 'failed', 'aborted'].includes(selected.status)} onClick={() => void act(async () => { await request.post(`${BASE}/workshop/runs/${selected.id}/interventions`, { action, role, text: intervention, source: 'typed' }); setIntervention(''); })}>{action === 'say' ? 'Send human turn' : 'Nudge model'}</Button>)}</div>
        {(selected.state.transcript || []).map((turn, index) => <article key={index} className="my-2 rounded bg-surface-secondary p-3"><strong>{turn.role}</strong><p className="whitespace-pre-wrap">{turn.content}</p></article>)}
        {selected.state.judgment && <dl>{Object.entries(selected.state.judgment.judgment).map(([axis, score]) => <div key={axis} className="flex justify-between gap-3"><dt>{axis}</dt><dd>{score} / 6</dd></div>)}</dl>}
      </section>}
    </>}
  </main>;
}
