import { ArtifactStore } from "./src/artifacts.mjs";
import { NimClient } from "./src/client.mjs";
import { PUBLIC_CATALOG, SKILLS, TOOLKIT_COMMIT, WORKFLOWS } from "./src/catalog.mjs";
import { publicError } from "./src/errors.mjs";
import { resolveSkillInput, resolveWorkflowInput } from "./src/samples.mjs";
import { createUiHandlers } from "./src/ui.mjs";
import { JSON_SCHEMAS, VALIDATORS } from "./src/validation.mjs";
import { WorkflowRunner } from "./src/workflows.mjs";

export const PLUGIN_VERSION = "3.1.0";

function summaryForSkill(skillId, input) {
  const summary = { requestBytes: Buffer.byteLength(JSON.stringify(input), "utf8") };
  if (typeof input.sequence === "string") summary.sequenceLength = input.sequence.length;
  if (typeof input.input_pdb === "string") summary.pdbBytes = Buffer.byteLength(input.input_pdb);
  if (typeof input.protein === "string") summary.proteinPdbBytes = Buffer.byteLength(input.protein);
  if (Array.isArray(input.polymers)) summary.polymerCount = input.polymers.length;
  if (Array.isArray(input.ligands)) summary.ligandCount = input.ligands.length;
  return summary;
}

function toolResult(value) {
  const text = JSON.stringify({
    status: "completed",
    runId: value.runId,
    summary: value.summary,
    artifacts: value.artifacts,
    caveat: "Research use only. Review confidence and validate experimentally; this is not clinical advice.",
  }, null, 2);
  return { content: [{ type: "text", text }], structuredContent: value };
}

export function createRuntime({ fetchImpl = globalThis.fetch, env = process.env, artifactRoot, logger = console } = {}) {
  const store = new ArtifactStore(artifactRoot || env.BIONEMO_ARTIFACT_ROOT || "/workspace/agent/artifacts");
  const client = new NimClient({ fetchImpl, env, logger });

  async function runSkill(skillId, rawInput) {
    const input = VALIDATORS[skillId](await resolveSkillInput(skillId, rawInput));
    const run = await store.createRun({ kind: "skill", id: skillId, inputSummary: summaryForSkill(skillId, input) });
    try {
      const result = await client.call(skillId, input);
      await store.saveNimResult(run, result);
      await store.complete(run, { steps: [{ label: SKILLS[skillId].label, skillId, status: "completed", elapsedMs: result.elapsedMs }] });
      return {
        runId: run.runId,
        summary: { skill: SKILLS[skillId].label, elapsedMs: result.elapsedMs, requestId: result.requestId, responseKeys: Object.keys(result.data).slice(0, 50) },
        artifacts: store.presentArtifacts(run),
      };
    } catch (error) {
      const safe = publicError(error);
      await store.complete(run, { status: "failed", error: safe });
      throw Object.assign(new Error(`${safe.code}: ${safe.message}`), { code: safe.code, status: safe.status });
    }
  }

  const workflowRunner = new WorkflowRunner({ client, store, onProgress: async () => {} });
  async function runWorkflow(workflowId, rawInput) {
    try { return await workflowRunner.run(workflowId, await resolveWorkflowInput(workflowId, rawInput)); }
    catch (error) {
      const safe = publicError(error);
      throw Object.assign(new Error(`${safe.code}: ${safe.message}`), { code: safe.code, status: safe.status });
    }
  }
  return { store, client, runSkill, runWorkflow };
}

export default {
  id: "bionemo-agent-toolkit",
  name: "BioNeMo Agent Toolkit",
  description: "Bounded NVIDIA hosted-NIM adapters plus a preconfigured remote BioNeMo MCP gateway.",
  version: PLUGIN_VERSION,
  register(api) {
    const runtime = createRuntime({ logger: api.logger });
    for (const definition of Object.values(SKILLS)) {
      api.registerTool({
        name: definition.tool,
        label: definition.label,
        description: `${definition.description} NVIDIA-hosted route only; research use only.`,
        parameters: JSON_SCHEMAS[definition.id],
        async execute(_toolCallId, params) { return toolResult(await runtime.runSkill(definition.id, params)); },
      });
    }
    for (const definition of Object.values(WORKFLOWS)) {
      api.registerTool({
        name: definition.tool,
        label: definition.label,
        description: `${definition.description} Bounded event-sized hosted NIM calls only; research use only.`,
        parameters: JSON_SCHEMAS[definition.id],
        async execute(_toolCallId, params) { return toolResult(await runtime.runWorkflow(definition.id, params)); },
      });
    }

    const handlers = createUiHandlers({ store: runtime.store, runtimeVersion: PLUGIN_VERSION });
    api.registerHttpRoute({ path: "/plugins/bionemo/readiness", auth: "plugin", match: "exact", handler: handlers.readiness });
    api.registerHttpRoute({ path: "/plugins/bionemo/assets/3dmol.min.js", auth: "plugin", match: "exact", handler: handlers.viewerAsset });
    api.registerHttpRoute({ path: "/plugins/bionemo/view", auth: "plugin", match: "prefix", handler: handlers.viewer });
    api.registerHttpRoute({ path: "/plugins/bionemo", auth: "plugin", match: "exact", handler: handlers.dashboard });
    api.registerHttpRoute({ path: "/plugins/bionemo/api", auth: "gateway", match: "prefix", handler: handlers.api });
    api.session.controls.registerControlUiDescriptor({
      surface: "tab",
      id: "bionemo-research",
      label: "BioNeMo",
      description: "Hosted NIM catalog, workflow progress, and authenticated artifact downloads.",
      icon: "flask-conical",
      group: "agent",
      order: 5,
      path: "/plugins/bionemo",
      requiredScopes: ["operator.read"],
    });
    api.on("before_prompt_build", async () => ({
      prependSystemContext: `BioNeMo Toolkit pin ${TOOLKIT_COMMIT}. Use only the configured bionemo_*, clawbio_* MCP, and Tavily MCP tools. Never ask for or reveal credentials. When a structure artifact has viewerUrl, always give the user a normal Markdown link labeled View structure in 3D in addition to the downloadable local artifact. Keep all work nonclinical, research-only, and explain confidence plus wet-lab validation requirements. Do not claim that this application itself runs NIM containers or can create Nebius resources.`,
    }));
    api.logger.info?.(`BioNeMo Agent Toolkit ${PLUGIN_VERSION} registered ${PUBLIC_CATALOG.skills.length} skills and ${PUBLIC_CATALOG.workflows.length} workflows`);
  },
};
