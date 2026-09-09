import { useState } from 'react';
import { Button } from '@librechat/client';
import { Atom, BookOpen, Server, Dna, FlaskConical, ScanLine, ArrowUpRight, Check } from 'lucide-react';
import { useChatContext, useChatFormContext } from '~/Providers';
import { useGetStartupConfig } from '~/data-provider';
import { useRequiresKey } from '~/hooks';

const workflows = [
  {
    id: 'infra', title: 'Build the compute plan for your demo', icon: Server, tag: 'AI infrastructure',
    description: 'Turn your model idea into a GPU, batch-job or inference-endpoint plan using the installed Nebius skills.',
    tools: 'Tavily · hosted model catalog · Nebius setup guidance',
    skills: 'Cloud basics · capacity & quotas · Serverless jobs & endpoints',
    prompt: 'Help me tackle the AI infrastructure challenge at the Stockholm Longevity × AI Hackathon. Introduce your installed Nebius skills for cloud setup, capacity, compute and Serverless jobs/endpoints, plus Tavily for official-documentation research. Ask which workload I want to build. Once I choose, load nebius-cloud-basics and the one task-specific skill needed; do not load the whole skill pack or fetch the full model catalog. Use a focused Tavily search if current details are needed. Produce one concrete configuration with a small benchmark and a cost-estimation method. If a hosted scientific model is relevant, inspect that model’s schema. Use nebius-infrastructure-prep when I need a local MCP setup handoff: https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md, with SAFE_MODE=true. The skills are installed here; executing cloud commands needs my own connected environment. Do not ask for credentials or create cloud resources.',
  },
  {
    id: 'biology', title: 'Try the event’s two aging models', icon: Dna, tag: 'Longevity biology × AI',
    description: 'Added for this event: AltumAge for DNA methylation and Clinical PhenoAge for blood biomarkers.',
    tools: 'AltumAge · Clinical PhenoAge · Tavily',
    skills: 'aging-models · scientific-gateway',
    prompt: 'Show me how this agent can help with the longevity-biology challenge using the two hosted aging models: AltumAge for DNA methylation and Clinical PhenoAge for blood biomarkers. Load aging-models and scientific-gateway; discover my live model access and get_model_schema for both models. Use Tavily to find primary research and explain what each model estimates and which data it needs. Offer two concrete starting demos: a small, clearly labeled synthetic PhenoAge example, or preparation of a correctly ordered AltumAge methylation dataset. Explain why these models use different inputs and are not interchangeable aging clocks. Ask which scientific question and demo I want to explore. After I choose, show the exact inputs and obtain my go-ahead before inference. For AltumAge, verify the 20,318-CpG input requirement and the available transfer path before promising a run. End with an evaluation idea and an artifact I could show at the hackathon. Predictions are research outputs, not clinical assessments.',
  },
  {
    id: 'molecules', title: 'Explore a longevity target in 3D', icon: Atom, tag: 'Longevity biology × AI',
    description: 'Research a target, plan a folding or docking experiment, and inspect real protein structures and ligand poses in chat.',
    tools: 'Tavily · OpenFold2 · DiffDock · interactive 3D viewer',
    skills: 'openfold2 · diffdock · drug-discovery-pipeline',
    prompt: 'Help me build a target-exploration demo for the longevity-biology challenge. Introduce the tools I have here: Tavily for cited research, OpenFold2 for protein folding, DiffDock for ligand poses and visualize_structure for an interactive 3D result. Load the relevant openfold2, diffdock and drug-discovery-pipeline skills. Ask for a target or longevity question, or offer a small example if I am new to this. Research the target with Tavily, discover model access and inspect live schemas. Propose one bounded folding or docking run with its actual required inputs; explain how I can rotate, zoom and inspect the returned structure in chat. Offer Boltz2 or the hosted protein-design models only when their live contracts fit the task. Ask before inference and do not promise file-upload or batch-viewer capabilities that are unavailable. Explain that a predicted structure or docking score is a research hypothesis, not evidence of binding or efficacy.',
  },
  {
    id: 'trust', title: 'Fact-check a longevity claim', icon: BookOpen, tag: 'Communication, trust & policy',
    description: 'Use Tavily and the aging-model skills to turn a claim about biological age into a cited, understandable evidence brief.',
    tools: 'Tavily web search · AltumAge & PhenoAge model schemas',
    skills: 'tavily-research · aging-models',
    prompt: 'Help me build a communication, trust or policy demo that shows what this agent can actually do. Use tavily-research for Tavily web search and aging-models to explain the hosted AltumAge and Clinical PhenoAge models. Ask for an audience and a longevity claim; offer “Does a lower predicted biological age prove better health?” as a starting example. Search primary sources with Tavily, inspect relevant live model schemas, and build a short evidence table with citations, study population, result and limitations. Show the distinction between a model output, an association and a validated health outcome. Produce an accessible fact-check or interactive-demo outline using those real capabilities. Verify current official sources if a policy question arises. No inference is needed for the evidence brief.',
  },
  {
    id: 'clinical', title: 'Prototype a healthspan research assistant', icon: ScanLine, tag: 'Healthspan & clinical translation',
    description: 'Explore biomarker and imaging workflows with PhenoAge, chest-X-ray reasoning and CT segmentation model contracts.',
    tools: 'Clinical PhenoAge · NV-Reason-CXR · NV-Segment-CT · Tavily',
    skills: 'aging-models · imaging-models',
    prompt: 'Help me build a healthspan and clinical-translation research demo using capabilities available through this agent. Introduce Clinical PhenoAge for biomarker-based age estimates, NV-Reason-CXR-3B for chest-X-ray research and NV-Segment-CT for CT segmentation. Load aging-models and imaging-models, discover my live model access, inspect the relevant schemas and check readiness before offering execution. Ask whether I want a synthetic biomarker demo or an imaging-workflow design. Use Tavily to find primary research and a suitable public example dataset. Propose concrete input preparation, model output, human review and evaluation; distinguish what runs here from steps awaiting a compatible image/file transfer path or runtime. Ask before inference. Use public, synthetic or appropriately de-identified data only. This is a research prototype without EHR access or clinical validation.',
  },
  {
    id: 'wildcard', title: 'Combine models for your own idea', icon: FlaskConical, tag: 'Open / wildcard',
    description: 'Discover the hosted genomics, molecule and protein-design models, then connect them to your own longevity question.',
    tools: 'Evo2 · GenMol · ProteinMPNN · RFdiffusion · Tavily',
    skills: 'evo2 · genmol · protein-binder-design · scientific-batch',
    prompt: 'Help me turn my own scientific question into a wildcard AI × longevity demo. Start with a short tour of what I can use here: Tavily for research; AltumAge and Clinical PhenoAge for aging; Evo2 for DNA-sequence generation; GenMol for molecules; ProteinMPNN for protein sequences; and scientific-batch models such as ESMFold2, Protenix v2, RFdiffusion, BindCraft and BoltzGen for structure and design. Explain the interactive viewer for supported real structure results. Discover my live catalog and load the relevant installed skills, such as evo2, genmol, protein-binder-design or scientific-batch. Ask about my expertise and idea, then suggest two small workflows using named tools with a concrete input and output at each step. Verify schemas, access, runtime readiness and artifact compatibility before chaining models. Use Tavily for related work and propose an evaluation and Sunday demo artifact. Ask before submitting inference or batch jobs. Use the installed Nebius infrastructure skills if my idea needs a deployment plan.',
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
          Search with Tavily, explore hosted scientific models, inspect structures in 3D,
          and plan your compute with the installed Nebius skills. Pick a challenge to see where to begin.
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
      {selected === 'infra' && (
        <aside aria-label="Infrastructure setup handoff" className="mt-4 rounded-xl border border-border-medium bg-surface-secondary p-4 text-sm text-text-primary">
          <h4 className="font-semibold">Ten Nebius infrastructure skills are installed.</h4>
          <p className="mt-2 text-xs leading-5 text-text-secondary">Use them here for cloud setup, capacity, compute, Serverless jobs and endpoints, data and secrets, recipes, and troubleshooting. Your cloud account is not connected to this chat; use the handoff below to execute the plan in your own environment.</p>
          <p className="my-3 select-all break-words text-xs">Fetch and follow the installation guide: https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md</p>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <Button type="button" variant="outline" size="sm" onClick={async () => {
              try {
                await navigator.clipboard.writeText('Fetch and follow the installation guide: https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md');
                setCopyStatus('Setup prompt copied. Paste it into your local coding agent.');
              } catch { setCopyStatus('Copy is unavailable. Select and copy the setup prompt above.'); }
            }}>Copy MCP setup prompt</Button>
            <a href="https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md" target="_blank" rel="noreferrer" className="underline underline-offset-4">Official setup guide</a>
            <a href="https://github.com/nebius/skills" target="_blank" rel="noreferrer" className="underline underline-offset-4">Nebius skills source</a>
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
