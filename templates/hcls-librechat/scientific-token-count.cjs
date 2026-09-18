// Bound each tokenizer call to the upstream 4 KiB UTF-16 window. Long schemas
// must not become one token per byte just because they exceed that window.
// Chunk boundaries can change BPE merges; include an explicit allowance and
// retain the conservative byte bound if the tokenizer is unavailable or fails.
module.exports = function countBoundedText(text, tokenizer) {
  if (!tokenizer) return Buffer.byteLength(text, 'utf8');
  let total = 0;
  let chunks = 0;
  try {
    for (let start = 0; start < text.length;) {
      let end = Math.min(start + 4096, text.length);
      if (end < text.length && text.charCodeAt(end - 1) >= 0xd800 && text.charCodeAt(end - 1) <= 0xdbff) end--;
      total += tokenizer.count(text.slice(start, end));
      chunks++;
      start = end;
    }
    return Math.min(Buffer.byteLength(text, 'utf8'), Math.ceil(total * 1.05) + 16 * Math.max(0, chunks - 1));
  } catch {
    return Buffer.byteLength(text, 'utf8');
  }
};
