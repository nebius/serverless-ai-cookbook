# Integration evidence — 17 September 2026

Only synthetic/public teaching data. No credentials, clinical validation or
production-readiness claim. The recording source and licensing notes are in
`/home/tux/demo-assets/medical-speech-en-de-20260916/README.md`.

- `20260917-r2`: first successful queued upload workflows, including complete
  EN/DE audio. Summary separates cached replay latency from original receipt
  duration. It is not a cold-start benchmark.
- `20260917-r3`: same-job recovery after a provider ReadTimeout. The original
  318-second attempt was incomplete. The final 598-second receipt includes the
  operator's delay before pressing Resume; do not treat it as model inference
  time or hide the failure. Completed stages were reused.
- `20260917-report-fidelity-r4` and `r5`: **rejected prompt experiments**. German
  appetite history was preserved, but English unclear medication `dire light`
  was normalized to a brand and accepted. These prompts are not shipped. The
  original verifier is retained; its known false rejections remain visible in
  the report review queue. The first diagnostic additionally made an incorrect
  test assumption that stool testing was entirely unspoken; the full transcript
  does mention taking a sample, with an ASR error. That assertion was corrected.
- `report-fidelity-calls.tar.gz`: exact requests, responses and timing receipts
  for both rejected experiments. Kept compressed to avoid hundreds of generated
  call files in code review. `run.json` contains source/prompt hashes.

Browser-backed workshop runs:

- `d2481256-b22e-4a2a-9d9f-37f284333b79`: Qwen-30B, profile-000, ten rounds,
  completed, unchanged, five-axis mean 4.05, benchmark eligible.
- `d9533733-73df-4dae-bbb9-097070acbbf7`: profile-001, pause → nudge → clinician
  takeover → human turn → resume; completed, mean 4.525, correctly excluded
  from benchmark comparisons. Abort was disabled after completion as expected.

These examples test transport/controls and are not a meaningful clinician
ranking. Expanded model qualification lives in the solutions-library gateway
evidence directory, not here. The final gateway/customer-path release test is
separate from these local client candidates.
