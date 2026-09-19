# Accepted-study replay under an active worker lock

## Observed failure

On exact v57 (`d7cf50364f80e98efa974200d33dbde7f193e6b8`), the clinical
scientist's first `run_scientific_workflow` call returned accepted/queued Study
`e2bdf85f-c25c-50bf-b458-b8ea83ee4057`. The next call replayed the same saved
plan and output directory. It returned `[Errno 11] Resource temporarily
unavailable` while the worker was executing the already accepted study.
The agent then incorrectly told the user nothing had been submitted.

The original study completed all five phases in 124.591 seconds, after its
browser closed, and delivered 30 verified final UI downloads. This is durable
execution/artifact success, **not** a clean end-to-end conversation pass.
The original erroneous message and both tool responses remain unchanged.

Private retained message receipt relative to the protected run directory:
`natural-v57/scientist-08/readback-r2/messages-27e4da0f-1b32-5c84-b193-67cd7c251636.json`,
SHA256 `8605b42bc6c6d56dc022e8264ca669b4f61c8471ae94441dfa64f8aa55f71851`.
No clinical transcript or credentials are copied into this evidence note.

## Cause and repair

`submit()` attempted the nonblocking long-lived phase lock before looking for
an existing immutable receipt. `advance()` legitimately holds that lock for
the duration of its current phase. A replay was consequently treated as a
generic error, despite a successful original admission.

The repair reads the existing publication-synchronized receipt first, validates
the unchanged plan identity and caller fingerprint, and returns the same saved
study. It does not acquire the worker lock, revalidate changing inputs, write
another receipt, or submit another model operation. Accepted responses explicitly
distinguish new admission from an existing-study replay.

If a concurrent first submission holds the lock and has not yet published its
receipt, the second call returns `study_admission: unknown` and a stable identity
for read-only observation. It does not claim rejection or retry admission.
Only acquisition of the admission lock is handled this way; storage errors,
unreadable latest journals and caller/identity mismatches remain errors.
No lock timeout, retry policy, model budget or concurrency limit changes.

## Local regression coverage

The held-lock regression reproduced the original `BlockingIOError` before the
runtime change. Nine new tests cover saved replay, an actual running CPU phase
that finishes only once, concurrent first-admission uncertainty, a publication
race, caller/identity mismatches, damaged latest receipts, unrelated storage
errors, and actual stdio SDK calls using both inline and saved-file plans.

The combined new tests plus existing study/text/cancellation tests pass 52 cases.
The final integration also includes the 18 saved-summary cases: 70 pass, with
receipt `v58-submission-replay-source-final.xml` in the protected run directory.
Ruff and whitespace checks pass. Test-only fixture corrections (required report
role, synchronous local-runner hook and SDK serialization alias) did not weaken
the regression or modify retained evidence.

This source gate is not an installed-image, cloud-deployment or natural-client
pass. The combined successor must run the same acceptance against its immutable
image, followed by customer-shaped qualification. Historical v57 outcomes are
not relabelled.
