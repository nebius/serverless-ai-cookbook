/* Loaded in LibreChat after its normal authentication middleware is installed. */
const express = require('express');
const multer = require('multer');
const fs = require('node:fs/promises');
const os = require('node:os');
const { requireJwtAuth } = require('~/server/middleware');
const { getUserPluginAuthValue, updateUserPluginAuth } = require('~/server/services/PluginService');
const service = require('/opt/hcls-librechat/demos/service.cjs');
const router = express.Router();
const upload = multer({ dest: os.tmpdir(), limits: { fileSize: 512 * 1024 * 1024, files: 1, fields: 4 } });
const wrap = (handler) => (req, res, next) => Promise.resolve(handler(req, res)).catch(next);
router.use(requireJwtAuth);
router.use((_req, res, next) => { res.set('Cache-Control', 'no-store'); next(); });
router.get('/workshop/example', (_req, res) => res.json(require('/opt/hcls-librechat/demos/workshop-example.json')));
async function key(req) {
  return getUserPluginAuthValue(req.user.id, 'SCIENTIFIC_MODELS_API_KEY', false, 'mcp_scientific-demos');
}
router.get('/settings', wrap(async (req, res) => res.json({ configured: Boolean(await key(req)),
  report_model: service.REPORT_MODEL, private_sword: 'awaiting_event_artifact', provider: 'Nebius Token Factory (global)' })));
router.put('/settings', wrap(async (req, res) => {
  const value = req.body?.api_key;
  if (typeof value !== 'string' || value.length > 4096) throw service.failure('Supply a platform API key.');
  await service.platform(value, 'GET', '/v1/models');
  const saved = await updateUserPluginAuth(req.user.id, 'SCIENTIFIC_MODELS_API_KEY', 'mcp_scientific-demos', value);
  if (saved instanceof Error) throw service.failure('Could not save the key.', 503);
  res.json({ configured: true });
}));
router.get('/apps', wrap(async (req, res) => {
  const credential = await key(req);
  const [models, scientific] = await Promise.all([
    service.platform(credential, 'GET', '/v1/models'),
    service.platform(credential, 'GET', '/v1/scientific-models'),
  ]);
  const native = new Map((models.data || []).map((item) => [item.id || item.model_id, item]));
  const batches = new Map((scientific.data || []).map((item) => [item.model_id || item.id, item]));
  const ids = [...new Set([...native.keys(), ...batches.keys()])].sort();
  res.json({ data: ids.map((id) => ({ id, native: native.get(id), scientific: batches.get(id) })) });
}));
router.get('/runs', wrap(async (req, res) => res.json(await service.runs(req.user.id, await key(req), {
  cursor: req.query.cursor, limit: req.query.limit === undefined ? 50 : Number(req.query.limit),
}))));
router.post('/runs', wrap(async (req, res) => res.status(201).json(await service.track(req.user.id, await key(req), req.body?.operation_id, {
  label: req.body?.label, model_id: req.body?.model_id, source: 'panel',
}))));
router.get('/runs/:id', wrap(async (req, res) => res.json(await service.track(req.user.id, await key(req), req.params.id, { source: 'panel' }))));
router.get('/runs/:id/result', wrap(async (req, res) => res.json(await service.operationResult(await key(req), req.params.id))));
router.post('/runs/:id/cancel', wrap(async (req, res) => res.json(await service.platform(await key(req), 'POST', `/v1/operations/${req.params.id}:cancel`))));
router.get('/workspace', wrap(async (req, res) => res.json(await service.workspaceList(await key(req), req.query.path || ''))));
router.post('/workspace', upload.single('file'), wrap(async (req, res) => {
  if (!req.file) throw service.failure('Attach one file.');
  try {
    const name = req.body.path || req.file.originalname;
    res.status(201).json(await service.workspacePut(await key(req), name, req.file.path));
  } finally { await fs.unlink(req.file.path).catch(() => {}); }
}));
router.get('/workspace/file', wrap(async (req, res) => {
  const value = await service.workspaceGet(await key(req), req.query.path || '');
  res.download(value.absolute, value.normalized);
}));
router.get('/clinical', wrap(async (req, res) => res.json({ data: await service.list(req.user.id) })));
router.post('/clinical', upload.single('file'), wrap(async (req, res) => {
  if (!req.file) throw service.failure('Attach an audio or transcript file.');
  try {
    const job = await service.clinical(req.user.id, await key(req), { kind: req.body.kind,
      language: req.body.language, idempotency_key: req.body.idempotency_key,
      filename: req.file.originalname, local_path: req.file.path });
    res.status(202).json(job);
  } finally { await fs.unlink(req.file.path).catch(() => {}); }
}));
router.get('/clinical/:id', wrap(async (req, res) => res.json(await service.status(req.user.id, req.params.id))));
router.post('/clinical/:id/resume', wrap(async (req, res) => res.json(await service.start(req.user.id, await key(req), req.params.id))));
router.get('/clinical/:id/files/:name', wrap(async (req, res) => {
  const bytes = await service.output(req.user.id, req.params.id, req.params.name);
  res.type(req.params.name.endsWith('.json') ? 'application/json' : 'text/plain').attachment(req.params.name).send(bytes);
}));
router.get('/workshop/catalog', wrap(async (req, res) => res.json(await service.platform(await key(req), 'GET', '/v1/workshop/catalog'))));
router.get('/workshop/runs', wrap(async (req, res) => res.json(await service.platform(await key(req), 'GET', '/v1/workshop/runs'))));
router.post('/workshop/runs', wrap(async (req, res) => res.status(202).json(await service.platform(await key(req), 'POST', '/v1/workshop/runs', req.body, req.get('Idempotency-Key')))));
router.get('/workshop/runs/:id', wrap(async (req, res) => res.json(await service.platform(await key(req), 'GET', `/v1/workshop/runs/${req.params.id}`))));
router.get('/workshop/runs/:id/report', wrap(async (req, res) => res.json(await service.platform(await key(req), 'GET', `/v1/workshop/runs/${req.params.id}/report`))));
router.post('/workshop/runs/:id/interventions', wrap(async (req, res) => res.json(await service.platform(await key(req), 'POST', `/v1/workshop/runs/${req.params.id}/interventions`, req.body))));
router.use((error, _req, res, _next) => {
  const status = error.code === 'LIMIT_FILE_SIZE' ? 413 : error.status || 500;
  res.status(status).json(service.publicError(Object.assign(error, { status })));
});
module.exports = router;
