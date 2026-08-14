import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { configureOpenClaw } from "../runtime/runtime-config.mjs";

const root = new URL("../", import.meta.url);

test("ClawBio is source-pinned, license-filtered, and copied only to terminal-capable skill roots", async () => {
  const [dockerfile, sanitizer, wrapper, templateText, router] = await Promise.all([
    readFile(new URL("Dockerfile", root), "utf8"),
    readFile(new URL("runtime/prepare-clawbio.py", root), "utf8"),
    readFile(new URL("runtime/clawbio-mcp.py", root), "utf8"),
    readFile(new URL("config/openclaw.template.json", root), "utf8"),
    readFile(new URL("workspace/skills/clawbio-catalog/SKILL.md", root), "utf8"),
  ]);
  const template = JSON.parse(templateText);

  assert.match(dockerfile, /CLAWBIO_COMMIT="794dd1f5aacc1af308694c9b2f7966d0e396916e"/u);
  assert.match(dockerfile, /CLAWBIO_ARCHIVE_SHA256="207978ebea5d940242f8f0e2708ef768ac976bf04e161e68c6556c91f215e5a0"/u);
  assert.match(dockerfile, /UV_IMAGE="ghcr\.io\/astral-sh\/uv:0\.11\.7@sha256:240fb85a/u);
  assert.match(dockerfile, /rdkit-2025\.9\.6-cp311-cp311-manylinux_2_28_x86_64\.whl/u);
  assert.match(dockerfile, /RDKIT_WHEEL_SHA256="3f4fc084890efb29b51ea4679bb07d28b276b6e73e3381e678a5ba057b4c4222"/u);
  assert.match(dockerfile, /io\.nebius\.rdkit\.version="\$\{RDKIT_VERSION\}"/u);
  assert.match(dockerfile, /uv pip install --python \/opt\/clawbio\/bin\/python --no-deps \/tmp\/rdkit-2025\.9\.6-cp311-cp311-manylinux_2_28_x86_64\.whl/u);
  assert.match(dockerfile, /ligand-embeddability\.py --self-test/u);
  assert.match(dockerfile, /rdkit-LICENSE/u);
  assert.match(dockerfile, /rm -rf[^\n]+\\\n\s+&& chmod -R a-w \/opt\/clawbio/u);
  assert.doesNotMatch(dockerfile, /COPY --from=clawbio-builder[\s\S]+chmod -R a-w \/opt\/clawbio/u);
  assert.match(dockerfile, /uv sync[\s\S]+--frozen[\s\S]+--extra mcp[\s\S]+--no-editable/u);
  assert.match(dockerfile, /cp -a "\$\{skill\}" \/etc\/codex\/skills\//u);
  assert.match(dockerfile, /cp -a "\$\{skill\}" \/home\/node\/\.claude\/skills\//u);
  assert.match(dockerfile, /find \/etc\/codex\/skills[^\n]+wc -l\)" -eq 127/u);
  assert.match(dockerfile, /find \/home\/node\/\.claude\/skills[^\n]+wc -l\)" -eq 127/u);
  assert.doesNotMatch(dockerfile, /cp -a[^\n]+clawbio[^\n]+\/workspace\/agent\/skills/u);

  assert.match(sanitizer, /EXPECTED_UPSTREAM_SKILLS = 97/u);
  assert.match(sanitizer, /EXPECTED_DISTRIBUTED_SKILLS = 95/u);
  assert.match(sanitizer, /"wes-clinical-report-en", "wes-clinical-report-es"/u);
  assert.match(sanitizer, /genome-compare\/data\/manuel_ancestry\.json/u);
  assert.match(sanitizer, /symbolic links are not allowed/u);
  assert.match(sanitizer, /65_536/u);

  assert.equal(template.agents.defaults.skills.at(-1), "clawbio-catalog");
  assert.deepEqual(template.agents.defaults.skills, template.agents.list[0].skills);
  assert.equal(template.agents.defaults.skills.length, 15);
  assert.ok(template.skills.limits.maxSkillsInPrompt >= template.agents.defaults.skills.length);
  assert.match(router, /demo_runnable_in_image/u);
  assert.match(router, /cannot use it to inspect patient or customer files/u);
  assert.match(wrapper, /Only explicit ClawBio demo runs are enabled/u);
  assert.match(wrapper, /def list_skills\(/u);
  assert.match(wrapper, /def describe_skill\(/u);
  assert.match(wrapper, /def run_skill\(/u);
  assert.match(wrapper, /"exit_code": result\.get\("exit_code"\)/u);
  assert.doesNotMatch(wrapper, /"returncode": result\.get\("returncode"\)/u);
  assert.doesNotMatch(wrapper, /def clawbio_(?:list|describe|run)_skill/u);
  assert.match(router, /`clawbio__list_skills`/u);
  assert.match(router, /`clawbio__describe_skill`/u);
  assert.match(router, /`clawbio__run_skill`/u);
  assert.doesNotMatch(wrapper, /CLAWBIO_MCP_ALLOW_LOCAL_FILES/u);
});

test("every OpenClaw role gets only the hardened local three-tool ClawBio MCP surface", () => {
  for (const env of [
    {},
    { NVIDIA_API_KEY: "test" },
    { NEBIUS_API_KEY: "test", BIONEMO_MCP_API_KEY: "test" },
    { OPENAI_API_KEY: "test" },
    { ANTHROPIC_API_KEY: "test" },
  ]) {
    const config = { agents: { defaults: { model: {} } }, models: {}, tools: { alsoAllow: [], deny: ["bundle-mcp"] } };
    configureOpenClaw(config, env);
    assert.deepEqual(config.mcp.servers.clawbio, {
      command: "/opt/clawbio/bin/python",
      args: ["/opt/bionemo/runtime/clawbio-mcp.py"],
      cwd: "/workspace/agent/artifacts/clawbio",
      transport: "stdio",
      timeout: 300,
      toolFilter: { include: ["list_skills", "describe_skill", "run_skill"] },
    });
    assert.ok(config.tools.alsoAllow.includes("bundle-mcp"));
    assert.equal(config.tools.deny.includes("bundle-mcp"), false);
  }
});
