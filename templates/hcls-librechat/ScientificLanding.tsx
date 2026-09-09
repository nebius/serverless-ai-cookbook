import { useChatContext, useChatFormContext } from '~/Providers';
import { useGetStartupConfig, useGetEndpointsQuery } from '~/data-provider';
import { useGetConversation, useNewConvo } from '~/hooks';
import useSelectMention from '~/hooks/Input/useSelectMention';

const tutorials = [
  ['protein-folding-and-structure', 'Protein Folding & Structure', 'Boltz2 · OpenFold2 · OpenFold3', 'Compare structures, confidence, and folding benchmarks.'],
  ['molecular-docking-and-design', 'Molecular Docking & Design', 'DiffDock · GenMol · MolMIM · ProteinMPNN', 'Explore binding poses and molecular design.'],
  ['molecular-dynamics', 'Molecular Dynamics · GROMACS', 'GPU simulation workbench', 'Prepare a simulation and compare performance.'],
  ['biomedical-imaging', 'Biomedical Imaging', 'Chest X-ray · CT segmentation', 'Explore image analysis and research evaluation.'],
  ['genomics-and-aging', 'Genomics & Biological Age', 'Evo2 · AltumAge · PhenoAge', 'Discover sequence and biological-age workflows.'],
  ['audio-transcription', 'Audio Transcription · Tutorial', 'Preview · model discovery', 'Plan transcription and evaluate speech models.'],
];

export default function ScientificLanding(_props: { centerFormOnLanding: boolean }) {
  const { data: startupConfig } = useGetStartupConfig();
  const { data: endpointsConfig } = useGetEndpointsQuery();
  const { conversation } = useChatContext();
  const methods = useChatFormContext();
  const getConversation = useGetConversation(0);
  const { newConversation } = useNewConvo();
  const modelSpecs = startupConfig?.modelSpecs?.list ?? [];
  const { onSelectSpec } = useSelectMention({
    modelSpecs, endpointsConfig, getConversation, newConversation, returnHandlers: true,
  });

  const selectTutorial = (name: string, title: string) => {
    const spec = modelSpecs.find((item) => item.name === name);
    if (!spec) return;
    onSelectSpec?.(spec);
    methods.setValue('text', `Start the ${title} tutorial: discover the live models and skills, list the available models, then guide me through an example and a reproducible comparison.`);
    document.querySelector<HTMLTextAreaElement>('[data-testid="text-input"]')?.focus();
  };

  return (
    <section id="nebius-scientific-workbench" aria-label="Scientific tutorials">
      <header className="nebius-workbench-header">
        <img src="/assets/logo.svg" alt="Nebius" width="131" height="36" />
        <h2>Nebius Scientific AI Agent</h2>
        <p>Explore a tutorial, or ask your own scientific question.</p>
      </header>
      <div className="nebius-tutorial-grid">
        {tutorials.map(([name, title, models, description]) => (
          <button key={name} type="button" data-tutorial={name}
            aria-pressed={conversation?.spec === name}
            onClick={() => selectTutorial(name, title)}>
            <strong>{title}</strong><span>{models}</span><small>{description}</small>
          </button>
        ))}
      </div>
    </section>
  );
}
