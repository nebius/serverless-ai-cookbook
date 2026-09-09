import { useState } from 'react';
import { Button } from '@librechat/client';
import { Atom, BookOpen, Compass, Dna, FlaskConical, ScanLine, ArrowUpRight, Check } from 'lucide-react';
import { useChatContext, useChatFormContext } from '~/Providers';
import { useGetStartupConfig } from '~/data-provider';
import { useRequiresKey } from '~/hooks';

const workflows = [
  {
    id: 'explore', title: 'Find the right model', icon: Compass, tag: 'Start here',
    description: 'Explore the scientific catalog and match a model to your question.',
    prompt: 'Help me choose a scientific model. Discover the models available to me, group them by task, and explain the inputs and outputs of the most useful options. Ask about my research question before suggesting a run.',
  },
  {
    id: 'fold', title: 'Fold a protein', icon: Dna, tag: 'Guided example',
    description: 'Go from an amino-acid sequence to a structure and confidence scores.',
    prompt: 'Guide me through a small protein-folding example. Discover the available structure models and read the OpenFold2 input schema. Prepare the synthetic sequence MKTAYIAKQRQISFVK, explain the expected structure and confidence outputs, and let me choose whether to run it. Do not submit a job yet.',
  },
  {
    id: 'molecules', title: 'Explore molecular design', icon: Atom, tag: 'Plan a workflow',
    description: 'Prepare a docking or molecule-generation experiment with clear inputs.',
    prompt: 'Help me plan a molecular docking or design workflow. Discover DiffDock, GenMol, MolMIM and ProteinMPNN, explain their distinct tasks, and ask which input I have. Use the selected model’s published schema. Explain any file-preparation requirements before proposing one bounded run.',
  },
  {
    id: 'sequences', title: 'Study sequences & aging', icon: FlaskConical, tag: 'Plan a workflow',
    description: 'Explore DNA generation, sequence alignment and biological-age models.',
    prompt: 'Show me the available sequence, MSA and biological-age workflows. Discover their exact schemas and explain which data each requires. Help me choose one useful example or evaluation plan without generating missing scientific data or starting compute.',
  },
  {
    id: 'imaging', title: 'Investigate biomedical images', icon: ScanLine, tag: 'Research workflow',
    description: 'Understand image inputs, preprocessing and evaluation before a run.',
    prompt: 'Guide me through the biomedical-imaging tools available here. Discover the chest X-ray reasoning and CT-segmentation contracts, explain input formats and evaluation methods, and identify any missing file capabilities. Keep this at the planning stage; do not offer a diagnosis or start a run.',
  },
  {
    id: 'literature', title: 'Research the literature', icon: BookOpen, tag: 'Web research',
    description: 'Find papers, compare methods and build a research plan with sources.',
    prompt: 'Help me research a scientific question. Ask for my topic and scope, then use web search to find relevant primary sources, compare methods and limitations, and cite the sources. Do not submit scientific compute as part of a literature review.',
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

  const chooseWorkflow = (workflow: (typeof workflows)[number]) => {
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
        <h2 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">What would you like to discover?</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
          Bring a research question, explore a model, or start with a guided workflow.
        </p>
      </header>

      {requiresKey && (
        <div role="status" className="mb-5 rounded-xl border border-border-medium bg-surface-secondary p-4 text-sm text-text-primary">
          Connect your provider key using <strong>Provider key</strong> next to the model picker to chat with {modelLabel}.
          You can also choose a Nebius model to continue.
        </div>
      )}

      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-text-primary">Start a workflow</h3>
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
            </button>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary">
        <span aria-live="polite">{selected ? 'Your starting prompt is ready below. Edit it or send when ready.' : 'Choose a card to prepare a prompt, or type your own question below.'}</span>
        {selected && <Button variant="ghost" size="sm" onClick={() => { methods.setValue('text', ''); setSelected(null); }}>Clear</Button>}
      </div>
    </section>
  );
}
