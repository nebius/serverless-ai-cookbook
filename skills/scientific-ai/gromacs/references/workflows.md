# Native workflows and boundaries

The prepared-TPR example assumes a **finite** compatible `simulation.tpr`
with compressed trajectory output enabled. It does not generate velocities,
select physics or override duration. Remove/change analyses if the input TPR
deliberately does not produce the required file. For a supplied restart add
`restart_checkpoint: "previous.cpt"` to its `mdrun` step and include that file.

## Preparation

An ordinary protein protocol is explicit `pdb2gmx` → `editconf` → `solvate` →
`grompp`/`genion` → minimization `grompp`/`mdrun` → equilibration → production.
The force field, water model, counterions, salt, protonation and restraints
are customer scientific choices. Include every `.itp`, restraint and index file
in the archive. Interactive selections belong in a step's `stdin`, including
newlines. A prepared ligand topology cannot be inferred from a SMILES or pose.

The onboarding qualification uses public PDB **1AKI**, AMBER99SB-ILDN/TIP3P,
neutralized solvent, minimization, 20 ps NVT and 100 ps production, then native
trajectory/energy joining, frame check, backbone RMSD and temperature/potential.
These 16 steps exercise the runtime but are not an equilibrated research study.
The reproducible generator and raw-evidence pointers are in the platform source:
`k8s-inference/models/molecular-dynamics/gromacs/qualification/make_lysozyme.py`.

## Free energy

GROMACS supports alchemical calculations through explicit MDP/topology inputs.
Choose and document perturbation definition, lambda schedule, soft-core options,
coupling/decoupling, restraints and any required correction terms. Preserve
replica seeds. Independent windows can use separate jobs on one GPU each;
dependent analysis must wait for all required terminal artifacts.

For a sequential campaign, each step can use `directory: "lambda-00"`, etc.,
with `grompp` and `mdrun` pairs. Finish with `gmx bar` using an explicit list of
the actual `dhdl` files (or explicit file-pattern objects). Check equilibration
discard, histogram overlap and estimator uncertainty. Short runs with poor
overlap are workflow tests, not reliable delta-G estimates.

The tested official ethanol tutorial uses seven windows and BAR. Its source is
CC-BY-4.0 and generated fixtures retain attribution. The official tutorial's
educational simultaneous Coulomb/VDW change is not a universal production
protocol. Replica exchange, coupled multi-rank `-multidir`, Hamiltonian replica
exchange and external analysis packages are not covered by this initial shape.

## Performance and Priority 2

- Benchmark the same TPR, settings, atom count and output cadence. Report
  **end-to-end aggregate** simulated ns/day separately from engine-reported
  ns/day; queue, staging/checkpoint I/O and initialization also matter.
- Initial engine: NVIDIA v2026.2 (reports 2026.2-dev), CUDA 13, thread-MPI.
  Real single-GPU tests cover H100/L40S; not every GPU has been qualified.
- PLUMED and Colvars appear in the engine build; enhanced-sampling workflow and
  external PLUMED kernel compatibility are **Priority 2**, not promised support.
- CP2K QM/MM and Torch NNPot are not compiled into that image. They require a
  separate pinned/qualified build and their own license/dependency review.
- Multi-node requires external MPI, compatible GPU-aware MPI/UCX/RDMA and gang
  scheduling. Thread-MPI is in-process and does not span nodes. Strong-scaling
  evidence on a sufficiently large system is needed before making it a default.
- MPS is an aggregate-throughput option, not more memory or independent GPUs.
  The initial customer job shape does not expose MPS or MIG controls. Do not
  change cluster device configuration from a scientific request.
- CUDA snapshots cannot substitute for a coherent CPU/filesystem checkpoint
  or independent random seeds. Native checkpoint continuation is the baseline.

## Primary documentation

- [NVIDIA GROMACS package](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/gromacs)
- [GROMACS 2026.2 commands](https://manual.gromacs.org/2026.2/user-guide/cmdline.html)
- [Managing simulations and checkpoints](https://manual.gromacs.org/2026.2/user-guide/managing-simulations.html)
- [MDP parameters](https://manual.gromacs.org/2026.2/user-guide/mdp-options.html)
- [Performance and offload](https://manual.gromacs.org/2026.2/user-guide/mdrun-performance.html)
- [Heterogeneous parallelization](https://www.gromacs.org/topic/heterogeneous_parallelization.html)
- [Official free-energy tutorial](https://tutorials.gromacs.org/free-energy-of-solvation.html)
- [NVIDIA MPS/MIG measurements](https://developer.nvidia.com/blog/maximizing-gromacs-throughput-with-multiple-simulations-per-gpu-using-mps-and-mig/)

Read the exact runtime/version documentation when flags differ. Never replace
customer scientific settings merely because a newer manual has another default.
