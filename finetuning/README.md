# JAI local fine-tuning preparation

Status: two QLoRA runs trained on Colab and merged locally (`jai-candidate`, best so far; `jai-candidate-v2`,
worse, see RESULTS.md). A third run (`jai-candidate-v3`, data rewritten to follow `facts.guide`) followed. Round-4 data
(`data/CHANGES-round4.md`) is approved and exported as `exports/reviewed-v4`, not yet trained. Not deployed: the app still uses qwen2.5:7b-instruct.
Review approvals were a bulk owner approval.
The running Ollama model and application configuration are unchanged.

## What this dataset is

402 fictional, agent-authored draft examples in 123 families, English/Arabic/Egyptian Arabic.
317 training rows and 85 held-out rows; all paraphrases from a family stay together.
Tasks match four production model interfaces: operation selection, argument preparation,
the small teaching semantic frame, and **conversation** (216 rows, 64 families in `conversations.py`).

Conversation answers state JadwAI facts only from the verified guide (`backend/app/assistant_guide.py`) that
production puts into the prompt as `facts.guide`, or from the scenario facts. `GUIDE_TOPICS` in
`conversations.py` lists the guide topics each family relies on, and the builder fails if any wording's
prompt lacks one. The `not-sure-*` and `notifications` families teach saying "I am not sure" (or a verified
"no") when the guide does not cover a question.

Conversation rows teach JAI to talk things through: explain how JadwAI works, answer from the
timetable facts it is given (a fictional Draft 3 for one group, a stale published timetable,
an exam draft, an empty workspace), reason about trade-offs, ask one focused question when a
request is vague or a name is unknown, follow pronouns and corrections across turns, hold its
ground politely when the user misreads the data, and reply in the user's language. Each prompt
is built by the production `facts()` code and a test runs every row through the real
`converse()` to prove the model sees exactly what the live chat sends. The builder refuses
replies over 80 words, in the wrong language, or exposing internal IDs or API paths.
None of this establishes research quality; the rows still need human review.
The test families are an engineering holdout, not a statistically representative benchmark;
related concepts still exist across families. More diverse independently reviewed data is needed.

No existing research corpus, reserved labels, live chat history, account credentials or
student data is read. The examples use fictional IDs; changing facts must be supplied at runtime.
This work does not replace the older evaluation protocol or resolve its pending human reviews.

## Local commands (project root)

Use the project's backend environment. Source `.env` privately if its database URL is needed
for app imports; the builder imports route definitions but never connects to the database.

```sh
backend/.venv/bin/python finetuning/build_dataset.py
backend/.venv/bin/python finetuning/toolkit.py validate
backend/.venv/bin/python finetuning/train.py --check
backend/.venv/bin/python -m pytest finetuning/test_toolkit.py -q
```

Building regenerates draft data and review templates. It invalidates approvals if content changes.
`data/manifest.json` fixes file hashes; each row and family has a content hash.

## Human review before training

Read `data/REVIEW.md` together with the actual contexts/messages in the JSONL files.
Copy `data/review-template.json` to `reviews.local.json`. For each family, verify every
wording, task, context, exact target, and language. Enter your own reviewer label, rationale,
and `approved: true` only when correct. Do not use an AI to claim a human review.
Edit incorrect labels in the builder, rebuild, and repeat review. A changed family hash
invalidates its approval. Reviewing test labels does not permit putting them into training.

```sh
backend/.venv/bin/python finetuning/toolkit.py export \
  --reviews finetuning/reviews.local.json --output finetuning/exports/reviewed-v4
```

Export requires approved training and test families. Only approved rows are exported.
Outputs use TRL conversational prompt/completion format; loss is on the completion only.
No production credentials or actual personal data should be added to this repository.

## Baseline on this Intel Mac

Ollama must already be running. Evaluation contacts only `127.0.0.1:11434/api/chat`;
no website API operation is executed. One wording per held-out family is tested by default.

```sh
backend/.venv/bin/python finetuning/toolkit.py evaluate \
  --model qwen2.5:7b-instruct --task frame --limit 3 --timeout 150 \
  --output finetuning/runs/baseline-frame.jsonl
```

Repeat with `--task selection` or `--task arguments` to test those interfaces. Run directories
are ignored by Git. Outputs record latency, JSON schema validity and exact semantic field
match. Reply quality, task completion, permissions, and tool execution are not evaluated by
this runner. Draft labels must not be reported as gold accuracy. Compare base and tuned models
on the same cases and settings after genuine label review. Use a validation split from training
families for tuning, and reserve test families for final comparison.

## Free GPU path (Google Colab or Kaggle) — recommended

1. Review and export on the Mac (above), then zip the export:
   `cd finetuning/exports && zip -r reviewed-v4.zip reviewed-v4`
2. Open `finetuning/colab_train.ipynb` in Google Colab (File → Upload notebook) with a T4 GPU
   runtime, or in Kaggle with GPU and Internet enabled. Run every cell and upload the zip when asked.
   It uses Unsloth (QLoRA, 4-bit, 6144-token context, loss on JAI's final answer only),
   about 30–60 minutes of training, then writes a `q4_k_m` GGUF and a small LoRA zip with
   `training-provenance.json`. Only the reviewed fictional rows leave the Mac.
3. Load it next to the original model (the app is not changed). Recommended: download only the small
   `jai-lora.zip` (the 4.7 GB GGUF download from Colab is slow and is lost when the runtime ends) and
   merge it on the Mac. Ollama 0.40 no longer loads LoRA adapters, so the adapter is merged into
   Ollama's own `qwen2.5:7b-instruct` weights:
   ```sh
   bash finetuning/build_quantize.sh          # once: builds llama.cpp's llama-quantize (needs Xcode)
   bash finetuning/merge_candidate.sh ~/Downloads/jai-lora.zip jai-candidate
   ```
   The merge must not re-quantize to the base model's own grid: the training changes weights by only
   ~0.5%, so Q4_K -> Q4_K erased ~98% of it. Base Q4_K tensors become Q6_K and Q6_K tensors become
   Q5_K (6.1 GB). `check_merge.py` runs at the end and must print `OK: training present`.
   If you did download a full GGUF from Colab instead, `bash finetuning/install_candidate.sh <file>.gguf`.
4. Compare both models on the same held-out cases, then rate replies blind:
   ```sh
   backend/.venv/bin/python finetuning/toolkit.py evaluate --model qwen2.5:7b-instruct --task conversation \
     --limit 40 --timeout 400 --output finetuning/runs/base-conversation.jsonl
   backend/.venv/bin/python finetuning/toolkit.py evaluate --model jai-candidate --task conversation \
     --limit 40 --timeout 400 --output finetuning/runs/tuned-conversation.jsonl
   backend/.venv/bin/python finetuning/toolkit.py sheet \
     --runs finetuning/runs/base-conversation.jsonl finetuning/runs/tuned-conversation.jsonl \
     --output finetuning/runs/rating-sheet.md
   ```
   Automatic checks cover no-action, language and length. The sheet hides which model wrote
   which reply (key in `rating-sheet.key.json`); score correctness, logic, helpfulness and
   naturalness by hand. Repeat `evaluate` with `--task selection|arguments|frame` too, so a
   better conversationalist is not a worse action-picker.
5. If the tuned model wins, set `JADWAI_LOCAL_MODEL=jai-candidate` in `.env` and restart the API.

## Training on your own Linux GPU (alternative)

This Mac is Intel x86_64 with 16 GB RAM and integrated Intel graphics. The QLoRA pipeline
requires a separate Linux NVIDIA CUDA GPU and original locally downloaded
`Qwen/Qwen2.5-7B-Instruct` weights. It does not train Ollama's quantized GGUF copy.
GPU memory requirements depend on sequence length and implementation; do a small smoke run
before scheduling a full experiment. No GPU service, payment, upload, or model download is
performed by these tools. Your choice to stay on this Mac means stop at preparation/evaluation.

On an approved Linux GPU machine with weights and dependencies already available locally:

```sh
python3.11 -m venv .training-venv
.training-venv/bin/pip install -r finetuning/requirements-training.txt
.training-venv/bin/python finetuning/train.py --check
.training-venv/bin/python finetuning/train.py \
  --base-model /local/models/Qwen2.5-7B-Instruct \
  --dataset finetuning/exports/reviewed-v4 \
  --output finetuning/runs/jai-lora-v1 --epochs 2
```

Training is offline, disables telemetry/reporting, verifies exported dataset hashes,
fails on overlong examples rather than silently truncating labels, and never reads the test
file as training/evaluation input. Dependencies are compatibility-pinned/ranged, not a fully
resolved lockfile. The GPU training path has not been executed here and needs a GPU smoke test.
Keep all artifacts under ignored `runs/`/`models/` paths, including checkpoints.

## Export and deployment after a successful experiment

Keep the exact base revision and adapter together. Merge the adapter into original weights
using PEFT on the training machine, then convert and quantize with a compatible llama.cpp
release. Import the resulting supported GGUF through an Ollama Modelfile:

```text
FROM /absolute/path/to/jai-tuned.gguf
```

Create a candidate model with `ollama create jai-candidate -f /path/to/Modelfile`.
Evaluate candidate and original under the same settings. Test real application workflows
with isolated fixtures, including unknown names, draft versus published focus, confirmation,
and English/Arabic multi-turn corrections. Check both raw-model and end-to-end behaviour:
built-in application handlers bypass the model and cannot be fixed by fine-tuning.

Only after review, set `JADWAI_LOCAL_MODEL=jai-candidate` in the private `.env` and restart.
Rollback by restoring `qwen2.5:7b-instruct`. Do not weaken backend checks or execute model
text directly. Fine-tuning does not establish feasibility or guarantee every request works.

References:
- https://huggingface.co/docs/trl/en/sft_trainer
- https://huggingface.co/docs/peft/en/developer_guides/quantization
- https://docs.ollama.com/import
