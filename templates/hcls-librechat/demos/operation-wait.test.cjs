const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
let root;
const setup = (async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-operation-wait-'));
  process.env.SCIENTIFIC_DEMOS_DIR = root;
  return require('./service.cjs');
})();
after(async () => { await setup; await fs.rm(root, { recursive: true, force: true }); });

async function scenario(response, check, waitSeconds = 30) {
  const service = await setup;
  const originals = { now: Date.now, timeout: global.setTimeout, fetch: global.fetch, signal: AbortSignal.timeout };
  const id = crypto.randomUUID();
  let clock = 0;
  const calls = [];
  Date.now = () => clock;
  global.setTimeout = (callback, milliseconds) => { clock += milliseconds; callback(); };
  AbortSignal.timeout = (milliseconds) => {
    calls.push({ at: clock, budget: milliseconds });
    return originals.signal(milliseconds);
  };
  global.fetch = async (_url, options) => {
    assert.equal(options.method, 'GET');
    return response({ id, calls, advance: (milliseconds) => { clock += milliseconds; } });
  };
  try {
    await check(service.waitOperation('test-owner', 'fixture-key', id, waitSeconds), calls, () => clock);
  } finally {
    Date.now = originals.now;
    global.setTimeout = originals.timeout;
    global.fetch = originals.fetch;
    AbortSignal.timeout = originals.signal;
  }
}
const running = ({ id, advance }) => {
  advance(40);
  return new Response(JSON.stringify({ id, status: 'running' }));
};
test('exact deadline returns saved pending observation without a final 1ms GET', async () => {
  await scenario(running, async (pending, calls, now) => {
    const result = await pending;
    assert.equal(result.status, 'running');
    assert.equal(result.terminal, false);
    assert.equal(result.wait_expired, true);
    assert.equal(now(), 30000);
    assert.equal(calls.length, 10);
    assert.ok(calls.every(({ at, budget }) => at < 30000 && budget > 1 && budget <= 30000));
    assert.equal(result.last_observed_at, result.updated_at);
    assert.equal(result.observations.length, 1);
    assert.match(result.next_step, /not complete/);
  });
});
test('deadline abort in a later status GET retains last valid state explicitly', async () => {
  await scenario((context) => {
    if (context.calls.length === 2) {
      context.advance(context.calls.at(-1).budget);
      throw new DOMException('Observation deadline', 'TimeoutError');
    }
    return running(context);
  }, async (pending) => {
    const result = await pending;
    assert.equal(result.status, 'running');
    assert.equal(result.wait_expired, true);
    assert.equal(result.terminal, false);
    assert.equal(result.observations.length, 1);
  });
});
test('first-read timeout cannot fabricate an operation state', async () => {
  await scenario(({ calls, advance }) => {
    advance(calls.at(-1).budget);
    throw new DOMException('Observation deadline', 'TimeoutError');
  }, async (pending) => { await assert.rejects(pending, (error) => error.status === 503); });
});
for (const status of [401, 403, 404, 500]) {
  test(`HTTP ${status} after a valid observation remains a real error`, async () => {
    await scenario((context) => {
      if (context.calls.length === 1) return running(context);
      context.advance(context.calls.at(-1).budget);
      return new Response(JSON.stringify({ detail: 'Retained backend failure' }), { status });
    }, async (pending) => { await assert.rejects(pending, (error) => error.status === status); });
  });
}
for (const error of [new TypeError('connection interrupted'), new DOMException('Cancelled', 'AbortError')]) {
  test(`${error.name} is not converted to a successful pending observation`, async () => {
    await scenario((context) => {
      if (context.calls.length === 1) return running(context);
      context.advance(context.calls.at(-1).budget);
      throw error;
    }, async (pending) => { await assert.rejects(pending, (failure) => failure.status === 503); });
  });
}
test('cancelled terminal operation returns immediately with no deadline-expired claim', async () => {
  await scenario(({ id }) => new Response(JSON.stringify({ id, status: 'cancelled' })), async (pending, calls) => {
    const result = await pending;
    assert.equal(result.status, 'cancelled');
    assert.equal(result.terminal, true);
    assert.equal(result.wait_expired, false);
    assert.equal(calls.length, 1);
  });
});
test('zero wait remains a single ordinary status read, not a 1ms timeout', async () => {
  await scenario(running, async (pending, calls) => {
    const result = await pending;
    assert.equal(result.wait_expired, false);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].budget, 45000);
  }, 0);
});
