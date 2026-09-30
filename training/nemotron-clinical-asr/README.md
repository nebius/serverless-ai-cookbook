---
title: Fine-tune English Nemotron Speech from your bucket
category: training
type: job
runtime: gpu-h100-sxm
frameworks: [nemo, pytorch]
keywords: [speech-to-text, finetuning, object-storage]
difficulty: intermediate
---

# 1. Your labelled audio → a fine-tuned checkpoint

Fine-tune [English Nemotron Speech 0.6B](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b)
in one finite Serverless Job. You supply audio **and human/reference transcripts**;
the recipe does not invent labels. Use only data you are authorized to process.

## Three steps

1. **Prepare your bucket:** `train.jsonl`, `validation.jsonl`, and `audio/`.
   Each manifest line has this shape:

   ```json
   {"audio_filepath":"audio/visit-001.wav","text":"The original spoken words.","conversation_id":"visit-001"}
   ```

   Supply complete, labelled **0.5–30 second, mono 16 kHz PCM16 WAV** segments.
   Split whole conversations between training and validation; keep your final
   test set separate. No forced alignment, dataset download or audio-only magic.
2. [![Create Job](../../templates/assets/create-job.svg)](https://console.nebius.com/serverless/job/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fnemotron-speech-train%40sha256%3A1a5756455cb3f6a763887511df205648cf1c53afbfc694d0ae6c0f605cb85f67&platform=gpu-h100-sxm&preset=1gpu-16vcpu-200gb&preemptible=false&command=python+%2Fopt%2Frecipe%2Ftrain.py&volumeMountPath=%2Fdata&volumeSize=100)
   The button prefills the public image pinned by digest and its command.
   Select your project, attach the bucket read/write at `/data`, and review
   the form before creating. Start with one H100/H200, 16 vCPU, 200 GB RAM,
   100 GiB container disk and 8 GiB shared memory. The default is 500 steps;
   override the command with `python /opt/recipe/train.py --steps 1000` if needed.
3. **Get the result:** your bucket contains `runs/<unique-run-id>/model.nemo`,
   `model.sha256`, `metrics/`, and a final `result.json`. Only a checkpoint with
   finite validation WER is exported. Use that output folder in
   [recipe 2: deploy stock or fine-tuned speech](../../templates/endpoint-nemotron-speech/README.md).

**Validation scope:** CPU tests and imports passed for these recipe images.
No new GPU training or endpoint validation was run; validate your own data and
deployment before relying on results.

Validation WER selects an export; it is **not clinical validation** or proof that
your fine-tune improves every use case. Review held-out results before use.
Check the [NVIDIA Open Model License](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b/blob/main/LICENSE)
before redistributing weights. No private demonstration checkpoint is included.

## Optional: build and inspect the source

```bash
docker build -t YOUR_REGISTRY/nemotron-train:YOUR_VERSION .
docker run --rm --network none --entrypoint python \
  -v "$PWD:/tests:ro" YOUR_REGISTRY/nemotron-train:YOUR_VERSION \
  -m unittest discover -s /tests -p 'test_*.py'
```

The Dockerfile pins public PyTorch/NeMo and a checksummed dependency lock from
the [preserved engineering source](https://github.com/rene-tech/serverless-ai-cookbook/tree/db9e31e3ce4f760804b448a846101797111594fa/training/nemotron-clinical-asr).
The small `train.py` here is the actual recipe, not a call into the old workflow.
Use an immutable image digest when creating jobs. No training is run by tests.

**Troubleshooting:** wrong format/split fails before GPU imports; permission
errors require a writable bucket mount; missing `result.json` means no completed
export. A failed job never resumes or overwrites another run. Delete only your
finished Job/VM when no longer needed; keep the output bucket/checkpoint.
