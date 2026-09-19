/** Separate input transfers from model execution using the public operation contract. */
export function runDisplay(run: { protocol?: string; status?: string; operation?: { protocol?: string } }) {
  const protocol = run.protocol || run.operation?.protocol;
  const upload = protocol === 'scientific-artifact-upload-v1';
  const batch = protocol === 'scientific-batch-v1';
  const terminal = ['succeeded', 'failed', 'cancelled', 'completed', 'preempted', 'expired'].includes(run.status || '');
  const pending = !terminal;
  return {
    upload, terminal,
    status: upload ? (pending ? 'Upload pending' : ['succeeded', 'completed'].includes(run.status || '')
      ? 'Upload finalized' : `Upload ${run.status}`)
      : batch && run.status === 'running' ? 'Workflow active' : run.status || 'unknown',
    description: upload && pending ? 'Waiting for input transfer or finalization; this is not inference.'
      : batch && pending ? 'Individual stages may be queued, loading or computing. Open Details for stage status.'
      : run.status === 'queued' ? 'Accepted; execution has not started' : '',
    // A batch's generic started_at is orchestration, not GPU admission. The
    // observed BindCraft run spent18 minutes queued after that timestamp.
    // Do not present a zero wait or this interval as measured GPU execution.
    showComputeTiming: !upload && !batch,
    readyTimingLabel: 'Accepted → ready (includes queue)',
    showResult: !upload && ['succeeded', 'completed'].includes(run.status || ''),
  };
}
