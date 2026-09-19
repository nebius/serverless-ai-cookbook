const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { read, save } = require('./service.cjs');
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const NO_FACTS_CODE = 'no_supported_clinical_facts';
const NO_FACTS_DETAIL = 'No supported clinical facts were extracted from this source, so no report was produced. The unchanged transcript and review are retained. Check that the source contains consultation dialogue or provide fuller material in a new job. Resuming the same source does not add evidence.';

async function acquireSlot(dir, keyHash) {
  const root = path.resolve(dir, '../..');
  const slot = path.join(root, `clinical-key-${keyHash}.lock`);
  // The OS releases this advisory lock if the worker dies. Never unlink its
  // inode: another queued process may already have it open.
  const holder = spawn('flock', ['-x', slot, 'sh', '-c', 'printf "acquired\\n"; cat >/dev/null'],
    { stdio: ['pipe', 'pipe', 'ignore'] });
  await new Promise((resolve, reject) => {
    holder.once('error', reject);
    holder.once('exit', () => reject(new Error('Clinical queue lock closed before acquisition')));
    holder.stdout.once('data', resolve);
  });
  return async () => {
    const closed = new Promise((resolve) => holder.once('exit', resolve));
    holder.stdin.end();
    await closed;
  };
}

async function main() {
  const dir = process.argv[2];
  // Parent persists the PID/start-time receipt before releasing the worker.
  for (let i = 0; i < 100; i++) {
    if (await fs.access(path.join(dir, 'launched')).then(() => true, () => false)) break;
    await new Promise((resolve) => setTimeout(resolve, 100));
    if (i === 99) return;
  }
  const request = await read(path.join(dir, 'request.json'));
  const receipt = await read(path.join(dir, 'status.json'));
  await save(path.join(dir, 'status.json'), { ...receipt, status: 'queued' });
  const releaseSlot = await acquireSlot(dir, request.key_hash);
  await save(path.join(dir, 'status.json'), { ...receipt, status: 'running' });
  const log = await fs.open(path.join(dir, 'worker.log'), 'a', 0o600);
  try {
    const args = [process.env.SCIENTIFIC_CLINICAL_SCRIPT,
      `--${request.kind}`, path.join(dir, request.source), '--language', request.language,
      '--base-url', request.platform, '--report-model', request.report_model,
      '--report-provider', request.report_provider, '--output', path.join(dir, 'output')];
    let code, lastReason, noFacts;
    for (let attempt = 0; attempt < 4; attempt++) {
      const child = spawn(process.env.SCIENTIFIC_CLINICAL_PYTHON, args,
        { stdio: ['ignore', log.fd, log.fd], env: process.env });
      code = await new Promise((resolve, reject) => { child.once('exit', resolve); child.once('error', reject); });
      const last = (await fs.readFile(path.join(dir, 'worker.log'), 'utf8')).trim().split('\n').at(-1);
      let reported;
      try { reported = JSON.parse(last); } catch { /* non-workflow failure */ }
      lastReason = reported?.reason || '';
      noFacts = reported?.error_code === NO_FACTS_CODE;
      const transient = /^HTTP (429|502|503|504);/.test(lastReason);
      const timeout = /^(ReadTimeout|ConnectTimeout|ReadError|ConnectError)$/.test(lastReason);
      if (code === 0 || (!transient && !(timeout && attempt === 0)) || attempt === 3) break;
      await save(path.join(dir, 'status.json'), { ...receipt, status: 'queued', provider_retries: attempt + 1,
        error: timeout ? 'Provider timeout; resuming cached stages once. The lost provider response may still incur usage.' : 'Provider busy; waiting before resuming cached stages.' });
      await pause(5000 * 2 ** attempt);
      await save(path.join(dir, 'status.json'), { ...receipt, status: 'running', provider_retries: attempt + 1 });
    }
    await save(path.join(dir, 'status.json'), { ...receipt, status: code === 0 ? 'completed' : 'incomplete',
      finished_at: new Date().toISOString(), ...(code ? noFacts
        ? { error: NO_FACTS_DETAIL, error_code: NO_FACTS_CODE }
        : { error: `${lastReason === 'ReadTimeout' ? 'Report provider timed out. ' : ''}Workflow incomplete. Inspect saved receipts and resume this job; do not re-upload.` } : {}) });
  } catch {
    await save(path.join(dir, 'status.json'), { ...receipt, status: 'incomplete', error: 'Clinical worker could not complete.' });
  } finally {
    await log.close();
    await releaseSlot();
    await fs.unlink(path.join(dir, 'launched')).catch(() => {});
  }
}
main().catch(() => process.exitCode = 1);
