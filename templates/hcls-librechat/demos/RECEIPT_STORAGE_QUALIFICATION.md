# Customer bucket receipt persistence

18 September 2026; found during the natural Scientist03 GLM-5.3 binder-design
study, not a synthetic model smoke test. The packaged batch client failed before
admission because `chmod` is unavailable on the mounted customer bucket.

## Observed mount behavior

The no-inference Scientist01 operator check ran against the real Serverless
`/workspace` bucket mount. All five tested temporary-file/rename variants read
back zero bytes at the destination, despite the source reading back correctly;
explicit flush/fsync did not repair rename. Direct write/readback succeeded.
POSIX lock-file operations on that mount also failed. Local tests did not expose
these behaviors. The failed candidate checks remain in the private evidence.

The shared `scientific_receipts.py` therefore:

- Writes JSON directly, requests mode0600 at creation, flushes, and verifies the
  actual bytes. A mismatch stops the client without submitting subsequent work.
- Writes each `receipt.json` state to an immutable `.receipt-history` record
  before updating its canonical JSON view. Resume selects the newest journal,
  including if the canonical write was interrupted or remained stale.
- Fails closed on an incomplete newest journal; it never falls back to an older
  pre-admission state and silently submits again. Legacy receipts remain readable.
- Uses a local container lock keyed by the absolute receipt directory. This
  excludes competing local clients, not writers across different containers.
  Platform idempotency remains the cross-container admission boundary. Do not
  run two clients for the same logical submission at once.

`check-receipt-storage.py` verifies real mounted writes, update/readback, recovery
of the original synthetic operation after an interrupted canonical write, and
local lock exclusion. It makes zero model calls and is not scientific acceptance.
`diagnose-mount-writes.py` preserves the bounded original mount probe.

History is intentionally retained during qualification. This patch does not
claim distributed filesystem transactions, durable LibreChat conversation
storage, or completed end-to-end scientific studies.

The corrected live check passed for all three clients, including canonical
truncation recovery and rejection of a competing local writer. Independently
downloaded the report and three resulting receipts via the Object Storage API,
not just the mount cache: report SHA-256
`82d0cdda23a175c3b85852df6596834a0db39e6ca9c7eadc36e7bd5ce82cf738`.
The agent's statement that this demonstrated "3 concurrent writers" is wrong:
three client implementations were tested sequentially, and the lock test proved
exclusion. The raw report, not that narrative, is the acceptance evidence.

## Context evidence and bounded output

Scientist03's first v16 GLM turn contained22 tool calls: approximately22KB tool
arguments and73KB outputs. The largest output was15KB of client implementation
source read while recovering our storage defect; each chosen model schema was
about8KB and the literature search7.5KB. The full live MCP catalog is317KB across
61tools, including deferred schemas of44KB (imaging),40KB (chat), and34KB (Cosmos).
Catalog bytes are not proof those deferred schemas were sent to the LLM.

The browser showed104K context before compaction; that UI estimate is not a
provider-verified token bill. The retained summary itself reports16,650tokens.
No context/completion/tool limits were increased. Default execution output now
returns4000bytes, total size, paging offset and a complete log-file pointer.
Instructions require local data reduction and discourage reading whole helper
sources or repeating unchanged model discovery. The next release must be tested
on fresh natural studies; reduced output alone is not a readiness claim.
