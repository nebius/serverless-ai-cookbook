# v59 design/refold failure and bounded coordinate preflight repair

The actual v59 scientist04/r11 Study **failed** after all three model operations succeeded. This is not natural customer completion or a release-readiness pass. The original plan, journal, files and conversation were not repaired or resubmitted.

## Original customer-shaped evidence

- Client source `a996ce38e21bb4a31e6545f22b3c32ca0465d960`; published OCI index `20748e8b3ace7552cd3a340959bf024f9064435b8eaa87e0c56f94b948590e73`; endpoint `aiendpoint-e00va0nnnepa97pkfe`.
- Remote SSH/per-file runtime-hash binding was unavailable because creation omitted an SSH authorized key. Root explicitly limited this to one targeted fix-validation Study; the published-image installed/local proofs do not replace missing remote per-file proof.
- One frozen prompt, no followup or additional inference. Study `b4eb491e-a703-5baf-8a11-5ba18475f0f9`; conversation `0cef82b6-999f-5fda-8dae-20fa4e17e4ec`. Browser saved state and disconnected while running at `2026-09-19T22:15:44.747422Z`.
- Model operations RFdiffusion `5941287f-7fcf-4a55-8b83-d9995056a6c3`, ProteinMPNN `5d9c7a09-23db-4f88-98ea-d5af06160f8c` and ESMFold2-Fast `ad861761-9b4a-4aba-8ad6-87a51a151741` all succeeded. Four input uploads succeeded. This does not qualify the requested final analysis/report.
- The engine failed at `correspondence`, 5/8 phases complete, with `ValueError: Selected coordinates need one exact matching entry in their recorded operation manifest.` No final report or metrics were published. All 36 registered files of the completed phases match their retained bytes/hashes.
- The final assistant message was model-authored admission prose, not the intended concise deterministic acknowledgment: it stated the correct Study/running phase and that results were unverified, but offered only prose navigation rather than a Runs hyperlink. Its planned counts were not completed results. Historical context was optional in the prompt, so its absence is not an independent failure.
- At `22:26:11Z`, the actual Runs card showed the failure and 5/8 phases. Two raw ESM files downloaded through the normal Workspace UI and matched retained SHA256/size. These are partial artifacts, not final deliverables. Latest browser state was saved and the actual browser closed at `22:26:54Z`; no password login, cookie-cache merge or scientific intervention was used.

## Confirmed semantic mismatch

The saved plan guessed `output-01.artifact` for two future coordinate inputs. That index happened to identify the RF backbone, but identified **confidence JSON**, not coordinates, for ESMFold. The same-operation coordinate guard correctly refused the latter. No corruption or coordinate-byte normalization defect was found.

| ESM manifest entry | Actual semantic type | Bytes | SHA256 |
| --- | --- | ---: | --- |
| 0 | `protein-structure-mmcif/v1` | 34170 | `7204b08857f28d36c4d9cd6017da8f1e2d1f5259e335f70aa62a0556e8adfc2d` |
| 1 | `structure-confidence-json/v1` | 596 | `5ba5eac1b967b3957333e434feedb2769c5e47aa43ffb4b120b208f44541247f` |

The raw same-operation confidence row identifies coordinate SHA/size, seed 1 and sample 0. It contains `plddt_mean=0.720092236995697`, `ptm=0.4071556031703949`, and `iptm=0.0` in their original scales. **None reached the original saved metrics or visible final report, because those outputs do not exist.** These are model confidence, not reference agreement or biological efficacy.

## Source-only repair and offline proof

The admission validator now rejects future batch `output-NN.artifact` references only in the existing manifest-capable `proteinmpnn-input.backbone` and `design-refold-correspondence.prediction` arguments. The same discovery/schema guidance directs an explicit `output-manifest.json` reference and `structure_index`. No index is substituted, and no guessed coordinate is admitted. Materialized inputs, guaranteed preparation outputs, raw non-coordinate references and deliverables remain supported. `structure-analysis.py` behavior is unchanged; no unsupported manifest-as-reference guidance was added.

The exact original plan fails preflight before any admission. An independently copied offline plan changing only those two references to manifests replays all five deterministic local phases against the original three verified successful operation records. ProteinMPNN input/backbone and ESM input/parameters/selected-sequence hashes stay unchanged. The replay verifies 48 mapped residues, the exact original selected coordinate bytes, raw confidence bytes and unique sample provenance, and confidence values appearing in the offline metrics and assembled report. It neither invokes a model nor writes the original workspace/Study. This explicit offline plan correction is **not** evidence that an uncoached successor planner will choose it.

`test_future_coordinate_contract.py` has 13 focused cases, including both exact retained-plan tests. The final source-overlay container run used `--network none` and passed **97 tests, zero skips**, including retained v58 geometry-preservation coverage. Ruff and diff checks passed. Earlier development attempts lacking local MCP dependencies, and the first run without the optional v58 mount, remain retained; they were not runtime failures and are not the final gate. An immutable successor-image gate and new natural acceptance are separate, still-required evidence.

## Protected evidence index

Paths below are relative to the protected `scientific-unattended-20260919` handoff root; no payloads, credentials or signed URLs are copied into Git.

| Receipt | SHA256 |
| --- | --- |
| `natural-v59/scientist-04/terminal-detail.json` | `7b7121b0e2962f3928fbd657a8f270d6da05808a0d05f3c7033d82538c67fa2f` |
| Exact saved plan under snapshot `workspace/scientist-04/unattended-20260919-r11/design-refold/plan-draft/revisions/0a3f4b17c347533597b1ca26bf6819400867ec90ce318a4a0831217e15b2bb40.json` | `0a3f4b17c347533597b1ca26bf6819400867ec90ce318a4a0831217e15b2bb40` |
| `independent-v59/scientist-04-s3-20260919T222116476143Z/receipt.json` (174 files / 447086 bytes) | `c94ab5cfec5daa432a19934a30b4a9ddb16dfe2b0db6a255b05f80df8a203536` |
| Same snapshot `listing.json` | `b6a8d1f938e5173b4b2805468acc0e1a4144af03b355efa9762c75cb0e717d2f` |
| `independent-v59/scientist-04-browser-r1/partial-download-receipt.json` | `02b7da958274edf6a0193927648f8b85685030b2611495fe8a430d712e697fd3` |
| Same browser folder `07-final-state-save.json` | `7b517c5b2dbd98d341ee74629fd14a44a19ff25ac95fc72fdb8d99ede3eb7f2a` |
| Same browser folder `08-final-close.json` | `5872093002c529648891c4b24a7614bfdc488485fb80d344b51ecb7b874e2f06` |
| `v60-coordinate-source-tests-r4/tests.xml` | `9e80040cc5ce84295e9307f36cda453dc0458a3741258ab29750e64b2f0b6bbb` |
| `v60-coordinate-source-tests-r4/execution.json` | `0bb42fd7ddd96c785671ec5ef05ffa9d79ecd1462061b6931e87dc51d60f523c` |

The actual remote outcome remains failed. No endpoint lifecycle action, runtime deployment, model rerun or repair of the original outputs occurred in this verification/fix lane.
