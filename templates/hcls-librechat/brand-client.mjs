import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const clientDir = process.argv[2];
if (!clientDir) throw new Error('Expected the LibreChat client directory');

const indexPath = join(clientDir, 'index.html');
let index = await readFile(indexPath, 'utf8');
if (!index.includes('<title>Nebius Scientific AI Agent</title>')) {
  index = index
    .replace('<title>LibreChat</title>', '<title>Nebius Scientific AI Agent</title>');
  await writeFile(indexPath, index, 'utf8');
}
