# Scientific startup comparison — 19 September 2026

This is a three-repetition exploratory comparison of the existing public
scientific-operation paths, not a Fast Start percentile qualification. The
experiment requests fresh worker Pods on existing capacity; it does not empty
node image caches, reboot nodes, or measure cold infrastructure provisioning.
Only disposable qualification tenants' startup preferences are changed, with
revision-checked restoration. Resource and retry limits are unchanged.

## Method and evidence

The committed runner is
[`qualify_startup_modes.py`](../../../scripts/qualification/qualify_startup_modes.py).
The offline, payload-free analyzer is
[`summarize_startup_modes.py`](../../../scripts/qualification/summarize_startup_modes.py),
commit `17e1b17`. Its tests and the read-only worker-node collector tests passed
22 cases. It preserves original verdicts, exact request and artifact hashes,
operation/Pod identities, image IDs, companion images, source-labelled node
driver metadata, restore subprocess timings, and original estimated/unavailable
lifecycle phases. All structure comparisons use identical explicit residue and
chain correspondence; no guessed remapping or hidden equivalence tolerance.

Protected evidence root:
`/home/tux/secure-handoff/scientific-unattended-20260919/snapshots`.
Each model directory has original `comparison.json`, six request directories,
and `analysis-final-v1.json`; the latter also hashes every source it consumes.
Raw inputs, structures, logs and credentials are not published here.

## Results

All 24 top-level requests completed, passed the existing artifact/semantic
gates and same-operation replay checks. All four original tenant startup
policies were restored; the last restoration was at **13:44:15 UTC**.
No extra inference was launched to replace an unfavorable result.
There were eight witnessed restored GPU workers and seven normal-fallback
workers among the twelve requested-restore requests (RFdiffusion uses two
shards/request). ESMFold2 had **no actual restore in this experiment**: all
three requested-restore workers used the incompatible newer driver and fell
back correctly. Its restore compatibility/performance gate remains open.

The following times are **client end-to-end seconds**, including public
admission, queue/worker preparation, inference, collection and verification.
Brackets show observed minimum–maximum, not confidence intervals.

| App | Normal loading, n=3 median [range] | Actually restored workers only | Other requested-restore outcomes |
| --- | --- | --- | --- |
| ESMFold2 | 113.6 [113.2–113.8] | **Not observed** | n=3 normal fallback: 117.0 [116.5–118.1] |
| ESMFold2-Fast | 111.6 [105.4–120.7] | n=2: 113.8 [111.7–115.9] | n=1 normal fallback: 103.9 |
| Protenix v2 | 164.8 [155.3–171.7] | n=2: 140.2 [91.8–188.6] | n=1 normal fallback: 162.0 |
| RFdiffusion, two designs/request | 140.0 [116.9–155.1] | n=1, both shards restored: 119.6 | n=2 mixed restore/fallback: 120.3 and 123.2 |

No end-to-end speedup is demonstrated for ESMFold2-Fast. Protenix has one fast
restored request and one substantially slower restored request: this does not
establish a predictable latency improvement. RFdiffusion's one all-restored
request is promising, but neither mixed-shard requests nor a single observation
qualify a restoration SLO.

### Structure checks and reproducibility

- ESMFold2: all six 247-residue structures parse with finite coordinates.
  Normal-versus-fallback joint Cα RMSDs are 0.00398, 0.00403 and 0.00312 Å.
  None of these comparisons establishes restored-process correctness.
- ESMFold2-Fast: all six 214-residue structures parse with finite coordinates.
  The two restored-versus-normal joint Cα RMSDs are 0.00399 and 0.00468 Å;
  the fallback pair is 0.00288 Å. These are observed agreement measurements,
  not a declared scientific-equivalence tolerance.
- RFdiffusion: both 48-residue design structure files are byte-identical in
  each paired normal/restored-policy request, including mixed fallback runs.
  This proves agreement for the frozen two-design input, not binder efficacy
  or support for every advertised mode.
- Protenix: all six 281-residue/two-chain structures parse, but normal-normal
  joint Cα RMSDs already range from **10.64 to 13.58 Å**. The two actual
  restore-normal pairs differ by 13.51 and 15.54 Å; the fallback pair differs
  by 15.04 Å. Restore-restore differs by 15.85 Å. These results do **not**
  establish reproducibility or accuracy, and they do not isolate restoration
  as the cause. Poor predictions remain in the evidence.

All checked adjacent Cα distances in these four Apps' outputs remain inside
the descriptive 2.5–4.5 Å gross-backbone range. Parsing/geometry checks are not
experimental structure recovery, binding, physical or clinical validation.

### Protenix seed tracing

Every request retains seed 7, the output identifies `prediction.7.0`, and the
normal worker log explicitly reports executing seed 7. The hosted wrapper
passes `--seeds` into the pinned CLI. In upstream revision
`2475421477ab414b571149ad4a875c390ff8a35d`,
[`infer_predict`](https://github.com/bytedance/Protenix/blob/2475421477ab414b571149ad4a875c390ff8a35d/runner/inference.py#L419)
resets the RNGs before iterating over the input;
[`seed_everything`](https://github.com/bytedance/Protenix/blob/2475421477ab414b571149ad4a875c390ff8a35d/protenix/utils/seed.py#L19)
seeds Python, NumPy, Torch and CUDA. The base
[`deterministic` configuration is false](https://github.com/bytedance/Protenix/blob/2475421477ab414b571149ad4a875c390ff8a35d/configs/configs_base.py#L46).
This is evidence against a simply dropped seed, not proof that a particular
GPU operation caused the variation. No runtime, precision, seed or tolerance
was changed, and no extra inference was launched for this diagnosis.

## What the timings do and do not measure

The JSON report separates client wall time, service accepted→completed time,
service started→completed time, producer-defined runtime fields, and individual
restore subprocesses. Lifecycle phase values remain labelled *estimated* or
*unavailable*. They may overlap and are **not** added into GPU compute time.
In particular, `active-compute` is an application lifecycle interval; without
a dedicated inference boundary it can include runtime initialization. It is
not DCGM occupancy or kernel time.

For ESMFold2-Fast the observed artifact-load intervals alone are 36–39 seconds;
actual CUDA restoration is 1.95–3.03 seconds, while CRIU and other preparation
add separate time. A fast CUDA copy therefore does not imply fast end-to-end
delivery. Protenix's long restored r2 records a 105-second image-pull interval;
r3 has no complete image-pull interval, so missing is not zero. The summaries
retain the complete per-call phase records and do not hide this variance in a
single cold-start number.

Every witnessed successful restore here used actual driver `580.159.04`.
Observed `580.173.02` workers rejected the incompatible checkpoint and loaded
normally. This fallback delivered results but is not a restoration success.
Kueue may select a different pool before Pod scheduling; global free GPU count
or a soft Pod preference does not establish compatible capacity availability.
Node labels such as `580.159.04-1ubuntu1` are retained as package metadata, not
silently substituted for an in-container NVIDIA driver measurement.

## Exact runtime and release scope

Observed model image digest suffixes (unchanged within each App's pairs):

| App | SHA-256 |
| --- | --- |
| ESMFold2 | `b372dd7e34e464680a82456ca31b403b0ac0d0851511930d471b67041adbbde3` |
| ESMFold2-Fast | `6eaf386a9bb4453d5048e16c28b8ca4236ae0f222185e33d5a7a49a1e1c8fa35` |
| Protenix v2 | `ac8f7c2c35d2bc911281f9d4a8aa9779e2cb955cdb1c2c2d37eb31d89669980e` |
| RFdiffusion | `f31902e0fbece8e7f823b36e47b79ec02fe0bc545a44131188f9194f13711f19` |

The control-plane companion changed during the campaign from release182
`f3a3d6c2d4e28b6f8693e6cc65c6d9b63ecd4e54e8e13d170059f4e85d0a60f6`
to release183
`7b4356a02429cc5056785b8b67a2b79afabbba023c118dbd1cb30f5cf63ff091`.
For example, Protenix r1/r2 use the former and r3 uses the latter. The source
report retains this per worker: these are not all tests against an unchanged
final platform release. Snapshot helper image
`17cc3536dd847355b8457b2e92bd7d0fdf292bdd8e6acc457e25f14e28284ba4`
is retained separately from the model process.

## Related maintenance-eviction recovery

This is a separate root-owned test, **not another snapshot repetition**:
operation `59cc8d6a-0791-4df6-8695-2d460077366c`, protected
`../worker-eviction-r183`, completed with automatic retry and same-identity
replay verified. Its materialized artifact receipt SHA-256 is
`4818fb8f53cf8abb0fc6d5dbc5e3a91af0ed797b68e13a8c8ba9ba547b562a15`.
Independent parsing confirms 247 Cα/1,870 atoms, finite coordinates, and
adjacent Cα distances 3.766–3.886 Å. Jointly fitted RMSD against ESMFold2's
first normal comparison result is 0.00393 Å. The earlier interrupted attempt
remains retained; this does not qualify every provider-preemption mode.

## Next evidence needed

1. Distinguish compatible snapshot capacity from ordinary fallback in customer
   startup expectations. Qualify a checkpoint for a new driver or an explicit
   compatible-pool policy before promising restoration there; do not weaken
   identity checks.
2. Measure and address initialization/artifact/image preparation separately
   from CUDA copy speed. Preserve fallback usability while doing so.
3. Diagnose Protenix normal-mode reproducibility with controlled environment
   and feature/RNG evidence before advertising seeded replay equivalence.
4. Only after these exact tuples are settled, run the required twenty-sample
   activation qualification and broader inputs. This n=3 experiment does not
   assign or upgrade a Fast Start level.

## Protected analysis hashes

| File, relative to the protected snapshot root | SHA-256 |
| --- | --- |
| `esmfold2/analysis-final-v1.json` | `2525da8a9467972befb8a7b854f604a6f9f0d8e2fc1dd12db4d64e1a9be0560e` |
| `esmfold2-fast/analysis-final-v1.json` | `23163a9e22ca89a85ed6abddc1b64d0d14416d9cd6fbb469b7286c92f4158587` |
| `protenix-v2/analysis-final-v1.json` | `c2e7543443211c6d64f40050d2d58cf26a58f7a8158a61e4aed8d91980a8918c` |
| `rfdiffusion/analysis-final-v1.json` | `c2f2a041a616f8054221bfdc886194ef9a1420e18b9fae3825cf770b23c2729a` |
