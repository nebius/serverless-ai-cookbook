const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

test('saved hidden result download follows authentication and checked workspace path', async () => {
  const routes = [], middleware = [], reads = [], downloads = [];
  const auth = () => {};
  const service = { workspaceGet: async (key, name) => {
    reads.push({ key, name });
    return { absolute: `/workspace/${name}`, normalized: name };
  } };
  const router = { use: (...args) => middleware.push(...args) };
  for (const verb of ['get', 'post', 'put']) router[verb] = (route, ...handlers) => routes.push({ verb, route, handlers });
  const dependencies = {
    express: { Router: () => router },
    multer: () => ({ single: () => () => {} }),
    '~/server/middleware': { requireJwtAuth: auth },
    '~/server/services/PluginService': { getUserPluginAuthValue: async () => 'fixture-key' },
    '/opt/hcls-librechat/demos/service.cjs': service,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'router.cjs'), 'utf8'), {
    require: (name) => dependencies[name] || require(name), module: { exports: {} },
  });
  assert.equal(middleware[0], auth);
  const route = routes.find((item) => item.verb === 'get' && item.route === '/workspace/file');
  await new Promise((resolve, reject) => {
    route.handlers[0]({ user: { id: 'scientist' }, query: { path: '.scientific-runs/run/result.json' } }, {
      download: (...args) => { downloads.push(args); resolve(); },
    }, reject);
  });
  assert.equal(reads[0].key, 'fixture-key');
  assert.equal(downloads[0][0], '/workspace/.scientific-runs/run/result.json');
  assert.equal(downloads[0][2].dotfiles, 'allow');
  service.workspaceGet = async () => { throw new Error('invalid workspace path'); };
  await assert.rejects(new Promise((resolve, reject) => route.handlers[0](
    { user: { id: 'scientist' }, query: { path: '../outside' } }, { download: resolve }, reject,
  )), /invalid workspace path/);
  assert.equal(downloads.length, 1);
});
