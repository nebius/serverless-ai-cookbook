import { useState } from 'react';
import { Button } from '@librechat/client';
import { Atom, BookOpen, Server, Dna, FlaskConical, ScanLine, ArrowUpRight, Check } from 'lucide-react';
import { useChatContext, useChatFormContext } from '~/Providers';
import { useGetStartupConfig } from '~/data-provider';
import { useRequiresKey } from '~/hooks';

const workflows = [
  {
    id: 'infra', title: 'Prepare your Nebius workspace', icon: Server, tag: 'AI infrastructure · preparation',
    description: 'Plan your stack and set up skills and MCP in your own coding environment.',
    prompt: 'Help me prepare for the AI infrastructure track at the Stockholm Longevity × AI Hackathon. Use the nebius-infrastructure-prep skill. Ask about my workload, operating system, local coding agent and whether my own Nebius account is ready. Explain the relevant Nebius skills and prepare a participant-side MCP setup handoff using https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md. Keep SAFE_MODE=true. This hosted chat is not connected to my cloud account: do not request credentials, install anything here, provision resources or claim a connection. Prepare a small benchmark plan and a read-only verification checklist for my local agent. Skills from https://github.com/nebius/skills may require repository access.',
  },
  {
    id: 'biology', title: 'Explore aging & biomarkers', icon: Dna, tag: 'Longevity biology × AI',
    description: 'Scope an aging-clock or biomarker study with honest evaluation.',
    prompt: 'Help me scope a longevity-biology prototype for the Stockholm hackathon: an aging clock or biomarker-inference workflow. Ask about my research question and available public, synthetic or appropriately de-identified data. Check the live AltumAge and PhenoAge schemas before suggesting a model. Plan a baseline, held-out evaluation, missing-data rules and confounder checks; distinguish chronological-age prediction from health outcomes. Cite primary research. Do not fabricate patient data, claim clinical validity or submit compute yet.',
  },
  {
    id: 'molecules', title: 'Investigate a longevity target', icon: Atom, tag: 'Longevity biology × AI',
    description: 'Connect evidence, protein structure and drug-repurposing hypotheses.',
    prompt: 'Help me explore a longevity target or drug-repurposing hypothesis for a research-only hackathon demo. Ask which target or question I want to investigate, then find primary evidence and distinguish hypotheses from validated findings. Check relevant protein-folding and DiffDock schemas and explain required inputs. Propose one bounded experiment and a way to inspect real returned protein structures or molecule poses in the interactive viewer. A docking score does not establish binding, efficacy or safety. Do not start compute yet.',
  },
  {
    id: 'trust', title: 'Make longevity science clear', icon: BookOpen, tag: 'Communication, trust & policy',
    description: 'Build an evidence brief that makes claims and uncertainty understandable.',
    prompt: 'Help me build a communication, trust or policy prototype for the Stockholm longevity hackathon. Ask for my audience and one scientific question or contested longevity claim. Use web research to trace primary sources, separate human evidence from preclinical results and distinguish association from causation. Draft an accessible evidence brief with citations, uncertainty and a way to test audience understanding. If policy is relevant, verify the jurisdiction and current sources; do not invent legal requirements. No scientific compute is needed.',
  },
  {
    id: 'clinical', title: 'Prototype a healthspan workflow', icon: ScanLine, tag: 'Healthspan & clinical translation',
    description: 'Design a clinician-facing research demo with human review and clear limits.',
    prompt: 'Help me scope a healthspan and clinical-translation prototype for the Stockholm hackathon. Ask which clinician or preventive-care workflow I want to support. Use public, synthetic or appropriately de-identified data only; do not request identifiable health records. Plan a research-only demo, clinician review, usability and subgroup evaluation, and explicit limits. Check the live tool contracts before suggesting biomarker or imaging tools. This agent has no live EHR integration and cannot diagnose, prescribe or validate clinical risk. Do not submit compute yet.',
  },
  {
    id: 'wildcard', title: 'Shape your own challenge', icon: FlaskConical, tag: 'Open / wildcard',
    description: 'Test an original AI × longevity idea and prepare a credible Sunday demo.',
    prompt: 'Help me turn my own AI × longevity scientific question into a wildcard hackathon project. Ask about my expertise, idea, intended user and available data. Research related work with citations, identify the smallest useful prototype, map only supported parts to this agent’s tools, and define success criteria and a Sunday demo narrative with limitations. Infrastructure execution happens outside this agent; use the infrastructure-preparation workflow for a local setup handoff. Do not invent integrations, promise deployment or run compute yet.',
  },
];

export default function ScientificLanding(_props: { centerFormOnLanding: boolean }) {
  const { conversation } = useChatContext();
  const { data: startupConfig } = useGetStartupConfig();
  const { requiresKey } = useRequiresKey();
  const methods = useChatFormContext();
  const [selected, setSelected] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState('');
  const spec = startupConfig?.modelSpecs?.list?.find((item) => item.name === conversation?.spec);
  const modelLabel = spec?.label || conversation?.model || 'your selected LLM';

  const chooseWorkflow = (workflow: (typeof workflows)[number]) => {
    methods.setValue('text', workflow.prompt, { shouldDirty: true });
    setSelected(workflow.id);
    setCopyStatus('');
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
        <a href="https://luma.com/5b82vwsa" target="_blank" rel="noreferrer" className="mb-3 inline-block text-xs font-medium text-text-secondary underline underline-offset-4">Stockholm Longevity × AI Hackathon · 11–13 September 2026</a>
        <h2 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">Build something for healthier lives.</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
          Bring your expertise. Explore the evidence, plan a bounded experiment, and shape a credible demo.
        </p>
      </header>

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
            </button>
          );
        })}
      </div>
      {selected === 'infra' && (
        <aside aria-label="Infrastructure setup handoff" className="mt-4 rounded-xl border border-border-medium bg-surface-secondary p-4 text-sm text-text-primary">
          <h4 className="font-semibold">Prepare here. Connect in your own environment.</h4>
          <p className="mt-2 text-xs leading-5 text-text-secondary">Your Nebius cloud account is not connected to this chat. After setting up your account, give the setup prompt below to your local coding agent. Authentication stays on your machine; keep safe mode enabled.</p>
          <p className="my-3 select-all break-words text-xs">Fetch and follow the installation guide: https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md</p>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <Button type="button" variant="outline" size="sm" onClick={async () => {
              try {
                await navigator.clipboard.writeText('Fetch and follow the installation guide: https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md');
                setCopyStatus('Setup prompt copied. Paste it into your local coding agent.');
              } catch { setCopyStatus('Copy is unavailable. Select and copy the setup prompt above.'); }
            }}>Copy MCP setup prompt</Button>
            <a href="https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md" target="_blank" rel="noreferrer" className="underline underline-offset-4">Official setup guide</a>
            <a href="https://github.com/nebius/skills" target="_blank" rel="noreferrer" className="underline underline-offset-4">Nebius skills (access may be required)</a>
          </div>
          <p role="status" className="mt-2 text-xs text-text-secondary">{copyStatus}</p>
        </aside>
      )}
      <p className="mt-4 text-xs leading-5 text-text-secondary">Research prototypes, not clinical advice. Infrastructure planning and setup guidance are available here; account connection and execution happen outside this agent.</p>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary">
        <span aria-live="polite">{selected ? 'Your starting prompt is ready below. Edit it or send when ready.' : 'Choose a card to prepare a prompt, or type your own question below.'}</span>
        {selected && <Button variant="ghost" size="sm" onClick={() => { methods.setValue('text', ''); setSelected(null); }}>Clear</Button>}
      </div>
    </section>
  );
}
