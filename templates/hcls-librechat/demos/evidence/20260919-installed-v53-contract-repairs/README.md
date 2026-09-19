# Exact installed v53 contract-repair gate

Passed on source `77994a39a9d0da6b78c9eb882bee66710bffe7a1`, OCI index
`sha256:cc2e18b8a6db41cf143dbbff126bb8e15b36ba1b5b4c27289ff3d180fa67abda`,
runtime manifest
`sha256:5cc9c61365bd1c9fc2150930e3b0ca222e13a9d179a04adaf2eda2da310048ee`.
The image was independently registry-verified before testing. No cloud resources,
customer studies, model calls or provider credentials were used.

All tests used the installed renderer, LibreChat `processMCPEnv`, MCP SDK stdio
transport and installed Python helpers in the immutable image. Docker networking
was disabled. Mounted files were external tests/evidence and isolated workspaces,
never replacements for runtime modules. Eight installed runtime hashes matched
the frozen source, including the batch client, GenMol helper, design helper and
its shared evaluator.

- All 11 baseline SDK cases passed: correct owner transport, excluded-owner
  regressions, clinical credential preflight without calling a provider,
  grouped composer persistence and same-identity admission/reconnect.
- The actual retained 381-character one-line title was preserved. Compact
  MindEval records and directory deliverables failed before admission; selecting
  full unchanged records allowed normal completion after client disconnect.
- A new typed study exercised saved GenMol request/result analysis and a real
  mmCIF artifact, using installed `gemmi==0.7.3`. It verified all four declared
  phases and exact manifest-order artifact bytes. Invalid/duplicate/underfilled
  molecules remained visible, not converted into a successful scientific score.
- Wrong JSON filenames, impossible known-helper outputs and predicted future
  filesystem paths were rejected before admission. No automatic renaming,
  protocol changes or retry/budget increases were introduced.
- Five CPU studies completed after client disconnect; reconnect and a separate
  reader verified **30 nonempty final artifact/manifest files** against exact
  byte counts and SHA-256. No hosted inference was submitted.

Protected receipt:
`U/workbench-v53-installed.TGr0M0/acceptance.json`, SHA-256
`58c704b4d99bedc18ebd1c4c8b802fd5474c798e45ea990bc410cd8c07076f02`.
The receipt binds the external semantic/typed test scripts by hash, all execution
receipts, source/image identities and independent readback. The gate passed on
its first execution.

This is **installed-component qualification, not natural-customer acceptance**.
Cloud v53 was held because a separate controlled test reproduced concurrent
receipt-publication reads failing closed. That repair and its successor image
require their own evidence. The original v52 failed customer journeys remain
unchanged; a CPU helper gate does not retroactively repair their reports.
