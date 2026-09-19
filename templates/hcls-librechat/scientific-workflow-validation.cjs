// Presentation only: the pinned tool's original validator remains authoritative.
const { createRequire } = require('node:module');
const appRequire = createRequire('/app/api/server/services/MCP.js');
const { validate } = appRequire('@cfworker/json-schema');
const { ToolInputParsingException } = appRequire('@langchain/core/tools');
const METHODS = new Set(['compose_scientific_workflow', 'run_scientific_workflow']);
const MAX_ISSUES = 6;

function describe(schema, value, path = '$', issues = []) {
  if (issues.length >= MAX_ISSUES || validate(value, schema).valid) return issues;
  const add = (field, constraint) => {
    const text = `${field}: ${constraint}`;
    if (issues.length < MAX_ISSUES && !issues.includes(text)) issues.push(text);
  };
  // Select an existing alternative for diagnostics only; never change the
  // schema/input passed to call(), or try a second handler invocation.
  if (Array.isArray(schema.oneOf)) {
    let candidates = schema.oneOf;
    for (const discriminator of ['kind', 'method']) {
      if (value && typeof value === 'object' && Object.hasOwn(value, discriminator)
          && candidates.some(s => s.properties?.[discriminator])) {
        candidates = candidates.filter(s => s.properties?.[discriminator]
          && validate(value[discriminator], s.properties[discriminator]).valid);
        if (!candidates.length) {
          add(`${path}.${discriminator}`, 'must match a published workflow kind/method');
          return issues;
        }
      }
    }
    if (candidates.length > 1) {
      const typed = candidates.filter(s => s.type && validate(value, { type: s.type }).valid);
      if (typed.length === 1) candidates = typed;
    }
    if (candidates.length === 1) describe(candidates[0], value, path, issues);
    else add(path, 'must satisfy exactly one documented alternative');
  }
  const failures = validate(value, schema).errors.filter(e => e.instanceLocation === '#'
    && e.keywordLocation === `#/${e.keyword}`);
  for (const { keyword } of failures) {
    if (keyword === 'required') {
      for (const name of schema.required ?? []) {
        if (value && typeof value === 'object' && !Object.hasOwn(value, name)) add(`${path}.${name}`, 'required');
      }
    } else if (keyword === 'type') add(path, `must have type ${[].concat(schema.type).join(' or ')}`);
    else if (keyword === 'minimum') add(path, `must be >= ${schema.minimum}`);
    else if (keyword === 'maximum') add(path, `must be <= ${schema.maximum}`);
    else if (keyword === 'exclusiveMinimum') add(path, `must be > ${schema.exclusiveMinimum}`);
    else if (keyword === 'exclusiveMaximum') add(path, `must be < ${schema.exclusiveMaximum}`);
    else if (keyword === 'minItems') add(path, `must contain at least ${schema.minItems} item(s)`);
    else if (keyword === 'maxItems') add(path, `must contain at most ${schema.maxItems} item(s)`);
    else if (keyword === 'minLength') add(path, `must contain at least ${schema.minLength} character(s)`);
    else if (keyword === 'enum' || keyword === 'const') add(path, 'must use a documented allowed value');
    else if (keyword === 'pattern' || keyword === 'not') add(path, 'must satisfy the documented format/exclusion');
    else if (keyword === 'additionalProperties') add(path, 'contains an unsupported field; use only documented fields');
    else if (keyword === 'anyOf' || keyword === 'allOf' || keyword === 'dependentRequired') add(path, 'must satisfy the documented field combination');
    else if (keyword === 'uniqueItems') add(path, 'must contain distinct items');
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    // Only schema-owned property names enter diagnostics, never submitted keys.
    for (const [name, child] of Object.entries(schema.properties ?? {})) {
      if (Object.hasOwn(value, name)) describe(child, value[name], `${path}.${name}`, issues);
      if (issues.length >= MAX_ISSUES) break;
    }
  } else if (Array.isArray(value) && schema.items && !Array.isArray(schema.items)) {
    for (let i = 0; i < value.length && issues.length < MAX_ISSUES; i++) describe(schema.items, value[i], `${path}[${i}]`, issues);
  }
  return issues;
}

function attach(toolInstance, serverName, serverToolName) {
  if (serverName !== 'environment-execution' || !METHODS.has(serverToolName)
      || toolInstance.name !== `${serverToolName}_mcp_environment-execution`) return toolInstance;
  const originalCall = toolInstance.call;
  toolInstance.call = async function (...args) {
    try { return await originalCall.apply(this, args); }
    catch (error) {
      if (error instanceof ToolInputParsingException) {
        try {
          const arg = args[0];
          const input = arg?.type === 'tool_call' ? arg.args : arg;
          // Handler-thrown parsing exceptions are not input-validation errors.
          if (!validate(input, this.schema).valid) {
            const issues = describe(this.schema, input);
            const details = issues.join('; ').slice(0, 880);
            error.message = 'Received tool input did not match expected schema'
              + (details ? `: ${details}.` : '. Check the published workflow schema.')
              + ' Correct these fields and call the same tool again.';
          }
        } catch { /* Unknown schema/metadata: retain the original exception. */ }
      }
      throw error;
    }
  };
  return toolInstance;
}

const ANCHOR = `  const toolInstance = tool(_call, {
    schema,
    name: normalizedToolKey,
    description: description || '',
    responseFormat: AgentConstants.CONTENT_AND_ARTIFACT,
  });`;
const CALL = "  require('/opt/hcls-librechat/scientific-workflow-validation.cjs').attach(toolInstance, serverName, serverToolName);";
function patchFactory(source) {
  if (source.split(ANCHOR).length !== 2 || source.includes(CALL)) throw new Error('Unsupported pinned MCP tool factory');
  return source.replace(ANCHOR, `${ANCHOR}\n${CALL}`);
}
module.exports = { attach, patchFactory, ANCHOR, CALL };
