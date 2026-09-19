# Seekable scientific output staging

Fresh v42 NumPy NPZ writing failed on the Object Storage mount because the
writer seeks backwards. An ordinary continuation independently used scratch.
This constraint also affects archives, HDF5 and database writers, not just video.

`scientific_receipts.staged_output(destination)` yields a local seekable path
with the same filename/suffix. Close the writer inside the context. Successful
exit reuses the existing streamed artifact publisher and exposes exact byte/hash
metadata. Writer exceptions publish nothing; conflicts preserve existing bytes;
identical destinations resume with verification. The batch client imports the
same publisher rather than keeping a duplicate implementation.

```python
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, '/opt/bionemo')
from scientific_receipts import staged_output

with staged_output(Path('/workspace/my-study/measurements.npz')) as staged:
    np.savez(staged.path, values=values)
print(staged.receipt)
```

This is an explicit helper, not replacement of all filesystem operations.
Bucket publication is streamed exclusively and read back, **not atomically
visible** to another reader. Scratch is temporary. Live SQLite/WAL, concurrent
databases and general shared POSIX semantics remain unsupported. Use SQLite's
backup API to a closed standalone local file and then publish that file.

## Source and actual-provider tests

79 focused tests pass: 8 staging, 7 analysis-export, 11 receipt, 41 streaming/
batch/result-recovery, and 12 execution-guidance; Ruff passes. Local/simulated
checks are distinct from the following actual-provider qualification.

One authorized CPU Serverless job used the exact v42 image, original test-owned
bucket and existing credential binding. Candidate module and fixture lived in
an isolated test prefix, not over the live installation. No inference, GPU,
public execution route, SSH, endpoint mutation, quota or policy change.

- Job `aijob-e00drr1vm8qnymczm8` provisioned from 05:17:31 UTC; image pull began
  05:19:03. The fixture ran 05:20:27.963026513–05:20:28.991179556 (1.028153s).
- NPZ, ZIP, HDF5 and a closed SQLite backup used `verified-copy` on the actual
  mount. Independent S3 downloads matched every hash and reopened all four
  formats, including SQLite integrity and exact rows.
- Failed writer left no object; conflicts preserved original bytes; identical
  resume returned `verified-existing`.
- Module SHA256 `be4e6bc84c7a2514e99f2e26e68838f789f17347dc80562540aeb47feb5fdd37`;
  fixture SHA256 `6f185ba5af17b60a3abc085f795b84c8a74e12a0e63ef78c496bc78c475d2958`.
- Protected `workspace-staging-v43/independent-verification.json` SHA256
  `cae1886b1fc0e6c3a1d550f5b909bff951da53987cf2951b32072083fae28851`.
- Only the completed test job was deleted after retaining full configuration,
  logs and receipts. Independent bucket files, credentials and previews remain.

Initial test commands used the wrong existing venv (missing httpx2 or boto3).
Separated existing environments passed without installing/changing packages.
Unrelated pytest cleanup warnings refer to older root-owned PostgreSQL sockets,
which were not deleted. Source and mount qualification are not evidence of
natural agent adoption; that needs a separately recorded successor replay.
