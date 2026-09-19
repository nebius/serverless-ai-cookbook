// A confirmed durable admission is a lifecycle fact, not a scientific result.
// Only the immediately completed, single-call batch can end this chat turn.
const toolName = 'run_scientific_workflow_mcp_environment-execution';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const messageType = (message) => message?.getType?.() ?? message?._getType?.();

function studyAdmissionAcknowledgement(messages) {
  if (!Array.isArray(messages) || messages.length < 2) return null;
  const result = messages.at(-1);
  const request = messages.at(-2);
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
