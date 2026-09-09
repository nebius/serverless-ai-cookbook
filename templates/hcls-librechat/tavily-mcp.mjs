import readline from 'node:readline';

const tools = [{ name: 'tavily_search', description: 'Search current web sources with Tavily. Cite returned source URLs.',
  inputSchema: { type: 'object', additionalProperties: false, properties: {
    query: { type: 'string', minLength: 1, maxLength: 2000 },
    max_results: { type: 'integer', minimum: 1, maximum: 10, default: 5 },
  }, required: ['query'] },
}];
const out = (id, result) => process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
const fail = (id, code, message) => process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n');
const rl = readline.createInterface({ input: process.stdin });
rl.on('line', async (line) => {
  let request;
  try { request = JSON.parse(line); } catch { return fail(null, -32700, 'Invalid JSON'); }
  const { id, method, params } = request;
  if (id === undefined) return; // Notifications do not receive responses.
  if (method === 'initialize') return out(id, { protocolVersion: '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'tavily', version: '1.2' } });
  if (method === 'ping') return out(id, {});
  if (method === 'tools/list') return out(id, { tools });
  if (method !== 'tools/call') return fail(id, -32601, 'Method not found');
  if (params?.name !== 'tavily_search') return fail(id, -32602, 'Unknown tool');
  const args = params.arguments ?? {};
  const count = args.max_results ?? 5;
  if (typeof args.query !== 'string' || !args.query.trim() || args.query.length > 2000 ||
      !Number.isInteger(count) || count < 1 || count > 10) return fail(id, -32602, 'Provide a query and max_results between 1 and 10');
  try {
    if (!process.env.TAVILY_API_KEY) throw new Error('Search is not configured. Ask the workspace operator to connect Tavily.');
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST', signal: AbortSignal.timeout(20000),
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.TAVILY_API_KEY}` },
      body: JSON.stringify({ query: args.query, max_results: count, search_depth: 'basic', include_answer: false }),
    });
    if (!response.ok) throw new Error(`Search provider returned HTTP ${response.status}. No search results were retrieved.`);
    const data = await response.json();
    out(id, { content: [{ type: 'text', text: JSON.stringify({ request_id: data.request_id,
      results: data.results?.map(({ title, url, content, score }) => ({ title, url, content, score })),
    }) }] });
  } catch (error) {
    const message = error.name === 'TimeoutError' ? 'Search timed out after 20 seconds. No results were retrieved; do not invent sources.' :
      error.message.startsWith('Search ') ? error.message : 'Search connection failed. No results were retrieved.';
    out(id, { isError: true, content: [{ type: 'text', text: message }] });
  }
});
