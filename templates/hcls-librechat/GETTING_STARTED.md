# Getting started with Scientific AI

Your operator gives you a personal LibreChat URL and login. You use a dedicated
instance even when colleagues share your tenant and its bucket. Models are
shared hosted Apps; you do not deploy them yourself.

1. Sign in and keep **Nebius Scientific AI Agent** selected to start.
2. Open **Apps**. It lists models authorized by your Scientific AI key. If the
   key is missing, configure it in the Apps key settings. Never paste a key into
   chat. Token Factory/OpenAI/Anthropic provider keys authorize chat models, not
   scientific Apps; object-storage credentials authorize files, not inference.
3. Open **Workspace → examples → v1**. This licensed/public/synthetic sample pack
   includes a README, manifest and per-case recipes. Read the source and license
   notes. If the mount or examples are missing, ask the operator to check storage
   and starter-data installation; do not invent a path or create another bucket.
4. Use **Getting started** to copy a prompt into chat. The workspace tour lists
   what your account can use without submitting model inference. Choose a model
   example, inspect the proposed input, then ask the agent to run it.
5. Follow the operation in **Runs**. After completion, inspect the real output
   files and download links. Save results outside the examples directory, e.g.
   `/workspace/my-studies/protein-001/`.

## Useful first examples

| Example | Input | Expected deliverable |
| --- | --- | --- |
| Workspace tour | Authorized catalog and sample index | Three applicable examples; no model inference |
| OpenFold2 | A public protein-sequence example | Structure, returned confidence and operation ID |
| GenMol | A small molecule-generation recipe | Generated SMILES and a saved result file |
| English speech | A complete teaching consultation | Full transcript and human-reference comparison |
| PhenoAge | Synthetic laboratory values with units | Numerical result and exact input provenance |
| SAM 2 | Synthetic image and segmentation prompts | Segmentation output and its downloadable artifacts |

These are onboarding examples, not reproduction of a scientific paper or
evidence of clinical efficacy. Some models require specific grants or licenses.
The exact live schema and recipe decide the actual input and output contract.
Do not shorten a recording or silently switch a model to make a test pass.

## How every example works

The cards prepare an editable chat prompt. **Copying a prompt does not submit
inference.** The agent first checks the caller-visible Scientific AI Apps,
reads the selected App's live schema and verifies the sample path. Before it
submits anything, it should show the exact input, expected output and destination
directory. One logical request gets one idempotency identity and one durable run
or operation ID. If the browser disconnects, resume that ID from **Runs**; do not
create a duplicate. Completed files belong under `/workspace/my-studies/`, never
inside the read-only example source directory.

### 1. Explore my workspace

- **Purpose:** learn what this user can actually access before spending GPU time.
- **Reads:** caller-scoped Apps plus `/workspace/examples/v1/README.md` and its
  manifest when the starter pack is mounted.
- **Produces:** three suitable examples with their source inputs and expected
  deliverables. It submits no model request and creates no scientific result.
- **Failure boundary:** a missing key, mount or manifest is reported explicitly;
  the agent must not invent a path, model grant or replacement bucket.

### 2. Fold a sample protein

- **App:** OpenFold2, only when it is visible to the caller and its current
  schema accepts the selected public sequence recipe.
- **Produces:** the original operation ID, terminal state, actual returned
  structure file and every confidence field the App explicitly returns. The 3D
  viewer is used only when the result format is supported.
- **Interpretation:** confidence is a model output, not experimental structure
  validation, function or binding evidence.

### 3. Generate a few molecules

- **App:** GenMol with the starter recipe's bounded candidate count and current
  live input contract.
- **Produces:** the returned molecules, including exact SMILES where present,
  the run identity and a downloadable result file with input provenance.
- **Interpretation:** generated structures and measured output fields do not
  establish binding, efficacy, safety or synthesizability.

### 4. Transcribe a teaching consultation

- **Input:** the complete public English recording and its supplied human
  reference transcript. The example must not shorten or replace the recording.
- **Produces:** a complete model transcript, timing/segment metadata when the
  selected App returns it, a reference comparison, provenance and download links.
- **Interpretation:** this example evaluates transcription only. It does not
  create a medical report, diagnosis or clinical recommendation.

### 5. Try a synthetic aging-clock example

- **App:** PhenoAge, using only the synthetic laboratory profile and the exact
  units declared by the recipe and live schema.
- **Produces:** the numerical App result together with the complete normalized
  input profile, units, model identity and run provenance.
- **Interpretation:** it is a software and transport example, not an assessment
  of a real person or evidence of biological age or health.

### 6. Segment a teaching image

- **App:** SAM 2 when authorized, with the starter pack's synthetic image and
  declared point/box prompts.
- **Produces:** the operation ID, original input and prompts, complete mask or
  overlay artifacts, and verified download links.
- **Interpretation:** describe only what the returned mask contains. The example
  does not establish clinical accuracy or generalize to an undisclosed modality.

The broader research cards can guide literature review, CT and chest X-ray
research, Cellpose microscopy, single-cell UMAP, generated media, robotics and
other authorized Apps. They are not silently counted as completed starter
examples: each needs its own live schema, suitable data and acceptance evidence.

## Bring your own data

Upload through **Workspace** and tell the agent the resulting `/workspace/`
path. The normal chat attachment picker is not an automatic bridge to scientific
model APIs. Model tools use finalized platform artifacts; let the installed
file helpers transfer bytes rather than pasting base64 or signed links into chat.

For consultation drafts, use **Clinical Report** for a browser-local recording
or transcript, or ask the agent to use an existing workspace transcript. Review
the transcript, citations, withheld facts and questions. Drafts require qualified
human review and are not clinically validated.

**Conversation Evaluation** retains the general MindEval comparison workflow.
It has no event-specific endpoint default. Keep the patient, judge and profiles
fixed for a matched comparison; reported grades are not clinical validation.

## If something takes time or fails

- Queued work may be waiting for a compatible GPU. Watch the existing operation
  instead of launching a duplicate.
- A browser or chat timeout does not mean accepted model work stopped. Use Runs
  to recover the original ID and retrieve its terminal result.
- Whole studies with accepted durable plans can continue after disconnect.
  Ordinary unsubmitted chat plans and arbitrary shell sessions are not durable
  studies. Closing a browser does not turn an unfinished plan into one.
- For an access error, verify the chosen App appears in your authorized catalog.
  Do not use another person's key or an operator token.
- For support, share the operation ID, model, approximate time and bounded error
  message. Do not send credentials, signed download links or private input data.

The portable [Scientific AI skills](https://github.com/rene-tech/serverless-ai-cookbook/tree/main/skills/scientific-ai)
describe the same hosted tool contracts for other supported MCP clients.
