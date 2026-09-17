import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input } from '@librechat/client';
import { request } from 'librechat-data-provider';
import { compareBatch, comparisonCsv } from './scientific-comparison';
import type { WorkshopRun as Run } from './scientific-comparison';

type Job = { id: string; status: string; created_at: string; error?: string; files: string[] };
type Catalog = { catalog: { judge_model: string; data: { id: string; clinician_eligible: boolean; patient_eligible: boolean }[] };
  profiles: { data: { id: string; profile_id?: string; name?: string }[] }; limits: { profiles: number; workers_per_team: number } };
const BASE = '/api/scientific-demos';
const field = 'rounded-lg border border-border-medium bg-surface-primary p-2 text-text-primary';
const errorText = (error: Error) => {
  const detail = (error as Error & { response?: { data?: { error?: string } } }).response?.data?.error;
  return detail || error.message;
};
function download(name: string, data: BlobPart, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Demos() {
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
    <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <div><p className="text-xs text-text-secondary">NEBIUS SCIENTIFIC AI</p><h1 className="text-2xl font-semibold">Clinical AI demos</h1></div>
      <Link to="/c/new" className="underline">Back to chat</Link>
    </header>
    <nav aria-label="Demo selection" className="mb-5 flex flex-wrap gap-2">
      <Button variant={clinical ? 'default' : 'outline'} onClick={() => setParams({ tab: 'clinical' })}>Clinical Report Draft</Button>
      <Button variant={!clinical ? 'default' : 'outline'} onClick={() => setParams({ tab: 'mindeval' })}>MindEval Workshop</Button>
    </nav>
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
