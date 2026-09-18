/** Separate input transfers from model execution using the public operation contract. */
export function runDisplay(run: { protocol?: string; status?: string; operation?: { protocol?: string } }) {
  const upload = (run.protocol || run.operation?.protocol) === 'scientific-artifact-upload-v1';
  const terminal = ['succeeded', 'failed', 'cancelled', 'completed', 'preempted', 'expired'].includes(run.status || '');
  const pending = !terminal;
  return {
    upload, terminal,
    status: upload ? (pending ? 'Upload pending' : ['succeeded', 'completed'].includes(run.status || '')
      ? 'Upload finalized' : `Upload ${run.status}`) : run.status || 'unknown',
    description: upload && pending ? 'Waiting for input transfer or finalization; this is not inference.'
      : run.status === 'queued' ? 'Accepted; execution has not started' : '',
    showComputeTiming: !upload,
    showResult: !upload && ['succeeded', 'completed'].includes(run.status || ''),
  };
}
