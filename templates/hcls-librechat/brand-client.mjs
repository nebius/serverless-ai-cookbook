import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const clientDir = process.argv[2];
if (!clientDir) throw new Error('Expected the LibreChat client directory');

const indexPath = join(clientDir, 'index.html');
let index = await readFile(indexPath, 'utf8');
if (!index.includes('<title>Nebius Scientific AI Agent</title>')) {
  index = index
    .replace('<title>LibreChat</title>', '<title>Nebius Scientific AI Agent</title>')
    .replace('</head>', `  <meta name="theme-color" content="#071B35" />
  <style id="nebius-scientific-theme">
    :root { color-scheme: light; }
    body { background: #F5F8FC; }
    #root { border-top: 4px solid #75E6B5; }
  </style>
</head>`);
  await writeFile(indexPath, index, 'utf8');
}
