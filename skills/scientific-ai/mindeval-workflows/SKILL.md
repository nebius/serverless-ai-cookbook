---
name: mindeval-workflows
description: Run or analyze the existing MindEval consultation simulation and judge workflow, with fixed patient/judge roles, explicit clinician variants, retained interventions and exact score exports. Use for the Scientific AI workshop client when scientific-demos is available.
license: Apache-2.0
---

# MindEval consultations

MindEval is a workflow provided by the existing `scientific-demos` MCP, not a
model App or a replacement clinical service. Check that this optional server is
connected. With only the hosted model MCP, explain that the workshop harness is
not installed; don't invent workshop tools. Upstream: https://github.com/SWORDHealth/mind-eval

For a new authorized run, use the registered workshop catalog to discover the
actual clinician choices and fixed patient/judge. Preserve profiles, prompt
versions, turn cap and patient/judge settings across clinician comparisons.
Judge-family conflicts and interventions must be visible in the report; don't
claim an unbiased comparison merely because scores exist. Never call a private
Sword production endpoint without its separate explicit authorization.

Use current workshop tool schemas for starting, observing and intervening in a
run. Keep the run ID; acceptance is not completion. A simulated consultation is
not clinical advice or evidence of patient outcomes.

For reuse-only analysis, obtain the full retained record with `workshop_get_run`
and its verified `workspace_file`. Do not start a new consultation to recreate an
export. The installed durable `mindeval` analysis phase accepts retained record
paths and produces `report.md`, `scores.csv`, `runs.csv`, `measurements.json`,
`provenance.json`, original records and complete transcripts. Preserve missing
scores and failed judgments rather than silently replacing them with zero.
Quote computed scores and criteria from those files, not a chat summary. No
clinical winner is inferred from a small or methodologically unmatched cohort.
