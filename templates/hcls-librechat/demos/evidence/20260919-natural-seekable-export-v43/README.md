# Natural v43 recorded-data export — narrow verified delivery

## Frozen identity and task

Scientist10 used the ordinary browser, same tenant bucket/key and unchanged
DeepSeek-V4-Pro-0813 planner (131072 context, 8192 output, low reasoning).
Source `31ea81371b31a06cc9b7366963dcbcc9f72d7453`; image
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v43-31ea813`, index
`sha256:6b03912b411c32c66bc22bdd1e0962f5c6e168962a5fd8077eae4f1cb0ada554`.
Endpoint `aiendpoint-e00s62sznpcf4h066c`, backend182. Conversation
`521be947-6927-57c3-bc14-27111bd7c494`.

The frozen natural request asked for all recorded non-video ALOHA fields in
compressed NPZ, HDF5, ZIP with portable tables and closed SQLite, with source
comparisons, hashes, report and download links. It named no helper/tool or
expected answer. Prompt SHA256
`c024721e159178571ab27c295318d747e576b28cc174044fed8dac46b87c467d`.
Nine input files / 5,206,730 bytes exactly match the earlier frozen inputs.
No hosted-model inference was submitted; all tools were CPU execution.

## Observed outcome

The agent independently imported the installed `persist_local_file` helper,
wrote/closed the four seek-dependent formats locally and published them to the
real bucket. No seek/rename publication failure occurred. Independent reopening
against the original parquet verifies all nine fields, shapes, values and
original-dtype bytes in every format. SQLite integrity check passes; NPZ entries
are compressed; ZIP uses explicit 0/1 boolean parsing. Original parquet SHA256:
`a8ab6f619dc72f049f53fbc20ed97bd05582e028a3a81f93844bd13076cadc0b`.

Each format contains 128 rows and **6,144 scalar values**: 5,376 action/state/
effort values, 128 float32 timestamps, 512 int64 identifiers and 128 booleans.

| Final artifact | Bytes | SHA256 |
|---|---:|---|
| NPZ | 10930 | `5c4b5d30bfe19a0dcbbdfd25dce80d0bea3159801213fba7dc4b73a08a3e80b0` |
| HDF5 | 36480 | `125150f18c43fce01ba64db8c1bc6e3db0300d5de99a4044b9bcb847ce9751af` |
| ZIP | 19349 | `be2bdc221ecf55b4eca5cb7461412bfc2073cf0d8d3e34f1d12d4fc1525854a2` |
| SQLite | 69632 | `9a126719fd482e6fc42053397b6d834c6a6b75e9f7f1a6a9d75efc84a90c3038` |
| Final comparison JSON | 3117 | `5605973a4d0eeee7b1159d379251c38d2abfa1f1323ce964a384003623e6206e` |
| Final report | 3255 | `d00f3e48f3c412e556e34d78c80ef0ba932f1d38052067e746907787c0ea3666` |

Seven actual browser downloads (these six plus source-reference NPZ) match
independent S3 bytes. Exact model-generated authenticated workspace URLs were
used, then the real Download selected file button. No URL repair or API-only
download was substituted. The URLs are nevertheless fenced text in chat, not
clickable links: navigation required copying/opening them. v44 renderer work is
a separate regression gate and does not change this result.

## Preserved friction and inaccurate claims

First prompt 05:33:31.125 UTC, first response 05:36:03.011. Five preparation
execution jobs failed and were self-recovered: absent pyarrow; optional pandas
conversion unavailable; two incorrect Arrow ChunkedArray `.values` accesses;
unsupported zero-copy boolean conversion. The agent installed needed pyarrow
during its own CPU work; no operator changed the image or coached it.

The first ZIP comparator treated string `"0"` as true. All export bytes were
already correct, but the first turn ended with incomplete verification. One
ordinary continuation at05:37:20.269 requested completion without parser,
count or helper hints. Final response05:38:05.622 corrected the comparator and
cross-checked a fresh source read. Old report/comparison files remain intact.
Total first-prompt-to-final274.497s includes user idle; response intervals are
151.886s and45.353s. There were17+2 execution tool calls; no third prompt.

The first response incorrectly stated5,120 vector values; this was not explicitly
corrected. The final report/chat instead says5,504 numeric values, which counts
only float32 vectors plus timestamps, not every non-video scalar. Correct data
and exact hash tables do not excuse imprecise narrative counts. No universal
scientific-report accuracy, one-turn completion, shared POSIX, live SQLite/WAL
or whole-platform readiness claim is made.

## Receipts

Protected root: `/home/tux/secure-handoff/scientific-qualification-20260918`.
Raw messages: `browser-evidence/scientist-10-v43-{first,second}-final/`.
Original and corrected files retained separately. Independent check:
`browser-evidence/scientist-10-v43-independent/numeric-verification.json`, SHA256
`531847ca05bb41164ca31445d735c6cada1ef149f0fd99efcdc5562f04548cdf`.
Browser receipt:
`browser-evidence/scientist-10-v43-browser-downloads/receipt.json`, SHA256
`de9874bf1b48fdc2265474eda1643b838d59c8c2bf3e0c01f7cc225ecb8b222a`.

The independent verifier's first manifest lookup expected `formats` instead of
the actual `exports` field; that harness-only failure was corrected before
success and is not attributed to the customer workflow. No source/output file
was changed by verification. Endpoint, chats, bucket, keys and original failed
v42 outputs remain retained.
