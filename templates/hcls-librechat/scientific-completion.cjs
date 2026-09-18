// A reasoning-only response is not a completed customer-facing answer.
// Do not infer the provider's finish reason or resubmit an existing operation.
module.exports = function markIncompleteAnswer(response) {
  const parts = Array.isArray(response?.content) ? response.content : [];
  const hasVisiblePart = [...parts].reverse().some((part, index, reversed) => {
    // A progress sentence before the last tool/thinking block is not the final
    // answer. Preserve it, but show interruption when nothing follows it.
    if (reversed.slice(0, index).some((later) => ['think', 'tool_call'].includes(later.type))) return false;
    if (part.type === 'text') return Boolean(String(part.text ?? '').trim());
    if (part.type === 'error') return Boolean(part.error);
    return ['image_file', 'image_url', 'audio', 'artifact', 'file'].includes(part.type);
  });
  if (hasVisiblePart || (!parts.length && String(response?.text ?? '').trim())) return false;
  response.content = [...parts, { type: 'error', error:
    'This turn ended without a usable answer. It is incomplete. Any submitted jobs may still be running: open Runs to recover their status and operation IDs, and ask to resume the existing work. Do not submit the same jobs again.' }];
  return true;
};
