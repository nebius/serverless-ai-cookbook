import { ArtifactStore, VIEWER_ROUTE_PREFIX } from "./src/artifacts.mjs";
import { NimClient } from "./src/client.mjs";
import { PUBLIC_CATALOG, SKILLS, TOOLKIT_COMMIT, WORKFLOWS } from "./src/catalog.mjs";
import { publicError } from "./src/errors.mjs";
import { resolveSkillInput, resolveWorkflowInput } from "./src/samples.mjs";
import { createUiHandlers } from "./src/ui.mjs";
import { JSON_SCHEMAS, VALIDATORS, normalizeDirectSkillInput } from "./src/validation.mjs";
import { WorkflowRunner } from "./src/workflows.mjs";
import { MCP_TURN_ID_FIELD, submissionToolBaseName, validMcpTurnId } from "../runtime/mcp-submission-policy.mjs";

export const PLUGIN_VERSION = "3.2.3";

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
    const normalizedInput = normalizeDirectSkillInput(skillId, rawInput);
    const input = VALIDATORS[skillId](await resolveSkillInput(skillId, normalizedInput));
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
    api.registerHttpRoute({ path: VIEWER_ROUTE_PREFIX, auth: "plugin", match: "prefix", handler: handlers.viewer });
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
    api.on("before_tool_call", async (event, ctx) => {
      if (!submissionToolBaseName(event?.toolName)) return;
      const runId = ctx?.runId || event?.runId;
      if (!validMcpTurnId(runId)) {
        return {
          block: true,
          blockReason: "BioNeMo compute submission was stopped because its trusted per-turn identity is unavailable. Start a new chat turn and try once more.",
        };
      }
      return { params: { ...event.params, [MCP_TURN_ID_FIELD]: runId } };
    });
    api.on("before_prompt_build", async () => ({
      prependSystemContext: `BioNeMo Toolkit pin ${TOOLKIT_COMMIT}. Use only the configured bionemo_*, clawbio_* MCP, and Tavily MCP tools. When clawbio_* MCP tools are available, use them for BioNeMo model work and do not call the direct bionemo_* adapters; use direct bionemo_* only when the MCP tools are absent. Follow every displayed tool schema exactly. Pass direct bionemo_* arguments as one flat JSON object. Adapted clawbio_* submission arguments are also flat: pass request fields at the top level as native JSON values plus only the displayed ack_* booleans after explicit user acceptance. Never send request, acknowledgements, or idempotency_key envelope fields, and never stringify an array or object. A clawbio_* submission tool may be called only once per user request. After it returns a job ID, poll only clawbio_job_status for that exact ID, at most four times; never resubmit or call jobs-list/model-fetch discovery while waiting. If it remains nonterminal, report the exact job ID and current status so the user can continue later. Never ask for or reveal credentials. When a structure artifact has viewerUrl, use that exact value in a normal Markdown link labeled View structure in 3D. The value may be a same-origin path beginning with /; preserve it verbatim and never prepend, invent, or rewrite a host. Attach the top-ranked structure by emitting its exact absolute downloadPath as MEDIA:<downloadPath> on its own line in the final reply. Keep all work nonclinical, research-only, and explain confidence plus wet-lab validation requirements. Do not claim that this application itself runs NIM containers or can create Nebius resources.`,
    }));
    api.logger.info?.(`BioNeMo Agent Toolkit ${PLUGIN_VERSION} registered ${PUBLIC_CATALOG.skills.length} skills and ${PUBLIC_CATALOG.workflows.length} workflows`);
  },
};
