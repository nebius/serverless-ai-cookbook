# Native media and recorded-data delivery repair

The v54 robotics Study `4df07e1b-fe38-5670-a588-36e0d84380af` stopped at native
result retrieval. Cosmos operation `41114ce9-55e0-4ccd-b855-fe50691242d7`
completed, but `invoke-native.py` only decoded JSON result artifacts. The actual
gateway contract was `video/mp4`, 1,168,024 bytes, SHA256
`7ab781c20814befb89a4f5a6097220e12edb1d69f4a126bb957f440299506148`.
The original Study remains failed evidence, not a delivered video study.

The generated downstream script also only searched for MP4 filename siblings.
It did not understand verified batch archives or compare the returned recorded
values. It had not executed; this is a demonstrated plan defect, not a claimed
second observed runtime failure.

## Changes

- Native JSON results retain their existing shape. Supported binary results
  publish a verified `result.<extension>` and `scientific-native-file/v1` receipt
  in `result.json`. Size/hash checks and same-operation result recovery remain
  mandatory. Known-result retrieval never submits another inference.
- The typed `robotics-analysis` phase consumes the explicit native result and
  manifest-indexed, hash-verified LeRobot archive. It measures all recorded
  values/types, episode identities/timestamps, camera bytes and decoded frames.
  Declared episode shard locators are respected; relocation is not data loss.
- It publishes the actual MP4 and augmented dataset, measurements and a report.
  Generic filename globbing/null comparisons are not acceptance evidence.
- The same integration exposes the separately tested `evo2-continuation`
  helper with required operation provenance, exact request/reference files and
  suffix-mode semantics. No generation budget or scientific parameter changed.

## Evidence and limits

14 native-client tests pass, including saved MP4 recovery with zero submission
calls, repeat readback, corruption rejection and unchanged JSON behavior.
Eight robotics/integration regressions pass, including actual FFmpeg decoding,
changed recorded values, moved unselected-camera shards and whole-study final
file publication. These fixtures are transport/integrity tests, not model tests.

An offline replay of the retained v42 real ALOHA/model outputs also passes:
128 rows, 6,144 nonvideo scalars, exact untouched-camera bytes/pixels and a
64-frame native video. No inference was submitted. The first replay rejected
the legitimately moved wrist-camera shard; that failed attempt is retained and
the explicit episode-locator regression covers the correction.

Protected receipts live under
`/home/tux/secure-handoff/scientific-unattended-20260919/robotics-helper-repair-v54`.
`retained-v42-r2/receipt.json` identifies its exact source/helper and measurements.
This is not a fresh customer-path pass or a v54 scientific acceptance result.
The combined immutable successor image still needs installed and affected
natural-workflow qualification before customer cutover.

Decoded RGB/temporal differences do not establish geometry preservation,
physical visual-action alignment, policy-training value or biological/clinical
validity. Those remain explicit limitations, not inferred from matching arrays.
