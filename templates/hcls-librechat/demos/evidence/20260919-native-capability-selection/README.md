# Preserve the native capability across durable execution

The exact v56 natural robotics Study
`503d2abc-fcf9-5c7d-adc6-dd62614ddb3a` failed before model admission.
The planner discovered `cosmos3_nano_transfer_video` and correctly prepared
its specialized input without the generic `mode` field. The durable native
phase could not carry the selected tool, and its client instead selected the
first native catalog entry: `cosmos3_nano_generate_media_native`.

The saved rejection was `local_input_validation`, `durable_admission:false`,
with the missing `mode` requirement. No model operation was created. One prior
artifact upload succeeded; it is not inference. The original failed Study,
plan, input, public schemas and chat remain unchanged. The Study's generic
ExceptionGroup hid the saved actionable rejection. Its interim chat also
incorrectly described both model calls as submitted after only Study admission.

The successor fixes the interface, not the scientific input:

- Optional native `tool_name` passes through both workflow versions to
  `invoke-native.py --tool`, is frozen in the plan/client identity, and selects
  that exact live contract.
- Legacy unnamed inputs require one uniquely validating native contract.
  Catalog ordering cannot select a capability. Ambiguity, unknown selectors
  and invalid inputs fail before inference; no mode is added or translated.
- Saved operation recovery still avoids rediscovery/resubmission. Changing the
  selected tool cannot reuse a different tool's receipt identity.
- Proven local no-admission errors expose bounded validation/selection metadata
  through the durable seam; ambiguous admissions are not relabelled or retried.
- Installed instructions preserve named capabilities and distinguish a queued
  Study from actual model operation IDs.

The checked-in six-contract fixture contains only public input schemas, not
customer data, handles or credentials. Fifteen selection regressions plus the
fourteen existing native-client regressions pass, including successful dedicated
dispatch without `mode`, replay without network, changed-selector rejection,
invalid/ambiguous no-admission and binary result recovery. These tests are not
a natural robotics acceptance pass. The combined successor still requires an
exact installed-image test and a new untouched customer workflow.

Protected original diagnosis receipt SHA256:
`8ec5fb0feeafcbf1db0dcb8edfc5ba5ac4a4a599bd15cdf9f62833d64c76ad4a`.
