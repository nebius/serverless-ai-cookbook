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
