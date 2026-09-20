// Keep only the two compact discovery primitives ready. Every execution,
// lifecycle, analysis and model-specific schema remains searchable and is
// loaded only when the agent needs it. This changes LibreChat context loading,
// never gateway authorization, tool visibility or calls.
const alwaysReady = new Set([
  'get_model_schema_mcp_scientific-ai-apps',
  'workbench_list_apps_mcp_scientific-demos',
]);
const deferableSuffixes = [
  '_mcp_scientific-ai-apps',
  '_mcp_scientific-demos',
  '_mcp_environment-execution',
  '_mcp_structure-viewer',
  '_mcp_tavily',
];

function shouldDefer(name) {
  return typeof name === 'string' &&
    deferableSuffixes.some((suffix) => name.endsWith(suffix)) &&
    !alwaysReady.has(name) &&
    !name.startsWith('mcp_all_mcp_');
}

module.exports = function scientificToolOptions(agent, loadedTools = []) {
  const suffix = '_mcp_scientific-ai-apps';
  const options = { ...agent.tool_options };
  // A first request may hold an mcp_all server pin until the catalog is loaded.
  // Predeclare the known model tools as well as any discovered additions.
  const modelTools = [
    'list_models', 'list_scientific_models', 'get_operation', 'get_operation_result',
    'msa_search_native', 'submit_alphafold3', 'submit_bindcraft', 'submit_boltzgen',
    'submit_esmfold2', 'submit_esmfold2_fast', 'submit_mosaic',
    'submit_openfold3_openbind', 'submit_proteina_complexa', 'submit_protenix_v2',
    'submit_rfdiffusion', 'app_95943840d2b14a65b5cdaa4717b2cdc3',
    'infer_altumage_native', 'boltz2_predict_native', 'cosmos3_nano_generate_media_native',
    'infer_diffdock_native', 'generate_dna_native', 'genmol_generate_native',
    'molmim_run_native', 'analyze_image_openai_chat', 'segment_ct_native',
    'infer_openfold2_native', 'infer_openfold3_native', 'infer_phenoage_native',
    'infer_proteinmpnn_native', 'qwen3_8b_chat_openai_chat', 'generate_image_native',
  ];
  for (const rawName of modelTools) {
    const name = rawName + suffix;
    options[name] = { ...options[name], defer_loading: true };
  }
  for (const name of [...(agent.tools ?? []), ...loadedTools.map((tool) => tool.name)]) {
    if (shouldDefer(name)) {
      options[name] = { ...options[name], defer_loading: true };
    }
  }
  // The definitions-only loader expands mcp_all after this helper runs. Resolve
  // newly published names at lookup time too, without maintaining another model
  // catalog. This affects context loading only, never tool ACLs or validation.
  return new Proxy(options, { get(target, name, receiver) {
    const value = Reflect.get(target, name, receiver);
    if (shouldDefer(name)) {
      return { ...value, defer_loading: true };
    }
    return value;
  } });
};
