import { readFile, writeFile } from 'node:fs/promises';
const mode = process.argv[2];
const filename = mode === 'client' ? '/app/client/src/routes/index.tsx' : '/app/api/server/index.js';
let source = await readFile(filename, 'utf8');
const anchor = mode === 'client' ? "              path: 'search'," : "  app.use('/api/keys', routes.keys);";
if (!source.includes(anchor)) throw new Error(`Unsupported pinned LibreChat ${mode} routes`);
if (mode === 'client') {
  source = "import ScientificDemos from '~/components/ScientificDemos';\n" + source;
  source = source.replace(anchor, "              path: 'demos', element: <ScientificDemos />,\n            },\n            {\n" + anchor);
} else {
  source = source.replace(anchor, anchor + "\n  app.use('/api/scientific-demos', require('./routes/scientific-demos'));" );
}
await writeFile(filename, source);
