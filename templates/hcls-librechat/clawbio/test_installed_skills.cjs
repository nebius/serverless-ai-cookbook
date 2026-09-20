/* Run inside the candidate image: actual LibreChat deployment-skill loader. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const appRequire = createRequire('/app/package.json');
const { loadDeploymentSkillsFromDirectory } = appRequire('@librechat/api');

(async () => {
  const manifest = JSON.parse(fs.readFileSync('/opt/clawbio/manifest.json', 'utf8'));
  const registry = await loadDeploymentSkillsFromDirectory('/app/skill', {
    projectRoot: '/app', explicitlyConfigured: true,
  });
  const ids = registry.ids();
  for (const name of Object.keys(manifest.skills)) {
    const skill = registry.getByName(`clawbio-${name}`, ids);
    assert.ok(skill, `Skill not discoverable: ${name}`);
    assert.ok(skill.body.includes('Deployment instructions below override'));
    assert.ok(registry.getFileByPath(skill._id, 'references/upstream.md'));
  }
  assert.ok(registry.getByName('clawbio-catalog', ids).body.includes('no separate ClawBio MCP'));
  const core = JSON.parse(fs.readFileSync('/app/skill/manifest.json', 'utf8'));
  for (const name of Object.keys(core.skills)) {
    assert.ok(registry.getByName(name, ids), `Existing skill missing: ${name}`);
  }
  assert.equal(ids.length, Object.keys(core.skills).length + Object.keys(manifest.skills).length);
  const result = { total_discovered: ids.length, clawbio_skills: Object.keys(manifest.skills).length,
    references_loaded: true, existing_skill_checks: true, database_or_provider_calls: 0 };
  if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result));
})().catch(error => { console.error(error); process.exitCode = 1; });
