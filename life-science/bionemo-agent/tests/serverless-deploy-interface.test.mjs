import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { chmod, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import test from "node:test";

const execFileAsync = promisify(execFile);
const scriptPath = new URL("../scripts/run_serverless_endpoint.sh", import.meta.url);

async function fakeCli() {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-deploy-interface-"));
  const bin = path.join(root, "bin");
  const capture = path.join(root, "nebius-args.txt");
  await import("node:fs/promises").then(({ mkdir }) => mkdir(bin, { mode: 0o700 }));
  const crane = path.join(bin, "crane");
  const nebius = path.join(bin, "nebius");
  await writeFile(crane, "#!/bin/sh\nprintf '%s\\n' 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'\n", { mode: 0o700 });
  await writeFile(nebius, `#!/bin/sh
if [ "\${1:-}" = vpc ] && [ "\${2:-}" = subnet ] && [ "\${3:-}" = get ]; then
  if [ "\${BIONEMO_TEST_SUBNET_FAIL:-0}" = 1 ]; then exit 17; fi
  printf '%s\\n' "\${BIONEMO_TEST_SUBNET_PARENT:-project-e00testparent}"
  exit 0
fi
printf '%s\\n' "$@" > "$BIONEMO_TEST_CAPTURE"
`, { mode: 0o700 });
  await chmod(crane, 0o700);
  await chmod(nebius, 0o700);
  return { root, bin, capture };
}

function argumentValues(lines, flag) {
  const values = [];
  for (let index = 0; index < lines.length - 1; index += 1) {
    if (lines[index] === flag) values.push(lines[index + 1]);
  }
  return values;
}

test("Serverless deployment exposes only a role and credential selectors", async () => {
  const source = await readFile(scriptPath, "utf8");
  for (const obsolete of [
    "PROFILE", "PARENT_ID", "PLATFORM", "PRESET", "DISK_SIZE",
    "BIONEMO_PUBLIC_ORIGIN", "AGENT_MODEL", "REGISTRY_SECRET",
    "AGENT_PROVIDER", "BIONEMO_BACKEND", "BIONEMO_MCP_URL",
    "BIONEMO_ENABLE_HTTPS_TUNNEL", "BIONEMO_REQUIRE_DEVICE_PAIRING",
    "NVIDIA_API_KEY_SECRET", "NGC_API_KEY_SECRET", "NEBIUS_API_KEY_SECRET",
    "BIONEMO_MCP_API_KEY_SECRET", "OPENAI_API_KEY_SECRET", "ANTHROPIC_API_KEY_SECRET",
  ]) assert.equal(source.includes(obsolete), false, `${obsolete} must not be a deployment input`);
  assert.match(source, /Usage: \$0 nvidia\|tokenfactory/u);
  assert.match(source, /MODEL_CREDENTIALS_SECRET/u);
  assert.match(source, /TAVILY_SECRET/u);
  assert.match(source, /--container-port 18789/u);
  assert.doesNotMatch(source, /--public|--auth|--token-secret/u);
});

test("invalid roles and missing selectors fail before invoking a cloud command", async () => {
  const fixture = await fakeCli();
  try {
    const cases = [
      { args: [], env: {} },
      { args: ["other"], env: { AUTH_TOKEN_SECRET: "auth", MODEL_CREDENTIALS_SECRET: "model" } },
      { args: ["nvidia"], env: { MODEL_CREDENTIALS_SECRET: "model" } },
      { args: ["tokenfactory"], env: { AUTH_TOKEN_SECRET: "auth" } },
    ];
    for (const value of cases) {
      await assert.rejects(() => execFileAsync(scriptPath.pathname, value.args, {
        env: {
          PATH: `${fixture.bin}:/usr/bin:/bin`,
          BIONEMO_TEST_CAPTURE: fixture.capture,
          ...value.env,
        },
      }));
      await assert.rejects(() => readFile(fixture.capture, "utf8"));
    }
  } finally {
    await rm(fixture.root, { recursive: true, force: true });
  }
});

test("NVIDIA role derives every fixed runtime setting and pins the friendly image tag", async () => {
  const fixture = await fakeCli();
  try {
    const { stdout } = await execFileAsync(scriptPath.pathname, ["nvidia"], {
      env: {
        PATH: `${fixture.bin}:/usr/bin:/bin`,
        BIONEMO_TEST_CAPTURE: fixture.capture,
        AUTH_TOKEN_SECRET: "auth-selector",
        MODEL_CREDENTIALS_SECRET: "nvidia-selector",
        TAVILY_SECRET: "tavily-selector",
        SUBNET_ID: "subnet-id",
        ENDPOINT_NAME: "nvidia-demo",
      },
    });
    const lines = (await readFile(fixture.capture, "utf8")).trim().split("\n");
    assert.deepEqual(lines.slice(0, 3), ["ai", "endpoint", "create"]);
    assert.deepEqual(argumentValues(lines, "--image"), ["cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/ba@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]);
    assert.deepEqual(argumentValues(lines, "--env-secret"), [
      "AUTH_TOKEN=auth-selector",
      "NVIDIA_API_KEY=nvidia-selector",
      "TAVILY_API_KEY=tavily-selector",
    ]);
    assert.deepEqual(argumentValues(lines, "--env"), [
      "BIONEMO_HTTPS_MODE=nebius",
    ]);
    assert.deepEqual(argumentValues(lines, "--parent-id"), ["project-e00testparent"]);
    assert.deepEqual(argumentValues(lines, "--subnet-id"), ["subnet-id"]);
    assert.match(stdout, /get-by-name --name "nvidia-demo" --parent-id "project-e00testparent"/u);
    assert.match(stdout, /nebius ai endpoint get "\$ENDPOINT_ID"/u);
    assert.equal(stdout.includes("\\$ENDPOINT_ID"), false);
  } finally {
    await rm(fixture.root, { recursive: true, force: true });
  }
});

test("Token Factory role maps one combined provider secret to reasoning and MCP", async () => {
  const fixture = await fakeCli();
  try {
    const digest = "cr.eu-north1.nebius.cloud/example/ba@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const { stdout } = await execFileAsync(scriptPath.pathname, ["tokenfactory"], {
      env: {
        PATH: `${fixture.bin}:/usr/bin:/bin`,
        BIONEMO_TEST_CAPTURE: fixture.capture,
        AUTH_TOKEN_SECRET: "auth-selector",
        MODEL_CREDENTIALS_SECRET: "combined-selector",
        IMAGE: digest,
      },
    });
    const lines = (await readFile(fixture.capture, "utf8")).trim().split("\n");
    assert.deepEqual(argumentValues(lines, "--image"), [digest]);
    assert.deepEqual(argumentValues(lines, "--env-secret"), [
      "AUTH_TOKEN=auth-selector",
      "NEBIUS_API_KEY=combined-selector",
      "BIONEMO_MCP_API_KEY=combined-selector",
    ]);
    assert.deepEqual(argumentValues(lines, "--env"), ["BIONEMO_HTTPS_MODE=nebius"]);
    assert.deepEqual(argumentValues(lines, "--parent-id"), []);
    assert.deepEqual(argumentValues(lines, "--subnet-id"), []);
    assert.equal(stdout.includes("--parent-id"), false);
  } finally {
    await rm(fixture.root, { recursive: true, force: true });
  }
});

test("invalid subnet metadata fails before endpoint creation", async () => {
  for (const extraEnv of [
    { BIONEMO_TEST_SUBNET_FAIL: "1" },
    { BIONEMO_TEST_SUBNET_PARENT: "folder-wrong-parent" },
  ]) {
    const fixture = await fakeCli();
    try {
      await assert.rejects(() => execFileAsync(scriptPath.pathname, ["nvidia"], {
        env: {
          PATH: `${fixture.bin}:/usr/bin:/bin`,
          BIONEMO_TEST_CAPTURE: fixture.capture,
          AUTH_TOKEN_SECRET: "auth-selector",
          MODEL_CREDENTIALS_SECRET: "nvidia-selector",
          IMAGE: "cr.eu-north1.nebius.cloud/example/ba@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
          SUBNET_ID: "subnet-id",
          ...extraEnv,
        },
      }));
      await assert.rejects(() => readFile(fixture.capture, "utf8"));
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  }
});
