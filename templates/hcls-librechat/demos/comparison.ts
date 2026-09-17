export type WorkshopRun = {
  id: string; batch_id: string; status: string; created_at: string;
  state: {
    config: { patient_model: string; max_turns: number; mode: string; profile_id: string;
      clinician_model: string; profile_ids: string[]; clinician_models: string[] };
    transcript?: { role: string; content: string }[]; intervened?: boolean; benchmark_eligible?: boolean;
    registration?: { judge_model?: string; provenance?: unknown };
    judgment?: { model?: string; judgment: Record<string, number>; overall_score: number };
    error?: { message?: string };
  };
};

/** A batch fixes the profile cohort and generation parameters at admission.
 * Only profiles completed without intervention by EVERY selected clinician
 * enter the paired mean. Failures and missing cells stay in the denominator.
 */
export function compareBatch(runs: WorkshopRun[], batchId: string) {
  const rows = runs.filter((run) => run.batch_id === batchId);
  const config = rows[0]?.state.config;
  const models = config?.clinician_models || [];
  const profiles = config?.profile_ids || [];
  const judgeModels = new Set(rows.map((run) => run.state.judgment?.model || run.state.registration?.judge_model).filter(Boolean));
  const qualifies = (run?: WorkshopRun) => Boolean(run && run.status === 'completed' &&
    run.state.benchmark_eligible && !run.state.intervened &&
    Number.isFinite(run.state.judgment?.overall_score) && judgeModels.size === 1);
  const matched = profiles.filter((profile) => models.every((model) =>
    qualifies(rows.find((run) => run.state.config.profile_id === profile && run.state.config.clinician_model === model))));
  const summaries = models.map((model) => {
    const own = rows.filter((run) => run.state.config.clinician_model === model);
    const paired = own.filter((run) => matched.includes(run.state.config.profile_id));
    const scores = paired.map((run) => run.state.judgment!.overall_score);
    return { model, planned: profiles.length, completed: own.filter(qualifies).length,
      failed: own.filter((run) => ['failed', 'aborted'].includes(run.status)).length,
      intervened: own.filter((run) => run.state.intervened).length,
      missing: profiles.length - own.length, paired: scores.length,
      mean: scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null };
  });
  return { batch_id: batchId, profiles, matched_profiles: matched, judge_models: [...judgeModels],
    clinical_validation: false, summaries, runs: rows };
}

export function comparisonCsv(result: ReturnType<typeof compareBatch>) {
  const quote = (value: unknown) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const fields = ['model', 'planned', 'completed', 'failed', 'intervened', 'missing', 'paired', 'mean'] as const;
  return [fields.join(','), ...result.summaries.map((row) => fields.map((key) => quote(row[key])).join(','))].join('\r\n');
}
