# Rene personal speech-demo endpoint — 18 September 2026

## Scope and identity

One new personal instance, explicitly requested by Rene. The existing Stockholm
endpoint and its users, Mongo data and conversations are not replaced or migrated.
This is not completion of the separate Porto workshop acceptance task.

- Task Deck: `fs2-librechat-rene-bucket-demo-r20260918`.
- Source: `rene-tech/serverless-ai-cookbook`, branch
  `agent/librechat-scientific-branding`, image source commit `cb13e8c`.
- Endpoint: `aiendpoint-e00nkx6mf6qwvwsfkp`,
  `scientific-rene-speech-20260918`.
- Project: `project-e00rene`; region: `eu-north1`.
- CPU D3, `4vcpu-16gb`, 100 GiB network SSD, regular CPU capacity.
  Speech inference uses the existing Scientific AI model platform; no new GPUs.
- Image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0918-cb13e8c`.
- Verified registry digest:
  `sha256:bfa1ad766597366aa46f76c6380172ddb9d5e831fab9867418519319fd196fea`.
- Login: `rene@nebius.com`; open registration disabled. Fresh Mongo, not copied
  test accounts. Existing Scientific AI `rene` / `rene` key `internal-test` reused;
  no key, tenant, S3 identity or quota was rotated/created/raised.
- Credentials are outside Git under the protected local deployment handoff and
  a deployment-scoped MysteryBox secret; never include their values here.

## Storage

The already provisioned bucket `fs2-data-bucket-081a89fb4b12bf2194ad340d` is mounted
by the Serverless endpoint at `/workspace`, read/write, using Rene's S3 identity.
Its legacy immutable name is preserved. Mongo and encrypted credentials stay on
the endpoint disk; the bucket is not a database filesystem.

Copied prefix: `demo-assets/medical-speech-en-de-20260916/`.

- Five complete prepared WAV recordings: two English PriMock consultations and
  three German HHU recordings (Herzrasen, grippaler Infekt, Polyarthritis).
- Four English human-annotated TextGrid files and two clinical notes, with source
  and licence/attribution documents.
- Five generated Nemotron transcripts from the retained 17 September report
  acceptance, explicitly under `generated-transcripts/`, not human references.
- README, source manifest and checksums. The source checksum file covers the
  original larger bundle; `UPLOAD-INDEX.json` describes the curated uploaded set.
- 26 files, 80,870,905 bytes, plus the upload index. All 26 were downloaded back
  through S3 and matched SHA-256. No existing different objects were overwritten.
- No verified human German ground-truth transcript is claimed.

## Verification progress

- 33 Python regression tests passed for rendering, deployment contract,
  execution and structure viewing; seven demo lifecycle/comparison tests passed
  inside the runtime image.
- Initial host test invocation could not import `httpx2`/`typescript`; the
  changed renderer/deployment tests passed on the host and Node demo tests were
  rerun successfully in the image with its actual dependencies. The unrelated
  native-file client suite was not part of this increment's acceptance.
- Initial create failed before an endpoint existed because the AWS default
  configuration profile was absent. Added a private task-local, non-secret
  profile containing the correct S3 endpoint and region; credentials remain in
  MysteryBox.
- A digest-based create then failed provider Compute label validation (131
  characters against 64 allowed). A new short unique tag resolves to the exact
  tested digest. No old tag moved and no quota was changed.
- The endpoint reached `RUNNING`; public TLS health returned HTTP 200 with
  certificate verification result 0. The authenticated browser showed the
  personal Rene account, configured platform key and both completed jobs.
- The endpoint read all 26 indexed objects from `/workspace` over its FUSE mount,
  matched SHA-256 in 1.45 seconds, wrote `STORAGE-CHECK-20260918.json` through
  the mount, and that object was read back independently through S3.
- A real chat used `environment-execution` to inspect the mounted path. After
  correctly discovering the language subdirectories it listed all five WAV
  names and returned count 5 (execution job
  `6fa23cbf-5322-421a-ac93-815e2c2972b7`); no model job was launched by that
  storage-only check.
- Complete public clinical workflows passed with fresh requests:
  - German `hhu-herzrasen.wav`: job
    `f41e9262cfcfb2f2d4eddca51432ab23`, completed in 99.384 seconds.
  - English `day1_consultation01_conversation.wav`: job
    `e1b84649ccc2fb9f7bf31f910329c4e5`, completed in 161.263 seconds.
  - Both produced and downloaded nonempty `transcript.txt`, `report.md`,
    `follow-up.md`, `review.md`, `document.json`, `review.json` and `run.json`.
    These are complete workflow times including queue, not cold starts or a
    clinical-quality result.
- Recent endpoint logs contained no warning/error lines. The initial browser
  login-page load logged the expected unauthenticated message before protected
  session state was loaded; the authenticated panel and chat subsequently passed.

## Limits and preservation

This is a personal instance of the existing root-execution workbench, not a new
multi-tenant sandbox. The clinical panel supports recorded-file upload and
transcripts; it is not a live microphone client. Its file picker selects local
browser files, not server mount paths. Mounted files are accessible through the
workspace/file tools. Draft reports require clinician review; full-file workflow
success is not clinical validation.

Keep the endpoint running for Rene. Before any later replacement, preserve its
`/data`, `/app/uploads`, runtime encryption keys, clinical jobs and conversations.
Keep the tenant bucket and original Stockholm endpoint unchanged.
