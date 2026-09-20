/* Exercise the real bundled LibreChat deployment-skill loader; no DB or secrets. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const { initializeDeploymentSkills, createDeploymentSkillMethods } = require('/app/packages/api/dist/index.cjs');

async function main() {
  const manifest = JSON.parse(fs.readFileSync('/app/skill/manifest.json', 'utf8'));
  const registry = await initializeDeploymentSkills({
    projectRoot: '/app', env: { DEPLOYMENT_SKILLS_DIR: '/app/skill' },
  });
  const loaded = registry.list();
  assert.deepEqual(loaded.map(x => x.name).sort(), Object.keys(manifest.skills).sort());
  const methods = createDeploymentSkillMethods({});
  let files = 0;
  for (const skill of loaded) {
    assert.ok(skill.body.length && skill.description.length, skill.name);
    assert.equal(skill.disableModelInvocation, undefined, skill.name);
    const retrieved = await methods.getSkillByName(skill.name, registry.ids());
    assert.equal(retrieved.body, skill.body, skill.name);
    for (const file of skill.files) {
      const read = await methods.getSkillFileByPath(skill._id, file.relativePath);
      assert.ok(read, `${skill.name}/${file.relativePath}`);
      if (read.content !== undefined && !read.isBinary) {
        const raw = fs.readFileSync(file.filepath, 'utf8');
        assert.equal(read.content, raw, `${skill.name}/${file.relativePath}`);
      }
      files++;
    }
  }
  const root = JSON.parse(fs.readFileSync('/app/skill/files.sha256.json', 'utf8'));
  for (const [name, expected] of Object.entries(root)) {
    const actual = crypto.createHash('sha256').update(fs.readFileSync(`/app/skill/${name}`)).digest('hex');
    assert.equal(actual, expected, name);
  }
  console.log(JSON.stringify({ status: 'passed', version: manifest.version,
    loader: 'LibreChat initializeDeploymentSkills + getSkillByName/getSkillFileByPath',
    skills: loaded.length, resources: files, verified_files: Object.keys(root).length,
    inference_calls: 0, customer_readiness_claim: false }));
}
main().then(() => process.exit(0)).catch(error => { console.error(error); process.exit(1); });
