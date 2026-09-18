import { readFile, writeFile } from 'node:fs/promises';
const path = '/app/api/server/services/ToolService.js';
let source = await readFile(path, 'utf8');
const anchor = '  const filteredTools = agent.tools?.filter((tool) => {';
if (!source.includes(anchor)) throw new Error('Unsupported pinned ToolService');
// Cover both the event-driven and classic tool-loading paths.
for (const property of ['toolOptions', 'agentToolOptions']) {
  const before = `${property}: agent.tool_options,`;
  if (!source.includes(before)) throw new Error(`Unsupported tool options: ${property}`);
  source = source.replaceAll(before, `${property}: require('/opt/hcls-librechat/scientific-tool-options.cjs')(agent, typeof loadedTools === 'undefined' ? [] : loadedTools),`);
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

// Preserve normal FINAL persistence ordering, but do not publish a blank
// reasoning/tool-only response as successfully completed.
const requestPath = '/app/api/server/controllers/agents/request.js';
let requestSource = await readFile(requestPath, 'utf8');
const completionAnchor = 'const responseIsUnfinished = terminalWasAborted || preemptIncomplete || stepLimitReached;';
if (!requestSource.includes(completionAnchor)) throw new Error('Unsupported pinned completion controller');
requestSource = requestSource.replace(completionAnchor, `const missingFinalAnswer =
          !terminalWasAborted && !preemptIncomplete && !stepLimitReached &&
          require('/opt/hcls-librechat/scientific-completion.cjs')(response);
        const responseIsUnfinished = terminalWasAborted || preemptIncomplete || stepLimitReached || missingFinalAnswer;`);
await writeFile(requestPath, requestSource);

const graphPath = '/app/node_modules/@librechat/agents/dist/cjs/graphs/Graph.cjs';
let graphSource = await readFile(graphPath, 'utf8');
const auditAnchor = 'const usageBreakdown = agentContext.getTokenBudgetBreakdown(messages);';
if (!graphSource.includes(auditAnchor)) throw new Error('Unsupported pinned context diagnostics');
graphSource = graphSource.replace(auditAnchor,
  `require('/opt/hcls-librechat/scientific-context-audit.cjs')(agentContext);\n\t\t\t\t${auditAnchor}`);
const responseAuditAnchor = 'const responseMessage = result.messages?.[0];';
if (!graphSource.includes(responseAuditAnchor)) throw new Error('Unsupported pinned provider diagnostics');
graphSource = graphSource.replace(responseAuditAnchor,
  `${responseAuditAnchor}\n\t\t\trequire('/opt/hcls-librechat/scientific-context-audit.cjs').response(responseMessage, agentContext);`);
await writeFile(graphPath, graphSource);

const apiPath = '/app/packages/api/dist/index.cjs';
let apiSource = await readFile(apiPath, 'utf8');
const exactCounterAnchor = 'if (requiresTokenEstimate(text)) return estimateBoundedTokenCount(text);';
if (apiSource.split(exactCounterAnchor).length !== 3) throw new Error('Unsupported pinned tokenizer');
apiSource = apiSource.replace(exactCounterAnchor,
  "if (requiresTokenEstimate(text)) return require('/opt/hcls-librechat/scientific-token-count.cjs')(text, tokenizer);");
const synchronousCounterAnchor = `getTokenCount(text, encoding = "o200k_base") {
\t\tif (requiresTokenEstimate(text)) return estimateBoundedTokenCount(text);
\t\tconst tokenizer = this.tokenizersCache[encoding];`;
if (!apiSource.includes(synchronousCounterAnchor)) throw new Error('Unsupported pinned synchronous tokenizer');
apiSource = apiSource.replace(synchronousCounterAnchor, `getTokenCount(text, encoding = "o200k_base") {
\t\tconst tokenizer = this.tokenizersCache[encoding];
\t\tif (requiresTokenEstimate(text)) return require('/opt/hcls-librechat/scientific-token-count.cjs')(text, tokenizer);`);
await writeFile(apiPath, apiSource);
