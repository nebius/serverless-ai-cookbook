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

/** A bounded observation ending is not the saved study or model timing out. */
export function studyDisplay(state: string) {
  if (state === 'observation_expired') {
    return {
      status: 'Waiting for an update',
      description: 'The status-check window ended, not the study. Checks continue automatically while the study supervisor is available.',
    };
  }
  if (state === 'waiting_admission') {
    return {
      status: 'Waiting to start',
      description: 'This step has not been accepted yet. The existing concurrency limit still applies.',
    };
  }
  if (state === 'observation_interrupted') {
    return {
      status: 'Reconnecting to the existing operation',
      description: 'A status connection was interrupted. Saved operation IDs are retained; do not submit another copy.',
    };
  }
  // Preserve terminal and unknown states; presentation never turns a failure
  // or unrecognized state into a successful or active run.
  return { status: state, description: '' };
}
