# Public inputs and provenance

No audio, patient records or generated checkpoints are included in this recipe.
Downloads below are public; review source terms before redistribution.

| Input | Public source | License and use here |
|---|---|---|
| Simulated medical interviews | [Figshare collection](https://springernature.figshare.com/articles/dataset/Collection_of_simulated_medical_exams/16550013), [publisher metadata](https://api.figshare.com/v2/articles/16550013) | CC0. Role-play English conversations; clinical train/dev/test split before alignment. |
| General-English replay/regression | [LibriSpeech, OpenSLR12](https://www.openslr.org/12/) | CC BY 4.0. Train-clean-100 for replay only; test-clean for regression only. Attribution: Vassil Panayotov, Guoguo Chen, Daniel Povey and Sanjeev Khudanpur; read LibriVox audiobooks. |
| External clinical sample | [PriMock57](https://github.com/babylonhealth/primock57), revision `cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5` | CC BY 4.0. Evaluation only. Attribution: Babylon Health; Papadopoulos Korfiatis, Moramarco, Sarac and Savkov (2022). The downloader selects two consultations, not the full 57. |
| Optional adaptation corpus | The same pinned [PriMock57 source](https://github.com/babylonhealth/primock57/tree/cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5) | CC BY 4.0. A separate fixed40-train/5-dev subset excludes the two sample cases and ten reserved external consultations below. Not the evaluation sample reused as training. |

`download_public.py` pins SHA-256 for all archives and PriMock audio. The archive
SHA-256 values were independently computed from the original public downloads;
Figshare also publishes MD5 `9c79f2050dbdaf13fb1c2c5d38587d60`. LibriSpeech's
publisher MD5 values are `2a93770f6d5c6c964bc36631d331a522` (train-clean-100) and
`32fa31d27d2e1cad72775fee3f4849a9` (test-clean). PriMock WAV hashes are the pinned
Git LFS object IDs; license and TextGrid files are verified against pinned Git
blob identities, with SHA-256 recorded after download. A Git LFS pointer is not
an audio recording.

Preparation retains licenses, source hashes and changes. For CC BY inputs,
preserve source attribution and license references, and identify preprocessing
when sharing derived material. Keep the original PriMock license with excerpts.
Model/checkpoint redistribution has separate model-license obligations.

The clinical archive has 272 audio/transcript pairs and measured 51.910 hours of
audio, rather than the approximately 55 hours in the source description. Its
cleaned human transcripts have no timestamps and are not certified verbatim.
Two original files use UTF-16; the parser detects BOMs instead of embedding NULs
in training text. Continuation/uncertainty warnings remain in provenance.
Conversation splits are not actor-disjoint; original model pretraining overlap
is unknown. Public defaults use explicit reproducible seeds, not hidden local
split files. A different seed creates a different experiment.

Forced alignment only assigns times to the supplied words; it cannot establish
that the words are correct. Listen to selected examples and keep clinical review
status explicit. PriMock clips use original single-speaker-channel TextGrid
intervals; they do not qualify mixed-channel diarization. The LibriSpeech
duration filter excludes utterances outside 0.5–30 seconds; report omissions,
not an unfiltered-corpus claim. No preparation script establishes medical
accuracy, model improvement, clinical safety or PHI suitability.

## Optional PriMock adaptation inputs

`prepare_primock_adaptation.py` consumes only the original public WAV and human
TextGrid files. The accompanying `primock_adaptation_sources.json` contains
public source hashes, sizes, revision and attribution—not recordings or
transcripts. All90 speaker-channel WAVs/TextGrids plus the license are verified
before any clips are written. `--download` is explicit; omit it for offline use
with a source directory containing `audio/`, `transcripts/` and `LICENSE.md`.

```bash
python data/prepare_primock_adaptation.py \
  --output-root ./clinical-data/primock-adaptation \
  --container-root /data/clinical-speech/primock-adaptation \
  --download
```

The fixed excluded consultations are `day1_consultation01`,
`day1_consultation02`, `day1_consultation06`, `day1_consultation13`,
`day2_consultation05`, `day2_consultation10`, `day3_consultation04`,
`day3_consultation07`, `day4_consultation06`, `day4_consultation09`,
`day5_consultation01` and `day5_consultation02`. They must not enter either the
adaptation train or development manifests. From the remaining45 consultations,
one development consultation per day is selected by the smallest
`SHA256("primock-adaptation-v1:20260926:" + conversation_id)`; the rest train.
This selection does not inspect hypotheses or select favorable passages.

The resulting membership is40 train/5 dev consultations, with3,118 train clips
(11,303.8425 seconds) and389 dev clips (1,450.446375 seconds). These are filtered
single-speaker human intervals, not the duration of45 complete consultations.
Empty, angle-bracket-marked and out-of-range intervals are reported as omissions.
The0.5–30-second filter uses rounded16k sample coordinates; retained PCM is
copied exactly without resampling or text repair. Original casing/punctuation,
source coordinates/hashes and CC BY4 attribution remain in the manifests and
`provenance.json`; `LICENSE.md` accompanies the outputs.

Keep these training/development examples separate from external evaluation and
sealed final inputs. Conversation separation is explicit; actor/speaker
separation and upstream pretraining exclusion are **not established**. Prior
evaluation/demo exposure is not a claim of blindness. These speaker-channel
clips do not establish diarization or clinical correctness. Neither prepared
audio nor a successful training smoke constitutes an efficacy result.
