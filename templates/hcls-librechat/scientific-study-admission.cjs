// A confirmed durable admission is a lifecycle fact, not a scientific result.
// Only the immediately completed, single-call batch can end this chat turn.
const toolName = 'run_scientific_workflow_mcp_environment-execution';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const messageType = (message) => message?.getType?.() ?? message?._getType?.();

function isHostBudgetNotice(message) {
  const metadata = message?.additional_kwargs;
  const provenance = metadata?.provenance;
  const parts = provenance?.parts;
  return messageType(message) === 'human' && metadata?.role === 'system' &&
    metadata.source === 'scientific-step-budget' && metadata.injected === true && metadata.isMeta === true &&
    provenance?.version === 1 && Array.isArray(parts) && parts.length === 1 &&
    parts[0]?.attribution === 'synthetic' &&
    parts[0]?.sourceMessageId === undefined &&
    metadata.sourceMessageId === undefined && metadata.sourceMessageIds === undefined;
}

function studyAdmissionAcknowledgement(messages) {
  if (!Array.isArray(messages) || messages.length < 2) return null;
  // ToolNode appends the host's near-budget notice after the completed tool.
  // Only that explicitly stamped synthetic notice is transparent. Never scan
  // past a user/steering message, another tool, or an arbitrary text lookalike.
  const end = messages.length - (isHostBudgetNotice(messages.at(-1)) ? 1 : 0);
  const result = messages[end - 1];
  const request = messages[end - 2];
  if (messageType(result) !== 'tool' || messageType(request) !== 'ai' ||
      result.name !== toolName || result.status === 'error') return null;
  const calls = request.tool_calls;
  if (!Array.isArray(calls) || calls.length !== 1 || calls[0].name !== toolName ||
      !calls[0].id || calls[0].id !== result.tool_call_id) return null;
  let content = result.content;
  if (Array.isArray(content)) {
    if (content.length !== 1 || content[0]?.type !== 'text') return null;
    content = content[0].text;
  }
  if (typeof content !== 'string') return null;
  let receipt;
  try { receipt = JSON.parse(content); } catch { return null; }
  if (!receipt || Array.isArray(receipt) || receipt.durable_study !== true ||
      receipt.study_admission !== 'accepted' || !uuid.test(receipt.id ?? '') ||
      receipt.job_id !== receipt.id || receipt.status !== 'running' ||
      !['queued', 'running', 'publishing'].includes(receipt.state) ||
      receipt.isError || receipt.error || receipt.failure || receipt.cancellation_failure ||
      receipt.admission_unknown || receipt.cancellation_unknown || receipt.queue_blocked) return null;
  return `Study accepted: \`${receipt.id}\`. Observed state: **${receipt.state}**.\n\n` +
    'The saved study continues independently of this chat. Follow progress and verified final files in ' +
    '[Runs → Whole studies](/demos?tab=runs). No continue prompt is needed for mechanical waiting.\n\n' +
    'This acknowledges admission only, not completion or scientific results.';
}

studyAdmissionAcknowledgement.patchBudgetHook = function patchBudgetHook(source) {
  const anchor = 'return { additionalContext: buildBudgetNotice(remaining) };';
  if (source.split(anchor).length !== 2) throw new Error('Unsupported pinned study budget-notice seam');
  // Use the existing injected-message transport so ToolNode retains an exact
  // producer tag and stamps synthetic provenance. Budget, text and timing stay
  // unchanged; no user message is reclassified and no provider turn is added.
  return source.replace(anchor, `return { injectedMessages: [{
\t\t\trole: "system", content: buildBudgetNotice(remaining),
\t\t\tisMeta: true, source: "scientific-step-budget"
\t\t}] };`);
};

// Pinned upstream seam, shared by classic/event-driven tool execution. Keep
// normal message events/persistence, but do not invoke a provider to paraphrase
// the just-confirmed receipt. Unrecognized or uncertain outcomes are untouched.
studyAdmissionAcknowledgement.patchGraph = function patchGraph(source) {
  const anchor = '\t\t\tconst { messages } = state;\n\t\t\tconst discoveredNames = require_tools.extractToolDiscoveries(messages);';
  if (source.split(anchor).length !== 2) throw new Error('Unsupported pinned study admission seam');
  return source.replace(anchor, `\t\t\tconst { messages } = state;
\t\t\tconst studyAdmissionText = require('/opt/hcls-librechat/scientific-study-admission.cjs')(messages);
\t\t\tconst admissionHasPendingTools = [...(this.pendingToolCallsByStep?.values() ?? [])].some((calls) => calls.size > 0);
\t\t\tif (studyAdmissionText !== null && !admissionHasPendingTools) {
\t\t\t\tthis.config = config;
\t\t\t\tconst admissionStepKey = this.getStepKey(config.metadata);
\t\t\t\tconst admissionEmitted = await dispatchTextMessageContent({
\t\t\t\t\tgraph: this, stepKey: admissionStepKey,
\t\t\t\t\tprovider: agentContext.provider, content: [{ type: 'text', text: studyAdmissionText }], metadata: config.metadata
\t\t\t\t});
\t\t\t\tif (!admissionEmitted) throw new Error('Unable to emit the confirmed study admission acknowledgement');
\t\t\t\tconst admissionMessage = new _langchain_core_messages.AIMessage({
\t\t\t\t\tid: this.messageIdsByStepKey.get(admissionStepKey), content: studyAdmissionText,
\t\t\t\t\tresponse_metadata: { scientific_admission_acknowledgement: true }
\t\t\t\t});
\t\t\t\tthis.runProducedAiMessageIds.add(admissionMessage.id);
\t\t\t\treturn { messages: [admissionMessage] };
\t\t\t}
\t\t\tconst discoveredNames = require_tools.extractToolDiscoveries(messages);`);
};

module.exports = studyAdmissionAcknowledgement;
