const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.TYPESCRIPT_MODULE || 'typescript');
let root;
const originalFetch = global.fetch;
const setup = (async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), 'whole-study-service-'));
  process.env.SCIENTIFIC_WORKSPACE = root;
  process.env.SCIENTIFIC_MODELS_API_KEY = 'dedicated-fixture-key';
  process.env.TEAM_ID = 'fixture-tenant';
  process.env.TEAM_BUCKET_NAME = 'fixture-bucket';
  process.env.SCIENTIFIC_CLIENT_PYTHON = process.execPath;
  process.env.SCIENTIFIC_STUDY_SCRIPT = path.join(root, 'observer.cjs');
  await fs.writeFile(process.env.SCIENTIFIC_STUDY_SCRIPT,
    'process.stdout.write(JSON.stringify({data:[],argv:process.argv.slice(2),engine:{configured:true,alive:true}}));');
  return require('./service.cjs');
})();
after(async () => { global.fetch = originalFetch; if (root) await fs.rm(root, { recursive: true, force: true }); });

test('whole-study observation requires exact dedicated key plus current platform storage permission', async () => {
  const service = await setup;
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push(url); assert.equal(options.headers.Authorization, 'Bearer dedicated-fixture-key');
    return new Response(JSON.stringify({tenant_id:'fixture-tenant',team_bucket_name:'fixture-bucket'}));
  };
  await assert.rejects(service.studies('another-key'), (error) => error.status === 403);
  assert.equal(calls.length, 0);
  const result = await service.studies('dedicated-fixture-key');
  assert.deepEqual(result.argv, ['--list']);
  assert.ok(!JSON.stringify(result).includes('dedicated-fixture-key'));
  assert.equal(calls.length, 1);
  const id = '11111111-2222-4333-8444-555555555555';
  assert.deepEqual((await service.studies('dedicated-fixture-key', 'cancel', id)).argv, ['--cancel', id]);
  await assert.rejects(service.studies('dedicated-fixture-key', 'cancel', '../escape'));
  global.fetch = async () => new Response(JSON.stringify({detail:'revoked'}), {status:403});
  await assert.rejects(service.studies('dedicated-fixture-key'), (error) => error.status === 403);
});

test('Runs renders study phases, unavailable worker warning and verified workspace links separately from model status', async () => {
  const source = await fs.readFile(path.join(__dirname, 'Demos.tsx'), 'utf8');
  const jsx = (type, props) => typeof type === 'function' ? type(props) : {type,props};
  const download = '/demos?tab=workspace&path=study&file=report.md';
  // Exercise the real display helper; an empty mock stopped exercising Runs
  // when the component adopted studyDisplay/runDisplay.
  const display = {exports:{}};
  vm.runInNewContext(ts.transpileModule(await fs.readFile(path.join(__dirname, 'run-display.ts'), 'utf8'), {
    compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
  }).outputText, {module:display,exports:display.exports});
  const dependencies = {
    react:{useState:(value)=>[value,()=>{}],useEffect:()=>{}},
    'react/jsx-runtime':{jsx,jsxs:jsx,Fragment:'fragment'}, axios:{},
    'react-router-dom':{Link:'Link',useSearchParams:()=>[new URLSearchParams('tab=runs'),()=>{}]},
    '@tanstack/react-query':{useQueryClient:()=>({invalidateQueries:async()=>{}}),useQuery:(key)=>({isLoading:false,
      data:key[1]==='settings'?{configured:true}:key[1]==='studies'?{engine:{configured:true,alive:false},data:[{
        id:'study-1',title:'Saved research',state:'completed',phase:'completed',completed_steps:['prepare','model','report'],step_count:3,
        artifacts:[{name:'Verified report',role:'report',size_bytes:42,sha256:'a'.repeat(64),download_url:download}]}]}:{data:[]}})},
    '@librechat/client':{Button:'Button',Input:'Input'},'librechat-data-provider':{request:{}},
    './scientific-comparison':{},'./scientific-run-display':display.exports,
    './ScientificGettingStarted':{default:()=>null},
  };
  const module = {exports:{}};
  vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,
    jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText,
    {module,exports:module.exports,require:(name)=>dependencies[name],URLSearchParams,encodeURIComponent});
  const elements=[];
  function visit(item) { if(Array.isArray(item)) return item.forEach(visit); if(!item||typeof item!=='object') return;
    elements.push(item); visit(item.props?.children); }
  visit(module.exports.default());
  assert.ok(elements.some(item=>item.type==='Link'&&item.props.to===download));
  assert.ok(elements.some(item=>item.props?.role==='status'&&String(item.props.children).includes('supervisor is currently unavailable')));
  assert.equal(elements.filter(item=>item.type==='Button'&&item.props.children==='Cancel remaining study').length,0);
});
