import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@librechat/client';
import { Atom, BookOpen, Server, Dna, FlaskConical, ScanLine, ArrowUpRight, Check } from 'lucide-react';
import { useChatContext, useChatFormContext } from '~/Providers';
import { useGetStartupConfig } from '~/data-provider';
import { useRequiresKey } from '~/hooks';
import { workspaceTourPrompt } from '../ScientificGettingStarted';

const workflows = [
  {
    id: 'literature', title: 'Reproduce a published result', icon: BookOpen, tag: 'Research & evidence',
    description: 'Find an open paper and dataset, then build a bounded, provenance-rich reproduction plan.',
    tools: 'Tavily · live Apps · workspace · durable runs',
    skills: 'Literature research · scientific gateway · evaluation',
    prompt: 'Help me reproduce a published scientific result using public data and the Scientific AI Apps available to my key. Ask for my field or suggest one realistic paper. Search primary sources, verify the paper, code, dataset, license and reported metric, then inspect the live App catalog and exact schemas. Build a bounded reproduction with fixed inputs, preprocessing, seeds, metrics and artifact provenance. Do not claim reproduction from a smoke test. Ask before submitting compute, save every operation in the Runs panel, and compare the terminal result with the paper.',
  },
  {
    id: 'structure', title: 'Predict and compare structures', icon: Atom, tag: 'Proteins & complexes',
    description: 'Use the authorized folding and complex Apps, inspect confidence, and compare against public PDB references.',
    tools: 'Boltz · OpenFold · ESMFold · Protenix · 3D viewer',
    skills: 'Structure prediction · MSA · scientific batch',
    prompt: 'Set up a reproducible protein or complex structure study. Discover my live Apps instead of assuming a model is deployed. Ask for the biological question and reference structure, inspect each selected App schema, keep sequence/MSA/template treatment matched, and define RMSD, DockQ or confidence metrics as appropriate. Ask before compute, track every operation in Runs, retrieve terminal artifacts, and use the structure viewer. Distinguish prediction confidence from experimental evidence.',
  },
  {
    id: 'design', title: 'Design and rank candidates', icon: FlaskConical, tag: 'Molecules & proteins',
    description: 'Build a traceable design funnel across docking, sequence design, binders, or molecule generation.',
    tools: 'DiffDock · RFdiffusion · ProteinMPNN · BindCraft · GenMol',
    skills: 'Molecular design · binder design · artifact pipelines',
    prompt: 'Help me design and rank molecular or protein candidates. Start from a live authorized catalog and ask about the target, public reference data and experimental decision. Inspect schemas before chaining Apps. Define fixed preparation, candidate counts, filters, ranking metrics, failure handling and a held-out or experimental validation plan. Ask before compute, upload large inputs as artifacts, track operation IDs, and keep generated hypotheses separate from measured binding or function.',
  },
  {
    id: 'genomics', title: 'Analyze sequences and aging clocks', icon: Dna, tag: 'Genomics & aging',
    description: 'Evaluate DNA sequence models or biological-age clocks on public, consented, non-identifying data.',
    tools: 'Evo2 · AltumAge · PhenoAge · Tavily',
    skills: 'Genomics · aging models · cohort evaluation',
    prompt: 'Plan a genomics or biological-age analysis using only public, synthetic or appropriately governed data. Discover the live Apps and exact modality of Evo2, AltumAge and PhenoAge; they are not interchangeable. Find the original paper and public evaluation data, define train/test separation, missing-data rules, confounders, subgroup analysis and confidence intervals. Ask before inference, preserve operation IDs and provenance, and do not turn research outputs into clinical assessments.',
  },
  {
    id: 'clinical', title: 'Work with speech and medical data', icon: ScanLine, tag: 'Clinical research',
    description: 'Transcribe recordings, draft reviewable reports, or evaluate research-only imaging Apps.',
    tools: 'Nemotron Speech · report drafts · imaging Apps',
    skills: 'Clinical documentation · speech · imaging evaluation',
    prompt: 'Help with a clinical-research workflow. Ask whether I need speech transcription, a source-linked report draft, or evaluation of an imaging App. Use only public, synthetic or properly de-identified data. Discover the live contract and validate the complete file path, not a tiny substitute. For documents, preserve evidence links, uncertainties and unanswered questions and require clinician review. For imaging, define a held-out reference, calibration and subgroup checks. Do not diagnose, triage or claim clinical validation.',
  },
  {
    id: 'robotics', title: 'Augment robotics data', icon: Server, tag: 'Physical AI',
    description: 'Transform videos or bounded LeRobot datasets while preserving episodes, schema, and provenance.',
    tools: 'Cosmos · LeRobot workflow · workspace',
    skills: 'Generative media · robotics datasets · acceptance testing',
    prompt: 'Help me augment a robotics dataset with the authorized Cosmos workflow. Ask whether the input is an MP4 or LeRobot dataset, inspect the exact live schema and supported transformation dimensions, and validate the complete input/output contract. Keep episode identity, timestamps, actions, observations, schema and provenance intact. Use a bounded public LeRobot dataset first, track durable operations, inspect terminal artifacts, and state fidelity limitations before scaling.',
  },
];

export default function ScientificLanding(_props: { centerFormOnLanding: boolean }) {
  const { conversation } = useChatContext();
  const { data: startupConfig } = useGetStartupConfig();
  const { requiresKey } = useRequiresKey();
  const methods = useChatFormContext();
  const [selected, setSelected] = useState<string | null>(null);
  const spec = startupConfig?.modelSpecs?.list?.find((item) => item.name === conversation?.spec);
  const modelLabel = spec?.label || conversation?.model || 'your selected LLM';

  const chooseWorkflow = (workflow: { id: string; prompt: string }) => {
    methods.setValue('text', workflow.prompt, { shouldDirty: true });
    setSelected(workflow.id);
    requestAnimationFrame(() => {
      const input = document.querySelector<HTMLTextAreaElement>('[data-testid="text-input"]');
      input?.focus();
      if (window.matchMedia('(max-width: 639px)').matches) {
        input?.closest('form')?.scrollIntoView({ block: 'end', behavior: 'instant' });
      }
    });
  };

  return (
    <section id="nebius-scientific-workbench" aria-label="Scientific workflows"
      className="mx-auto w-full max-w-4xl px-4 pb-5 pt-4 sm:px-6 sm:pt-6">
      <header className="mb-6 sm:mb-8">
        <div className="mb-4 flex items-center gap-3">
          <img src="/assets/logo.svg" alt="Nebius" width="92" height="24" className="nebius-wordmark" />
          <span className="border-l border-border-medium pl-3 text-xs font-medium tracking-wide text-text-secondary">SCIENTIFIC WORKSPACE</span>
        </div>
        <p className="mb-3 text-xs font-medium text-text-secondary">Models, data, literature and reproducible runs in one workspace</p>
        <h2 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">Turn a scientific question into traceable work.</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
          Search with Tavily, explore hosted scientific models, inspect structures in 3D,
          run Python, install packages, work with your bucket, and reconnect to durable model runs.
        </p>
      </header>

      <aside aria-label="First visit" className="mb-5 rounded-xl border border-border-medium bg-surface-secondary p-4">
        <h3 className="font-semibold">New here? Start with your sample data.</h3>
        <p className="mt-2 text-sm leading-6 text-text-secondary">Check your model access, explore the examples in your bucket, then run one example and download its results.</p>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
          <Button variant="outline" data-starter="tour" onClick={() => chooseWorkflow({ id: 'tour', prompt: workspaceTourPrompt })}>Prepare a workspace tour</Button>
          <Link className="underline" to="/demos?tab=getting-started">Getting started &amp; example prompts</Link>
        </div>
        <p className="mt-2 text-xs text-text-secondary">This prepares a chat prompt; it does not start model inference.</p>
      </aside>

      <nav aria-label="Scientific workbench" className="mb-5 grid gap-3 sm:grid-cols-3">
        <Link to="/demos?tab=apps" className="rounded-xl border border-border-medium bg-surface-secondary p-4 hover:bg-surface-hover"><strong>Apps</strong><p className="mt-1 text-sm text-text-secondary">See exactly which models your key can use.</p></Link>
        <Link to="/demos?tab=runs" className="rounded-xl border border-border-medium bg-surface-secondary p-4 hover:bg-surface-hover"><strong>Runs</strong><p className="mt-1 text-sm text-text-secondary">Reconnect to durable work without resubmitting it.</p></Link>
        <Link to="/demos?tab=workspace" className="rounded-xl border border-border-medium bg-surface-secondary p-4 hover:bg-surface-hover"><strong>Workspace</strong><p className="mt-1 text-sm text-text-secondary">Browse and upload files in your mounted bucket.</p></Link>
      </nav>

      {requiresKey && (
        <div role="status" className="mb-5 rounded-xl border border-border-medium bg-surface-secondary p-4 text-sm text-text-primary">
          Connect your provider key using <strong>Provider key</strong> next to the model picker to chat with {modelLabel}.
          You can also choose a Nebius model to continue.
        </div>
      )}

      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-text-primary">Choose a starting point</h3>
        <span className="text-xs text-text-secondary">Your chat model stays selected</span>
      </div>
      <div className="grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 lg:grid-cols-3">
        {workflows.map((workflow) => {
          const Icon = workflow.icon;
          const active = selected === workflow.id;
          return (
            <button key={workflow.id} type="button" data-workflow={workflow.id}
              aria-pressed={active} onClick={() => chooseWorkflow(workflow)}
              className={`group flex min-h-36 flex-col rounded-2xl border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring-primary motion-reduce:transition-none ${active ? 'border-border-heavy bg-surface-active' : 'border-border-light bg-surface-primary hover:border-border-heavy hover:bg-surface-hover'}`}>
              <span className="mb-3 flex w-full items-center justify-between gap-2">
                <Icon className="size-5 text-text-primary" aria-hidden="true" />
                <span className="text-xs text-text-secondary">{workflow.tag}</span>
              </span>
              <span className="flex items-center justify-between gap-2 text-sm font-semibold text-text-primary">
                {workflow.title}
                {active ? <Check className="size-4 shrink-0" aria-hidden="true" /> : <ArrowUpRight className="size-4 shrink-0 text-text-tertiary" aria-hidden="true" />}
              </span>
              <span className="mt-2 text-xs leading-5 text-text-secondary">{workflow.description}</span>
              <span className="mt-3 block border-t border-border-light pt-3 text-xs leading-5 text-text-primary">
                <span className="font-medium">Models &amp; tools: </span>{workflow.tools}
              </span>
              <span className="mt-1 block text-xs leading-5 text-text-secondary">
                <span className="font-medium">Skills: </span>{workflow.skills}
              </span>
            </button>
          );
        })}
      </div>
      {selected === 'literature' && (
        <aside aria-label="Reproducibility guidance" className="mt-4 rounded-xl border border-border-medium bg-surface-secondary p-4 text-sm text-text-primary">
          <h4 className="font-semibold">Research and execution stay connected.</h4>
          <p className="mt-2 text-xs leading-5 text-text-secondary">Use primary sources to define the target result, save public data in Workspace, and keep every submitted operation in Runs. A successful API response alone is not a reproduced result.</p>
          <Link to="/demos?tab=apps" className="mt-3 inline-block underline underline-offset-4">Open the live App catalog</Link>
        </aside>
      )}
      <p className="mt-4 text-xs leading-5 text-text-secondary">Research prototypes, not clinical advice. The agent can execute commands as root in this environment and use its mounted files. Cloud account access is configured separately.</p>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary">
        <span aria-live="polite">{selected ? 'Your starting prompt is ready below. Edit it or send when ready.' : 'Choose a card to prepare a prompt, or type your own question below.'}</span>
        {selected && <Button variant="ghost" size="sm" onClick={() => { methods.setValue('text', ''); setSelected(null); }}>Clear</Button>}
      </div>
    </section>
  );
}
