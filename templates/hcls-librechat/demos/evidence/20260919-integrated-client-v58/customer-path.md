# v58 customer-path results — partial deployment, not release acceptance

Four separate user instances ran the unchanged r10 scientific requests on the
source/image identities in [the integration record](README.md). Each received
one initial prompt. All four studies continued after an observed running-state
browser closure, finished, and delivered their promised files through the actual
Runs → Workspace download controls. No operator continuation or repaired output
is counted as an original success.

| Scientist / workload | Actual result | Verified UI downloads |
| --- | --- | --- |
| 04 — design and refold | Three inference operations and geometry checks passed, but saved metrics/report omitted available confidence. **Reporting failure.** | 16 / 220,608 bytes |
| 05 — docking and generation | Five operations; independent pose/molecule calculations, report and delivery passed. Poor docking poses remain visible. | 8 / 95,518 bytes |
| 07 — aging clocks | Four operations; independent calculations and report passed. Pending chat incorrectly described 16 overlapping samples instead of one. **Narrative failure.** | 8 / 57,089 bytes |
| 10 — Cosmos video and LeRobot | Native transfer and dataset augmentation, data integrity, four exports and delivery passed. Visual changes extend beyond lighting; exact object/geometry preservation is **not established**. | 14 / 3,692,502 bytes |

These are distinct scientific/delivery/interpretation outcomes, not four clean
customer passes. Study durations for 05/07/10 were 129.304 / 95.710 / 314.965
seconds respectively; these are whole-study times, not cold-start or GPU time.

## Original defects and retained evidence

04 referenced the exact batch coordinate file directly when preparing residue
correspondence. That path retained coordinates but lost the same operation's
manifest/confidence envelope. Actual seed 1, sample 0 native values were
`plddt_mean=0.7201420664787292`, `ptm=0.40709733963012695`, `iptm=0`.
Neither the saved empty confidence dictionary nor the report's zero retained
fields represented those results. The original files remain unchanged.
The 48-position mapping and independently checked 1.7464100723523615 Å RMSD
are separate from confidence and do not establish biological quality.

07's false count appeared in its description of planned stages, before the
study finished—not as a completed measured result. It nevertheless contradicted
the actual one-sample/original and sixteen-sample/reversed inputs. The later
deterministic report correctly records one overlap, 32 PhenoAge rows, 17 AltumAge
predictions and four negative predictions. Correct files do not erase bad chat.

10 preserved all 128 rows/6,144 nonvideo scalars, field types/bits, episode IDs,
timestamps and untouched wrist-camera bytes/decoded pixels. All four NPZ/HDF5/
ZIP-CSV/SQLite exports reconstructed the original columns. Bounded visual review
found a cup recolored red, new green tabletop marks and changes to fine gripper/
material appearance. Numeric preservation and generic report warnings do not
prove a lighting-only transformation or physical/action validity. One mistaken
Study-ID operation lookup recovered within the original turn and remains logged.

Protected receipts relative to `scientific-unattended-20260919`:

- 04: `natural-v58/scientist-04/final-verdict.json`, SHA256
  `b4d255b2e25e2ee8daa3f34153b9979ec5917730b76ae3b71b9db33b06ee6b48`; actual
  downloads in `independent-v58/scientist-04-browser-r1/download-receipt.json`.
- 05: `independent-v58/scientist-05-final-receipt.json`, SHA256
  `15ef75e302ffb2558adbba15dd09ee56bdd66db0dc64e7916b92ce2e60cdff01`.
- 07: `independent-v58/scientist-07-final-receipt.json`, SHA256
  `538576b463227724f722292902ec5374a5056138bcc4a1987c58777dace02d37`.
- 10: `independent-v58/scientist-10-final-receipt.json`, SHA256
  `7f43f2b7218cdd5daf9e20c4e1c2dc0a3f05a61a1e0f7afdcb8f03a7303d17f0`.

## Deployment blocker and successor

Six v58 creations (01/02/03/06/08/09) returned provider `Internal`; a complete
project inventory confirmed no corresponding endpoints. Original command
receipts and request/trace IDs remain in `v58-create-reconciliation-r1`.
Four available public-IP slots at a later read do not establish the cause of
those Internal responses. No quota or policy limit was increased. Serverless
exposes no image-update operation in the checked endpoint service; restarting
an older instance would not deploy this image.

The provider reports state 9 during image pulling in its current
[endpoint schema](https://github.com/nebius/api/blob/main/nebius/ai/v1/endpoint.proto).
The installed CLI printed that numeric value. 04's initial binding waited until
a fresh RUNNING observation, retaining the failed early read and unchanged
acceptance conditions.

Four fully archived superseded v57 test endpoints were deleted and confirmed
NotFound (51 retired previews cumulatively). Three older test endpoints remain
stopped after rejected deletions. Their archived evidence and all buckets are
retained; no customer endpoint was deleted. Removed endpoint IDs/local databases
are not rollback resources.

The successor repairs direct-coordinate metadata binding and deterministic
pending-study acknowledgement. It requires its own immutable image, installed
tests and fresh customer paths; these v58 results cannot qualify it. Backend190
remains deployed with gateway3/3, controller2/2 and admin2/2 at the latest check.
Rene's original client is unchanged. Complete ten-user qualification and his
state-preserving cloud cutover remain outstanding.
