import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@librechat/client';

export const workspaceTourPrompt = 'Help me get started with my Scientific AI workspace. List the Apps authorized for my key, check whether my bucket is mounted, and read /workspace/examples/v1/README.md and the example manifest if present. Recommend three examples I can actually use, with their inputs and expected outputs. Do not run inference yet. If the examples or credentials are missing, explain what is missing rather than inventing files or asking me to paste secrets into chat.';

const packInstructions = 'Read the matching case README and recipes in /workspace/examples/v1. Check that my live key authorizes the exact model and inspect its current schema. Do not invent a case path or substitute a different model without telling me. Show the selected input and expected output before starting. Use a new output directory outside examples; preserve the original run ID and resume the same run if polling is interrupted. Return download links to the actual saved results and state limitations.';

export const starterExamples = [
  { id: 'tour', title: 'Explore my workspace', input: 'Your model catalog and sample-pack index', output: 'Three suitable examples; no model inference', prompt: workspaceTourPrompt },
  { id: 'protein', title: 'Fold a sample protein', input: 'One public protein sequence from the starter pack', output: 'Predicted structure, returned confidence and an operation ID',
    prompt: `Help me run one OpenFold2 protein-folding starter example. ${packInstructions} Retrieve the completed structure, open it in the 3D viewer if its output is supported, and explain that confidence is not experimental validation.` },
  { id: 'molecule', title: 'Generate a few molecules', input: 'One GenMol starter recipe', output: 'Generated SMILES and a downloadable results file',
    prompt: `Help me run one small GenMol molecule-generation starter example. ${packInstructions} Keep the recipe's bounded candidate count. Summarize actual returned molecules and measured properties; do not claim affinity, safety or drug efficacy.` },
  { id: 'speech', title: 'Transcribe a teaching consultation', input: 'One complete public English recording, with its reference transcript', output: 'Full transcript, reference comparison and source links',
    prompt: `Help me transcribe one complete English teaching consultation from the speech starter examples using an authorized English speech model. ${packInstructions} Do not shorten the recording. Preserve the full transcript and compare it with the supplied human reference if present. Keep this to transcription and quality comparison, not diagnosis or a report draft.` },
  { id: 'aging', title: 'Try a synthetic aging-clock example', input: 'One synthetic laboratory profile, with declared units', output: 'PhenoAge output and the exact inputs used',
    prompt: `Help me run one synthetic PhenoAge starter example. ${packInstructions} Check the laboratory units from the recipe. Save the numerical result with the input profile and explain the synthetic, research-only nature of this example; do not interpret it as a real person's health assessment.` },
  { id: 'image', title: 'Segment a teaching image', input: 'One synthetic SAM 2 image example and its prompts', output: 'Segmentation result and downloadable artifacts',
    prompt: `Help me run one SAM 2 image-segmentation starter example. ${packInstructions} Preserve the original image and prompts, inspect the complete result artifacts, and describe what was segmented without implying clinical accuracy.` },
];

export default function ScientificGettingStarted() {
  const [copied, setCopied] = useState('');
  const [error, setError] = useState('');
  const copyPrompt = async (id: string, text: string) => {
    setError('');
    try { await navigator.clipboard.writeText(text); setCopied(id); }
    catch { setError('Clipboard unavailable. Select and copy the prompt text below.'); }
  };
  return <section aria-label="Getting started" className="space-y-6">
    <div>
      <h2 className="text-2xl font-semibold">Your first scientific run</h2>
      <p className="mt-2 text-sm leading-6 text-text-secondary">Use the existing Scientific AI Agent for models, literature, analysis and files. Each person has their own chat instance; colleagues may share the same tenant bucket. Your API key determines which Apps you can use.</p>
    </div>
    <ol className="grid gap-3 md:grid-cols-3">
      <li className="rounded-xl border border-border-medium p-4"><strong>1. Check your Apps</strong><p className="mt-2 text-sm text-text-secondary">Open Apps to verify access. If a key is needed, enter it in the key settings—not in a chat message. Chat-provider keys and Scientific AI keys are different.</p><Link className="mt-2 inline-block underline" to="/demos?tab=apps">Open Apps</Link></li>
      <li className="rounded-xl border border-border-medium p-4"><strong>2. Choose sample data</strong><p className="mt-2 text-sm text-text-secondary">Start with the licensed or synthetic examples in your bucket. Read the case instructions before replacing an example with your own data.</p><Link className="mt-2 inline-block underline" to="/demos?tab=workspace&path=examples%2Fv1">Open sample files</Link></li>
      <li className="rounded-xl border border-border-medium p-4"><strong>3. Run, inspect, download</strong><p className="mt-2 text-sm text-text-secondary">Send a prompt, review the proposed input, then request the run. Follow its original ID in Runs and download the completed files. A queued run may be waiting for GPU capacity.</p><Link className="mt-2 inline-block underline" to="/demos?tab=runs">Open Runs</Link></li>
    </ol>
    <div>
      <h3 className="text-lg font-semibold">Prompts you can try</h3>
      <p className="mt-1 text-sm text-text-secondary">Copy a prompt into chat and edit it. Copying never submits a request. Model examples require access to that App; the workspace tour checks this first.</p>
    </div>
    <div className="grid gap-3 md:grid-cols-2">
      {starterExamples.map((example) => <article key={example.id} data-example={example.id} className="rounded-xl border border-border-medium p-4">
        <h4 className="font-semibold">{example.title}</h4>
        <p className="mt-2 text-sm"><strong>Input:</strong> {example.input}</p>
        <p className="mt-1 text-sm"><strong>You get:</strong> {example.output}</p>
        <details className="mt-3 text-sm"><summary className="cursor-pointer underline">Read the prompt</summary><p className="mt-2 select-text whitespace-pre-wrap leading-6">{example.prompt}</p></details>
        <Button className="mt-3" variant="outline" size="sm" onClick={() => void copyPrompt(example.id, example.prompt)}>{copied === example.id ? 'Copied' : `Copy ${example.title.toLowerCase()} prompt`}</Button>
      </article>)}
    </div>
    <p role="status" className="text-sm">{error || (copied ? 'Prompt copied. Paste it into a new chat when you are ready.' : '')}</p>
    <aside className="rounded-xl border border-border-medium p-4 text-sm leading-6">
      <h3 className="font-semibold">Files, waiting and recovery</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>Upload scientific inputs through Workspace; refer to their <code>/workspace/</code> paths. The ordinary chat attachment picker does not automatically upload bytes to a model.</li>
        <li>Keep examples unchanged. Save your results in a separate folder such as <code>/workspace/my-studies/</code>.</li>
        <li>If a request is queued, reconnect to its run. Do not submit a new copy just because a browser or chat timed out.</li>
        <li>If the sample folder is missing, check Workspace and ask your operator to check starter-data installation. Do not paste storage secrets into chat.</li>
        <li>Prediction, simulation and report outputs are research aids, not verified scientific findings or clinical advice.</li>
      </ul>
    </aside>
    <div className="flex flex-wrap gap-4 text-sm"><Link to="/c/new" className="underline">Start a chat</Link><a href="https://github.com/rene-tech/serverless-ai-cookbook/tree/main/skills/scientific-ai" target="_blank" rel="noreferrer" className="underline">Get the Skills</a></div>
  </section>;
}
