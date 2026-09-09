import { PUBLIC_SAMPLES } from "./samples.mjs";

export const TOOLKIT_COMMIT = "23d483511e0b42221bdafd7259ff43c05220ee86";
export const NVIDIA_HOST = "health.api.nvidia.com";
export const NVIDIA_ORIGIN = `https://${NVIDIA_HOST}`;

const skill = (definition) => Object.freeze({ kind: "skill", ...definition });
const workflow = (definition) => Object.freeze({ kind: "workflow", ...definition });

export const MODEL_INVENTORY_TOOL = Object.freeze({
  name: "bionemo_models_list",
  label: "List BioNeMo models",
  description: "List a sanitized, read-only inventory of configured BioNeMo model services and their readiness without submitting compute.",
});

export const SKILLS = Object.freeze({
  boltz2: skill({
    id: "boltz2",
    tool: "bionemo_boltz2",
    label: "Boltz2",
    route: "/v1/biology/mit/boltz2/predict",
    timeoutMs: 600_000,
    description: "Predict biomolecular structures and optional ligand affinity with Boltz2.",
    artifactTypes: ["mmCIF", "PDB", "JSON"],
  }),
  diffdock: skill({
    id: "diffdock",
    tool: "bionemo_diffdock",
    label: "DiffDock",
    route: "/v1/biology/mit/diffdock",
    timeoutMs: 600_000,
    description: "Dock a small molecule into a protein structure with DiffDock.",
    artifactTypes: ["SDF", "JSON"],
  }),
  evo2: skill({
    id: "evo2",
    tool: "bionemo_evo2",
    label: "Evo2",
    route: "/v1/biology/arc/evo2-40b/generate",
    timeoutMs: 600_000,
    description: "Generate research DNA sequence continuations with Evo2 40B.",
    artifactTypes: ["FASTA", "JSON"],
  }),
  genmol: skill({
    id: "genmol",
    tool: "bionemo_genmol",
    label: "GenMol",
    route: "/v1/biology/nvidia/genmol/generate",
    timeoutMs: 600_000,
    description: "Generate molecules from bounded SAFE notation with GenMol.",
    artifactTypes: ["SMI", "JSON"],
  }),
  molmim: skill({
    id: "molmim",
    tool: "bionemo_molmim",
    label: "MolMIM",
    route: "/v1/biology/nvidia/molmim/generate",
    timeoutMs: 600_000,
    description: "Optimize or sample small molecules with MolMIM.",
    artifactTypes: ["SMI", "JSON"],
  }),
  msa_search: skill({
    id: "msa_search",
    tool: "bionemo_msa_search",
    label: "MSA Search",
    route: "/v1/biology/colabfold/msa-search/predict",
    pairedRoute: "/v1/biology/colabfold/msa-search/paired/predict",
    timeoutMs: 900_000,
    description: "Find homologous protein sequences with hosted ColabFold MSA Search.",
    artifactTypes: ["A3M", "FASTA", "JSON"],
  }),
  openfold2: skill({
    id: "openfold2",
    tool: "bionemo_openfold2",
    label: "OpenFold2",
    route: "/v1/biology/openfold/openfold2/predict-structure-from-msa-and-template",
    timeoutMs: 900_000,
    description: "Predict a monomer structure from sequence and optional MSA/template context.",
    artifactTypes: ["PDB", "mmCIF", "JSON"],
  }),
  openfold3: skill({
    id: "openfold3",
    tool: "bionemo_openfold3",
    label: "OpenFold3",
    route: "/v1/biology/openfold/openfold3/predict",
    timeoutMs: 900_000,
    description: "Predict protein, nucleic-acid, ligand, and complex structures with OpenFold3.",
    artifactTypes: ["PDB", "mmCIF", "JSON"],
  }),
  proteinmpnn: skill({
    id: "proteinmpnn",
    tool: "bionemo_proteinmpnn",
    label: "ProteinMPNN",
    route: "/v1/biology/ipd/proteinmpnn/predict",
    timeoutMs: 600_000,
    description: "Design protein sequences from a bundled public sample or inline backbone PDB with ProteinMPNN.",
    artifactTypes: ["FASTA", "JSON"],
  }),
  rfdiffusion: skill({
    id: "rfdiffusion",
    tool: "bionemo_rfdiffusion",
    label: "RFdiffusion",
    route: "/v1/biology/ipd/rfdiffusion/generate",
    timeoutMs: 900_000,
    description: "Generate protein backbones or bounded binder candidates with RFdiffusion.",
    artifactTypes: ["PDB", "JSON"],
  }),
});

export const WORKFLOWS = Object.freeze({
  research_drug_demo: workflow({
    id: "research_drug_demo",
    tool: "bionemo_research_drug_demo",
    label: "Research-first EGFR drug demo",
    steps: ["Tavily", "OpenFold2", "MolMIM", "OpenFold3"],
    description: "Research public EGFR evidence, characterize its target structure, optimize two gefitinib-derived candidates, and model the best-scoring candidate with the same target sequence.",
    crossBackend: true,
  }),
  compare_protein_structures: workflow({
    id: "compare_protein_structures",
    tool: "bionemo_compare_protein_structures",
    label: "Compare Crambin structure predictions",
    steps: ["OpenFold2", "OpenFold3"],
    description: "Predict the same fixed public Crambin sequence with OpenFold2 and OpenFold3 for a bounded, side-by-side research comparison.",
    crossBackend: true,
  }),
  optimize_ligand_complex: workflow({
    id: "optimize_ligand_complex",
    tool: "bionemo_optimize_ligand_complex",
    label: "Optimize an EGFR ligand complex",
    steps: ["MolMIM", "OpenFold3"],
    description: "Optimize exactly two gefitinib-derived candidates with MolMIM and model the best-scoring candidate with the fixed public EGFR sequence in OpenFold3.",
    crossBackend: true,
  }),
  batch_fold_demo: workflow({
    id: "batch_fold_demo",
    tool: "bionemo_batch_fold_demo",
    label: "Fold five public proteins",
    steps: ["Read fixed FASTA", "OpenFold2 × 5"],
    description: "Read the bundled five-protein FASTA and fold each public sequence exactly once, sequentially, while retaining per-record failures.",
    crossBackend: true,
  }),
  drug_discovery: workflow({
    id: "drug_discovery",
    tool: "bionemo_drug_discovery",
    label: "Drug discovery",
    steps: ["GenMol", "DiffDock", "Boltz2"],
    description: "Generate, dock, and affinity-rank a small event-sized molecule set.",
  }),
  msa_to_structure: workflow({
    id: "msa_to_structure",
    tool: "bionemo_msa_to_structure",
    label: "MSA to structure",
    steps: ["MSA Search", "OpenFold3"],
    description: "Build an MSA and hand it directly to OpenFold3.",
  }),
  protein_binder_design: workflow({
    id: "protein_binder_design",
    tool: "bionemo_protein_binder_design",
    label: "Protein binder design",
    steps: ["RFdiffusion", "ProteinMPNN", "OpenFold3 or Boltz2"],
    description: "Design one bounded binder backbone, sequence it, and co-fold it for research review.",
  }),
});

export const DIRECT_ONLY_TOOL_NAMES = Object.freeze([
  ...Object.values(SKILLS).map((entry) => entry.tool),
  ...Object.values(WORKFLOWS).filter((entry) => !entry.crossBackend).map((entry) => entry.tool),
]);

export const CONFIGURED_BACKEND_ATOMIC_SKILL_IDS = Object.freeze([
  "molmim",
  "openfold2",
  "openfold3",
]);

export const CONFIGURED_BACKEND_ATOMIC_TOOL_NAMES = Object.freeze(
  CONFIGURED_BACKEND_ATOMIC_SKILL_IDS.map((id) => SKILLS[id].tool),
);

export const NVIDIA_ONLY_TOOL_NAMES = Object.freeze(
  DIRECT_ONLY_TOOL_NAMES.filter((name) => !CONFIGURED_BACKEND_ATOMIC_TOOL_NAMES.includes(name)),
);

export const CROSS_BACKEND_TOOL_NAMES = Object.freeze(
  Object.values(WORKFLOWS).filter((entry) => entry.crossBackend).map((entry) => entry.tool),
);

export const EXACT_TOOL_NAMES = Object.freeze([
  ...Object.values(SKILLS).map((entry) => entry.tool),
  ...Object.values(WORKFLOWS).map((entry) => entry.tool),
  MODEL_INVENTORY_TOOL.name,
]);

export const PUBLIC_CATALOG = Object.freeze({
  toolkitCommit: TOOLKIT_COMMIT,
  hostedOrigin: NVIDIA_ORIGIN,
  researchOnly: true,
  modelInventory: MODEL_INVENTORY_TOOL,
  samples: PUBLIC_SAMPLES,
  skills: Object.values(SKILLS).map(({ id, label, tool, description, artifactTypes }) => ({
    id,
    label,
    tool,
    description,
    artifactTypes,
  })),
  workflows: Object.values(WORKFLOWS).map(({ id, label, tool, description, steps }) => ({
    id,
    label,
    tool,
    description,
    steps,
  })),
});
