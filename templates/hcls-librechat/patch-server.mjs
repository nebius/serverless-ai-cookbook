import { readFile, writeFile } from 'node:fs/promises';
const path = '/app/api/server/services/ToolService.js';
let source = await readFile(path, 'utf8');
const anchor = '  const filteredTools = agent.tools?.filter((tool) => {';
if (!source.includes(anchor)) throw new Error('Unsupported pinned ToolService');
// Cover both the event-driven and classic tool-loading paths.
for (const property of ['toolOptions', 'agentToolOptions']) {
  const before = `${property}: agent.tool_options,`;
  if (!source.includes(before)) throw new Error(`Unsupported tool options: ${property}`);
  source = source.replaceAll(before, `${property}: require('/opt/hcls-librechat/scientific-tool-options.cjs')(agent),`);
}
await writeFile(path, source);

// A slow/unavailable title model must not leave every chat named "New Chat"
// or keep the client polling a missing title. Preserve upstream title policy.
const titlePath = '/app/api/server/services/Endpoints/agents/title.js';
let titleSource = await readFile(titlePath, 'utf8');
for (const [before, after] of [
  ["setTimeout(() => reject(new Error('Title generation timeout')), 45000)",
   "setTimeout(() => reject(new Error('Title generation timeout')), 10000)"],
  ['const generatedTitle = await titlePromise;', 'let generatedTitle = await titlePromise;'],
  ['    if (!generatedTitle) {\n      logger.debug(`[${key}] No title generated`);\n      return;\n    }',
   `    if (!generatedTitle) {
      if (signal?.aborted || discardSignal?.aborted) return;
      generatedTitle = String(text ?? '').replace(/\\s+/g, ' ').trim().slice(0, 72) || 'Scientific research';
    }`],
]) {
  if (!titleSource.includes(before)) throw new Error('Unsupported pinned title service');
  titleSource = titleSource.replace(before, after);
}
await writeFile(titlePath, titleSource);
