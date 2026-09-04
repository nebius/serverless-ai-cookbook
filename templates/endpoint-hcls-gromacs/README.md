# GROMACS GPU MD API

GROMACS 2023.2 molecular dynamics behind the HCLS asynchronous endpoint contract,
using NVIDIA GPU nonbonded offload.

**License:** [LGPL-2.1](https://gitlab.com/gromacs/gromacs/-/blob/main/COPYING) ·
**Source image:** `nvcr.io/hpc/gromacs:2023.2`, pinned by digest in the Dockerfile

```bash
docker build --platform linux/amd64 \
  -f templates/endpoint-hcls-gromacs/Dockerfile \
  -t hcls-gromacs-md-api:local .
```

The guided argon smoke creates a TPR with `grompp`, runs `mdrun -nb gpu`, and returns
the TPR, coordinates, energies, checkpoint, log, command output, and result manifest.
Prepared TPR input is accepted as bounded base64; custom `.gro`, topology, and `.mdp`
text must be supplied together. Arbitrary command-line arguments are never accepted.

```json
{
  "input": {"steps": 10000, "gpu_mode": "gpu", "threads": 1},
  "research_use_acknowledgement": true
}
```

`ns_per_day` comes from GROMACS `Performance:` output. It describes only the supplied
system, settings, and GPU; it is not a universal hardware ranking. Validate the force
field, ensemble, equilibration, constraints, and sampling for real research.

See [the common API](../hcls-common/README.md) and
[HCLS Workbench](../hcls-workbench/README.md).
