# Natural genomics delivery — v56

On 2026-09-19 UTC, scientist06 completed one unchanged natural study request
without a follow-up. This is an exact-client acceptance result, not a
platform-wide or biological qualification. The earlier v54 analysis failure
remains preserved in [the repair record](../20260919-genomics-analysis-repair/README.md).

## Frozen identity and actual delivery

- Client source: `cba6304ec772a70cc7fccf44743145b0a7e3a479`.
- Client OCI index: `sha256:7b5b3b46713b61fd5fafc8085fa29fd8fc54f631a993c1aa28c4aa7d9e842c3c`.
- Backend190 source: `c154d77654a16b5cfdf732f505467ac981b6479f`;
  index `sha256:e4319840c1d9378c2942f2e389785917e045af4b5733f93da3b535c3f33e3dad`.
- One frozen r8 prompt; unchanged Kimi-K3 low, 131072 context, 8192 output.
- Study `537964be-6afa-5b2c-9c9a-4af14e3eb00c`: 14 completed phases,
  including 12 fresh Evo2 calls, typed `evo2-continuation` analysis, and report.
- Browser closed at 19:26:30.761837 UTC only after a fresh observation of this
  exact ongoing Study. Accepted-to-finished duration: 403.874 seconds.
- Actual Runs artifact links followed by **Download selected file** delivered
  all five final files (101334 bytes). Each matched both the published SHA-256
  and independently downloaded Object Storage bytes. API downloads alone were
  not counted as UI delivery.

## Independent checks

The independent verifier reused its frozen v54 method, not the report helper's
calculations. All twelve requests exactly matched the supplied Arabidopsis
chloroplast reference windows: starts 1000/15000/35000/60000/90000/120000,
256-base prefixes, 64 generated bases, seeds 1/7, temperature 0.7, top-k 4,
top-p 0.95 and unchanged telemetry flags.

All outputs contained 64 ACGT bases. CSV and Markdown tables matched independent
GC counts, reference matches, seed comparisons, sequence hashes, original
operation IDs and exact milliseconds-to-seconds conversions. All 37 analysis
source hashes, 74 declared phase files and 285 snapshot files were verified.
The report preserved original requests and returned operation/runtime identity.

Mean generated-suffix GC fraction was 0.3580729167; mean positional reference
agreement was 0.984375. Five seed pairs were identical; the remaining pair
differed at 2/64 positions. Model-reported time ranged from 2771.702974 to
2897.389579 **milliseconds**, separately from the whole-study wall time.

These are descriptive generation measurements, not reference likelihood,
variant-effect scores, functional validity, independent sampling, or paper
replication. Training-data overlap is unknown. The report's representative
operation telemetry is labeled separately; estimates/reservations do not prove
GPU occupancy, and missing values remain unavailable.

## Protected reproducibility references

`U` denotes the protected `scientific-unattended-20260919` campaign directory;
these references contain no credentials or private payloads in this repository.

| Evidence | Protected path under U | SHA-256 |
| --- | --- | --- |
| Independent final acceptance | `independent-v56/scientist-06-final-receipt.json` | `f9f754041af43623bee20412a07aa9d80ac3ae5956e9e16afc749cb77ae7cdee` |
| Independent numerical check | `independent-v56/scientist-06-numerical-r1.json` | `c40a0e4777a34d22b72bd0f71c58e337c412dcb27d24f882491b0906daae808c` |
| Exact object snapshot | `independent-v56/scientist-06-s3-20260919T193450857470Z/receipt.json` | `2b5f56737f2266bb8c2ffa4f001cd5e3a5d818d16bbc1e7b51ebf1fbc05344da` |
| Final report | Published `report.md`, mapped in final receipt | `946f5c9cf68334e73367fbe273d8bc0a9764f60fc9bd39275101a8aac80a4055` |

The final receipt links the current Study body, full UI download receipt,
disconnect witness and all five outputs. No additional inference was submitted
by verification. This success does not replace other personas' v56 failures or
qualify a later image automatically.
