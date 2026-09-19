# v56 installed runtime and local migration gate

Bounded local gates passed on 19 September 2026. These are not natural-client,
scientific-validity, clinical-readiness, or customer-cutover acceptance. The v55
harness was preserved but never run; the final successor was tested once.

## Immutable identity

- Source: `cba6304ec772a70cc7fccf44743145b0a7e3a479`.
- Tag: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v56-cba6304`.
- OCI index: `sha256:7b5b3b46713b61fd5fafc8085fa29fd8fc54f631a993c1aa28c4aa7d9e842c3c`.
- amd64 runtime: `sha256:a22fe8caffb04a31dee7bdf0e519a67e0da0fab793e105c4963169c704dc59d3`.
- Root-owned publication was independently recorded before the local gate.

Protected paths below are relative to
`/home/tux/secure-handoff/scientific-unattended-20260919`. They contain private
state and are intentionally not copied into the repository.

## Exact installed gate

`workbench-v56-installed.gj9k7jf8/acceptance.json`, SHA256
`70b3b428f1030b178de85c1c3163445d66d899dac48c1940fdf60a341e2c95c6`.

Task-owned Docker containers used the immutable index, network `none`, and no
runtime-file overlays. Test scripts and pytest dependencies were mounted only as
tests. Eighteen actual installed runtime files, including the worker, receipt
module, render configuration and service, matched the frozen source hashes.

- Eleven baseline SDK cases exercised the installed LibreChat renderer,
  `processMCPEnv`, real stdio SDK transport, owner binding and durable CPU work.
- Semantic validation rejected compact MindEval inputs and directory
  deliverables; correction to full records completed through the same admission
  path. The retained 381-character one-line title remained verbatim.
- Typed GenMol and genuine mmCIF analysis completed; malformed JSON filenames,
  impossible helper outputs and literal future-output paths were rejected.
- JSON-text and object plans resolved to the same durable identity; malformed
  JSON text admitted nothing.
- The installed clinical helper executed with synthetic HTTP-boundary responses
  only. Default no-report behavior failed strictly. Explicitly permitted
  `no_supported_clinical_facts` preserved source/review/coverage and completed its
  downstream report in a fresh standard installed worker after SDK disconnect.
  Four synthetic extraction responses were used; zero actual provider calls.
- Ten installed receipt-publication lock cases passed.
- Sixty-one installed domain cases passed: 14 native artifact transport,
  8 robotics, 26 sequence analysis, 12 cancellation, and one dependent Evo2
  whole-study publication case. Robotics tests included actual synthetic video
  decode, parquet, zstd and closed-file publication. Native transport and
  cancellation responses were fixtures, not live operation acceptance.
- Cancellation used the actual installed worker, retained a saved sent intent,
  tolerated changed analysis/input bytes only for cancellation, observed the
  same operation without new admission, released the queue, and retained the
  original failure. Owner/plan/operation ambiguity remained fail-closed.
- Evo2's test used saved synthetic operation envelopes, explicit future FILE
  references, the actual helper CLI and final report/manifest publication. It
  did not submit new inference or turn continuation scores into likelihoods.

The independent readback verified 38 nonempty files across seven completed CPU
studies in the baseline/semantic/typed/clinical gates. Domain tests separately
verified their own manifests. The strict expected-negative clinical study was
also retained as a failure, not counted among completed studies.

## Local customer migration replay

`rene-replacement/v56-local-acceptance.json`, SHA256
`f4e84b8ea594febbd1f0d0f2870bb9123419cc78bbcaa0124e578db66c56d8e2`.

The exact v56 image imported the retained strict-v2 customer archive into a new
isolated local Mongo instance: 49 collections, 81 documents, 334 index
definitions and two state files. Exact customer-state preservation was checked
before login. Six workbench seeds explicitly used Kimi-K3 at the unchanged
8192 output / 131072 context / low reasoning configuration; two Qwen demo seeds
remained unchanged. Original agent IDs, creation times and histories were
preserved. The retained archive contained zero custom agents and zero uploaded
files; this is not a positive nonempty custom-agent/upload replay claim.

The original password passed bcrypt verification and actual HTTP login; the
original account and one conversation/two messages were read unchanged, both
before and after a local restart. A complete post-login snapshot then survived
a further restart with exact customer-state equality. The local container was
stopped and its data retained. No model calls, cloud source reads or cloud
mutations occurred.

The network-isolated startup replayed only the previously retained exact
`GET /v1/models` response. It did not qualify live provider discovery, hosted
MCP, bucket mounts or a new customer endpoint. The prepared, unexecuted cloud
plan is `rene-replacement/prepared-20260919T191042024501Z/plan.json`.

Retained test failures were not rewritten: the first local image inspection
preceded completion of the Docker pull and created no container; one private
binding test initially over-replaced its own sentinel string; and a comparison
against the pre-login backup correctly detected the new session created by
the test login. That last failure was resolved by testing an exact post-login
snapshot, not by excluding session records or weakening the restore check.

Before customer cutover, the original source still requires fresh activity,
configuration and strict-state captures, an unchanged-state check before
activation, explicitly approved cloud migration, and real login/chat/files/
bucket continuity on the actual successor. The original customer endpoint was
not changed. Original v54 workflow failures remain historical evidence; the
successful v54 scientist04 study is not relabelled v56.
