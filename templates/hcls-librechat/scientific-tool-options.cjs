// Keep lifecycle/discovery tools ready; load each model's typed schema on demand.
// This changes only LibreChat's context loading, never gateway authorization or calls.
const core = new Set([
  'list_models', 'list_scientific_models', 'get_model_schema', 'invoke_model',
  'get_operation', 'get_operation_result', 'cancel_operation', 'acknowledge_operation',
  'submit_scientific_run', 'get_scientific_status', 'cancel_scientific_run',
  'list_scientific_events', 'get_scientific_artifact', 'get_scientific_result',
  'begin_scientific_artifact_upload', 'put_scientific_artifact_bytes',
  'finalize_scientific_artifact_upload', 'download_scientific_artifact',
  'read_scientific_artifact_bytes',
]);

module.exports = function scientificToolOptions(agent) {
  const suffix = '_mcp_bionemo-models';
  const options = { ...agent.tool_options };
  // A first request may hold an mcp_all server pin until the catalog is loaded.
  // Predeclare the known model tools as well as any discovered additions.
  const modelTools = [
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
  for (const name of agent.tools ?? []) {
    if (name.endsWith(suffix) && !core.has(name.slice(0, -suffix.length)) &&
        name !== `mcp_all${suffix}`) {
      options[name] = { ...options[name], defer_loading: true };
    }
  }
  return options;
};
