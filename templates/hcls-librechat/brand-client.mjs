import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const clientDir = process.argv[2];
if (!clientDir) throw new Error('Expected the LibreChat client directory');

const indexPath = join(clientDir, 'index.html');
const workbenchPath = join(clientDir, 'assets', 'nebius-scientific-workbench.js');
const workbenchScript = String.raw`(() => {
  const tutorials = [
    ['Protein Folding & Structure', 'Boltz2 · OpenFold2 · OpenFold3', 'Compare structures, confidence, artifacts, and fixed-input benchmarks.'],
    ['Molecular Docking & Design', 'DiffDock · GenMol · MolMIM · ProteinMPNN', 'Prepare docking and design workflows with matched evaluation criteria.'],
    ['Molecular Dynamics · GROMACS', 'GPU simulation workbench', 'Prepare, submit, monitor, and validate bounded MD runs.'],
    ['Biomedical Imaging', 'Chest X-ray reasoning · CT segmentation', 'Research-only CT/X-ray workflows with validation and human review.'],
    ['Genomics & Biological Age', 'Evo2 · AltumAge · PhenoAge', 'Plan reproducible genomics and biological-age evaluations.'],
    ['Audio Transcription · Tutorial', 'Readiness placeholder', 'Define streaming latency, WER, and concurrency acceptance tests.'],
  ];

  const chooseTutorial = (label) => {
    const selector = document.querySelector('[data-testid="model-selector-button"]');
    if (!selector) return;
    selector.click();
    const select = () => [...document.querySelectorAll('[role="option"]')]
      .find((option) => option.textContent?.trim().startsWith(label))?.click();
    requestAnimationFrame(() => requestAnimationFrame(select));
  };

  const suppressStandardLanding = (main) => {
    [...main.querySelectorAll('h1')]
      .filter((heading) => heading.textContent?.trim() === 'New chat')
      .forEach((heading) => heading.classList.add('nebius-hidden-landing'));

    // LibreChat renders an agent profile below the selector. The workbench already
    // supplies that identity and the tutorial choices, so hide the duplicate card.
    const profileTitle = [...main.querySelectorAll('p[aria-hidden]')]
      .find((element) => element.textContent?.includes('Nebius Scientific AI Agent') ||
        tutorials.some(([title]) => element.textContent?.includes(title)));
    const profile = profileTitle?.parentElement?.parentElement;
    if (profile && !profile.querySelector('textarea, input[placeholder^="Message "]')) {
      profile.classList.add('nebius-hidden-landing');
    }
  };

  const syncWorkbench = () => {
    const main = document.querySelector('main');
    let panel = document.getElementById('nebius-scientific-workbench');
    if (location.pathname !== '/c/new' || !main) {
      panel?.remove();
      return;
    }
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'nebius-scientific-workbench';
      panel.setAttribute('aria-label', 'Nebius Scientific AI Agent tutorials');
      const cards = tutorials.map(([title, models, description]) =>
        '<button type="button" data-nebius-tutorial="' + title + '"><strong>' + title +
        '</strong><span>' + models + '</span><small>' + description + '</small></button>',
      ).join('');
      panel.innerHTML = '<header class="nebius-workbench-header">' +
        '<div class="nebius-workbench-brand"><img src="assets/logo.svg" alt="Nebius logo" />' +
        '<div><p>Nebius Scientific AI Agent</p><h2>Scientific AI Workbench</h2></div></div>' +
        '<div class="nebius-agent-control" aria-label="Choose an agent"></div></header>' +
        '<p class="nebius-workbench-intro">Choose a guided tutorial or select a specialist, then start your chat below.</p>' +
        '<div class="nebius-tutorial-grid">' + cards + '</div>';
      panel.addEventListener('click', (event) => {
        const button = event.target.closest('[data-nebius-tutorial]');
        if (button) chooseTutorial(button.dataset.nebiusTutorial);
      });
      main.prepend(panel);
    }

    const selector = document.querySelector('[data-testid="model-selector-button"]');
    const toolbar = selector?.parentElement?.parentElement;
    const control = panel.querySelector('.nebius-agent-control');
    if (toolbar && control && !control.contains(toolbar)) control.append(toolbar);
    suppressStandardLanding(main);
  };

  new MutationObserver(syncWorkbench).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('popstate', syncWorkbench);
  syncWorkbench();
})();`;

let index = await readFile(indexPath, 'utf8');
if (!index.includes('<title>Nebius Scientific AI Agent</title>')) {
  index = index
    .replace('<title>LibreChat</title>', '<title>Nebius Scientific AI Agent</title>')
    .replace('</head>', `  <meta name="theme-color" content="#052B42" />
  <style id="nebius-scientific-theme">
    :root { color-scheme: light; }
    body { background: #F5F8FC; }
    #root { border-top: 4px solid #E0FF4F; }
    #nebius-scientific-workbench { max-width: 1080px; margin: 0 auto .85rem; padding: 1.25rem; border-radius: 1rem; background: #052B42; color: #fff; box-shadow: 0 16px 40px rgba(5,43,66,.16); }
    .nebius-workbench-header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
    .nebius-workbench-brand { display: flex; align-items: center; gap: 1rem; min-width: 0; }
    .nebius-workbench-header img { width: 131px; height: 36px; object-fit: contain; background: #E0FF4F; border-radius: .4rem; }
    .nebius-workbench-header p { margin: 0; color: #E0FF4F; font-size: .8rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
    .nebius-workbench-header h2 { margin: .18rem 0 0; color: #fff; font-size: 1.5rem; font-weight: 700; }
    .nebius-agent-control > div { display: flex; align-items: center; gap: .45rem; }
    .nebius-agent-control [data-testid="model-selector-button"] { border-color: rgba(224,255,79,.65); }
    .nebius-workbench-intro { max-width: 750px; margin: .9rem 0; color: #D6E5ED; line-height: 1.45; }
    .nebius-tutorial-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .7rem; }
    .nebius-tutorial-grid button { min-height: 126px; padding: .85rem; border: 1px solid rgba(224,255,79,.48); border-radius: .7rem; background: rgba(255,255,255,.07); color: #fff; text-align: left; cursor: pointer; transition: background .15s ease, transform .15s ease; }
    .nebius-tutorial-grid button:hover, .nebius-tutorial-grid button:focus-visible { background: rgba(224,255,79,.16); outline: 2px solid #E0FF4F; outline-offset: 2px; transform: translateY(-1px); }
    .nebius-tutorial-grid strong, .nebius-tutorial-grid span, .nebius-tutorial-grid small { display: block; }
    .nebius-tutorial-grid strong { font-size: .94rem; }
    .nebius-tutorial-grid span { margin-top: .35rem; color: #E0FF4F; font-size: .78rem; font-weight: 600; }
    .nebius-tutorial-grid small { margin-top: .45rem; color: #D6E5ED; font-size: .75rem; line-height: 1.35; }
    .nebius-hidden-landing { display: none !important; }
    @media (max-width: 900px) { .nebius-tutorial-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 700px) { .nebius-workbench-header { align-items: flex-start; flex-direction: column; } .nebius-agent-control { width: 100%; } }
    @media (max-width: 560px) { #nebius-scientific-workbench { margin: 0 .25rem .75rem; padding: 1rem; } .nebius-tutorial-grid { grid-template-columns: 1fr; } }
  </style>
  <script defer src="assets/nebius-scientific-workbench.js"></script>
</head>`);
  await writeFile(indexPath, index, 'utf8');
}
await writeFile(workbenchPath, workbenchScript, 'utf8');
