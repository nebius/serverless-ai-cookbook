import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
const clientDir = process.argv[2];
if (!clientDir) throw new Error('Expected the LibreChat client directory');
const path = join(clientDir, 'index.html');
let index = await readFile(path, 'utf8');
index = index.replace(/<title>.*?<\/title>/, '<title>Nebius Scientific AI Agent</title>');
index = index.replace('</head>', `<meta name="theme-color" content="#052B42" />
<style id="nebius-scientific-theme">
  #root { border-top: 3px solid #E0FF4F; }
  #nebius-scientific-workbench { box-sizing: border-box; flex: 0 0 auto; width: 100%; max-width: 896px; margin: auto auto 18px; padding: 12px 24px 0; }
  .nebius-workbench-header { margin: 0 0 24px; text-align: left; }
  .nebius-workbench-header img { display: block; width: 110px; height: 31px; padding: 3px 6px; border-radius: 4px; background: #E0FF4F; object-fit: contain; margin-bottom: 16px; }
  .nebius-workbench-header h2 { margin: 0; font-size: clamp(23px, 3vw, 32px); line-height: 1.2; font-weight: 600; letter-spacing: -.025em; color: rgb(var(--text-primary)); }
  .nebius-workbench-header p { margin: 10px 0 0; font-size: 14px; color: rgb(var(--text-secondary)); }
  .nebius-tutorial-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 10px; }
  .nebius-tutorial-grid button { min-width: 0; min-height: 130px; border: 1px solid rgb(var(--border-medium)); border-radius: 12px; background: rgb(var(--surface-secondary)); padding: 16px; text-align: left; color: rgb(var(--text-primary)); transition: border-color .15s, background .15s; }
  .nebius-tutorial-grid button:hover { border-color: #78919E; background: rgb(var(--surface-tertiary)); }
  .nebius-tutorial-grid button:focus-visible { outline: 2px solid #78919E; outline-offset: 3px; }
  .nebius-tutorial-grid button[aria-pressed="true"] { background: #052B42; color: #fff; border-color: #052B42; box-shadow: inset 3px 0 #E0FF4F; }
  .nebius-tutorial-grid strong, .nebius-tutorial-grid span, .nebius-tutorial-grid small { display: block; }
  .nebius-tutorial-grid strong { font-size: 14px; line-height: 1.4; font-weight: 600; }
  .nebius-tutorial-grid span { margin-top: 7px; font-size: 11px; line-height: 1.5; opacity: .75; }
  .nebius-tutorial-grid small { margin-top: 7px; font-size: 12px; line-height: 1.5; opacity: .8; }
  @media(max-width:1100px) { .nebius-tutorial-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
  @media(max-width:600px) { #nebius-scientific-workbench { padding: 8px 16px 0; margin-top: 0; } .nebius-workbench-header { margin-bottom: 18px; } .nebius-tutorial-grid { gap: 8px; } .nebius-tutorial-grid button { padding: 12px; min-height: 134px; } .nebius-tutorial-grid small { display: none; } }
</style></head>`);
await writeFile(path, index);
