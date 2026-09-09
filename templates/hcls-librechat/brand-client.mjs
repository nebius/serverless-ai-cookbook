import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const clientDir = process.argv[2];
if (!clientDir) throw new Error('Expected the LibreChat client directory');
const path = join(clientDir, 'index.html');
let index = await readFile(path, 'utf8');
index = index.replace(/<title>.*?<\/title>/, '<title>Nebius Scientific AI Agent</title>');
index = index.replace('</head>', `<style id="nebius-scientific-theme">
  /* The brand accent is confined to the shell; workflow surfaces use LibreChat theme roles. */
  #root { border-top: 3px solid #E0FF4F; }
  .nebius-wordmark { width: 92px; height: auto; flex-shrink: 0; }
  #nebius-scientific-workbench { flex: 0 0 auto; }
</style></head>`);
await writeFile(path, index);
