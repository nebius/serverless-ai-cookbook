// Bounded opt-in live chat/tool-format probe. No scientific tools are executed.
// NEBIUS_API_KEY=... node probe-chat-models.mjs <rendered-config.json>
import { readFile } from 'node:fs/promises';
if (!process.env.NEBIUS_API_KEY) throw new Error('NEBIUS_API_KEY is required');
const config = JSON.parse(await readFile(process.argv[2], 'utf8'));
const models = config.endpoints.custom.find((entry) => entry.name === 'Nebius Token Factory').models.default;
const queue = [...models];
const results = [];
await Promise.all(Array.from({ length: 4 }, async () => {
  while (queue.length) {
    const model = queue.shift();
    try {
      const response = await fetch('https://api.tokenfactory.nebius.com/v1/chat/completions', {
        method: 'POST', headers: { Authorization: `Bearer ${process.env.NEBIUS_API_KEY}`, 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(45000),
        body: JSON.stringify({ model, max_tokens: 512, messages: [
          { role: 'user', content: 'Call scientific_echo with text "ready". This is a tool-format test. Do not answer in prose.' },
        ], tools: [{ type: 'function', function: { name: 'scientific_echo',
          description: 'Echo a synthetic test string. No external effects.',
          parameters: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] },
        } }], tool_choice: 'auto' }),
      });
      const body = await response.json();
      const message = body.choices?.[0]?.message;
      results.push({ model, status: response.status,
        toolCall: message?.tool_calls?.some((call) => call.function?.name === 'scientific_echo') ?? false,
        finishReason: body.choices?.[0]?.finish_reason ?? null,
        errorType: body.error?.type ?? null,
      });
    } catch (error) {
      results.push({ model, status: null, errorType: error.name });
    }
  }
}));
process.stdout.write(JSON.stringify(results, null, 2) + '\n');
