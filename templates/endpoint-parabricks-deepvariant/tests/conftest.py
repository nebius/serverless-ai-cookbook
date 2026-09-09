from __future__ import annotations

import os
import tempfile


os.environ.setdefault("HCLS_RUN_ROOT", tempfile.mkdtemp(prefix="hcls-test-runs-"))
