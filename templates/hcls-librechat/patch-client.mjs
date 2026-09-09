import { readFile, writeFile } from 'node:fs/promises';
const path = '/app/client/src/components/Chat/ChatView.tsx';
let source = await readFile(path, 'utf8');
for (const [before, after] of [
  ["import ConversationStarters from './Input/ConversationStarters';", ''],
  ['{isLandingPage && <ConversationStarters />}', ''],
  ["'flex-1 items-center justify-end sm:justify-center'", "'flex-1 min-h-0 overflow-y-auto items-center pt-16 pb-4'"],
]) {
  if (!source.includes(before)) throw new Error(`Unsupported ChatView: missing ${before}`);
  source = source.replace(before, after);
}
await writeFile(path, source);
