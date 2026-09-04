# OpenMM GPU MD API

OpenMM 8.5.1 with its CUDA platform behind the HCLS asynchronous endpoint contract.

**License:** [MIT](https://github.com/openmm/openmm/blob/master/LICENSE) ·
**Source:** [OpenMM](https://github.com/openmm/openmm)

```bash
docker build --platform linux/amd64 \
  -f templates/endpoint-hcls-openmm/Dockerfile \
  -t hcls-openmm-md-api:local .
```

The guided examples are periodic Lennard-Jones argon systems for integration and
throughput validation. They are synthetic plumbing/performance cases, not biological
simulations.

```json
{
  "input": {
    "particle_count": 4096,
    "steps": 10000,
    "integrator": "LangevinMiddle",
    "precision": "mixed",
    "seed": 17
  },
  "research_use_acknowledgement": true
}
```

The endpoint refuses to report ready or execute when no NVIDIA GPU is visible. Results
identify CUDA, precision, ensemble, timestep, periodic box, energies, simulated time,
integration wall time, and integration ns/day. The positions artifact is a bounded
preview. Validate the physical model and sampling independently before scientific use.

The initial deployment target is `gpu-l40s-a` / `1gpu-8vcpu-32gb`. See
[the common API](../hcls-common/README.md) and
[HCLS Workbench](../hcls-workbench/README.md).
