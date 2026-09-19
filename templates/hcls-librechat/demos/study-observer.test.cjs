const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
let root, script, service;
const originalFetch = global.fetch;
before(async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), 'study-observer-diagnostic-'));
  script = path.join(root, 'observer.cjs');
  Object.assign(process.env, {SCIENTIFIC_WORKSPACE:root, SCIENTIFIC_MODELS_API_KEY:'dedicated-fixture-key',
    SCIENTIFIC_CLIENT_PYTHON:process.execPath, SCIENTIFIC_STUDY_SCRIPT:script});
  global.fetch = async () => new Response('{}');
  service = require('./service.cjs');
});
after(async () => { global.fetch = originalFetch; if(root) await fs.rm(root,{recursive:true,force:true}); });

async function rejects(source, code) {
  await fs.writeFile(script,source);
  await assert.rejects(service.studies('dedicated-fixture-key'),error => {
    assert.equal(error.status,503); assert.equal(error.code,code);
    const publicValue = service.publicError(error);
    assert.equal(publicValue.code,code);
    assert(!JSON.stringify(publicValue).includes('private-sentinel'));
    return true;
  });
}
test('strict observer exit retains failure with bounded code, not raw traceback or stdout',async () => {
  await rejects('process.stderr.write("private-sentinel traceback");process.stdout.write("private-sentinel");process.exit(7);','STUDY_OBSERVER_EXIT');
});
test('invalid observer JSON remains an error and cannot become a completed Study',async () => {
  await rejects('process.stdout.write("private-sentinel");','STUDY_OBSERVER_INVALID_RESPONSE');
});
test('existing observation output bound is unchanged and machine-readable',async () => {
  await rejects('process.stdout.write("x".repeat(4*1024*1024+1));','STUDY_OBSERVER_OUTPUT_LIMIT');
});
test('unavailable observer has bounded code without executable path details',async () => {
  process.env.SCIENTIFIC_CLIENT_PYTHON=path.join(root,'private-sentinel-missing-executable');
  try { await rejects('','STUDY_OBSERVER_UNAVAILABLE'); }
  finally { process.env.SCIENTIFIC_CLIENT_PYTHON=process.execPath; }
});
test('successful strict status and current authorization semantics stay unchanged',async () => {
  await fs.writeFile(script,'process.stdout.write(JSON.stringify({data:[],engine:{alive:true}}));');
  assert.deepEqual(await service.studies('dedicated-fixture-key'),{data:[],engine:{alive:true}});
  await assert.rejects(service.studies('other-key'),error=>error.status===403&&!error.code);
  global.fetch=async()=>new Response('{}',{status:403});
  try { await assert.rejects(service.studies('dedicated-fixture-key'),error=>error.status===403); }
  finally { global.fetch=async()=>new Response('{}'); }
});
