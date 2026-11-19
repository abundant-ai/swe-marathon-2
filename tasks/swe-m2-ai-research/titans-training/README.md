# Titans training

The first task asks an agent to improve a scratch-pretraining baseline with
continual neural memory. Training and evaluation use next-token prediction on
fixed corpus mixes. The earlier 125-case BABILong QA holdout is retained below
for a later task. Compute allowances and success thresholds still need baseline
measurements.

The runtime functions use the current local [Abundant Titans library](https://github.com/abundant-ai/titans)
and its continuous-stream `pretrain` API. The development image still pins
[`2260f95668a4c3d40fd6050292a1d2f74d8f5a5c`](https://github.com/abundant-ai/titans/commit/2260f95668a4c3d40fd6050292a1d2f74d8f5a5c),
which predates that API. Update the image and dependency pin after the current
library changes are published; the old image cannot run these functions yet.

## Training and streaming evaluation

[common/titans_task/runner.py](common/titans_task/runner.py) provides two functions
that accept an already constructed `ContinualModel`, including `TitansModel` or
a model with another memory architecture and connection implementation:

```python
from titans_task import evaluate, train

training = train(model, data_dir=prepared_data, output_dir=checkpoint_dir,
                 eval_every_steps=512)
loss = evaluate(model, data_dir=prepared_data, split="public")
```

`train` updates the supplied model in place and returns the library's
`TrainingResult`. The learning rate defaults to `1e-4`. Training uses FP32,
batch size one, 4,096-token blocks, one AdamW step per block and gradient clipping
at 1.0. Active memory continues across documents and blocks; ordinary attention
KV resets at each block. The selected connection controls its internal execution
boundaries. There are no task-specific Titans class checks or memory updates.

`eval_every_steps` is a positive integer counting completed optimizer steps. Its
default of 512 runs public evaluation every 2,097,152 training tokens. A final
evaluation always runs after saving the final checkpoint, including when the
last step is not a multiple of the interval. It runs only once when the interval
lands on the final step. For the full 2,560-step pilot, the default evaluates at
steps 512, 1,024, 1,536, 2,048 and 2,560. Set `eval_every_steps=None` to train
without public evaluation.

Each intermediate checkpoint is saved under
`<checkpoint_dir.name>.checkpoints/step-000512` beside `checkpoint_dir`; the final
checkpoint retains the original `checkpoint_dir` path. Results are printed and
appended to `public-eval.jsonl` in that sibling directory, with `step`,
`tokens_processed`, `public_loss` and the checkpoint's absolute path. The loss
uses the same public set and weighted mean as `evaluate`. Existing artifact
directories are rejected to avoid mixing different runs.

One library `pretrain` call owns the entire training stream and optimizer.
Periodic evaluation runs when that call requests its next batch, after the
previous step and memory detach. Evaluation uses fresh memory instead of the
training instance's memory. Model modes, gradient flags, existing gradients and
Python/NumPy/PyTorch random state are preserved so evaluation does not change
subsequent training. The returned elapsed time includes scheduled evaluations.
These checkpoints store shared model parameters; they are not full training
resume files containing the optimizer and active memory.

The corpus quotas are hard-coded in [data.py](common/titans_task/data.py):

| Phase | FineWeb-Edu input tokens | PG19 input tokens | WikiText-103 input tokens | Batches |
| --- | ---: | ---: | ---: | ---: |
| Training | 8,388,608 | 2,097,152 | 0 | 2,560 |
| Public evaluation | 524,288 | 262,144 | 262,144 | 256 |
| Private evaluation | 2,097,152 | 1,048,576 | 1,048,576 | 1,024 |

Tokens include document separators. Each input predicts one next-token target.
One additional source token supplies the final lookahead for each independent
stream; it is not another input or another batch.

### Prepared input files

[scripts/prepare_data.py](scripts/prepare_data.py) downloads the pinned sources,
selects disjoint document pools, tokenizes once, and writes the complete dataset.
The prepared data is available locally at `experiment/data/`. Follow the
[shared setup guide](../../../README.md#local-setup-and-checks) to prepare it again
or run its validation. Generation uses a fresh staging directory and publishes
the output only after every file passes the runtime loader's checks.

`train` and `evaluate` read pretokenized files. They never tokenize source text.
Each `.npy` file is a one-dimensional, little-endian `uint32` array; the loader
memory-maps it read-only and copies only the current block into CPU `int64`
input and label tensors shaped `[1, 4096]`. Model computation remains FP32.

The following paths are relative to `prepared_data`:

| Path | Contents |
| --- | --- |
| `train/stream.npy` | One mixed stream, 10,485,761 IDs including lookahead |
| `public/fineweb_edu/*.npy` | 8 independent streams |
| `public/pg19/*.npy` | 4 independent streams |
| `public/wikitext103/*.npy` | 4 independent streams |
| `private/fineweb_edu/*.npy` | 32 independent streams |
| `private/pg19/*.npy` | 16 independent streams |
| `private/wikitext103/*.npy` | 16 independent streams |
| `<split>/manifest.json` | Ordered files, input counts, SHA-256 checksums and tokenizer identity |
| `<split>/documents.jsonl` | Author-side source provenance and exact token ranges |
| `tokenizer/` | Saved tokenizer files for offline preparation validation |

The tokenizer is `NousResearch/Llama-2-7b-hf` at revision
`8efe6c9b93655b934e27bd9981e3ec13e55aee9d`, matching the scratch backbone's
32,000-token vocabulary. Preparation uses `add_special_tokens=False` and inserts
EOS between documents. Each manifest fingerprints the tokenizer backend,
special-token IDs and vocabulary; a mismatching model tokenizer is rejected.
Local tokenizer paths and transient padding/truncation settings do not affect
this comparison. Token files with wrong checksums, shapes, counts, dtypes or
out-of-vocabulary IDs are rejected as well.

During preparation, training chooses the source furthest behind its fractional
token quota, switching only between documents. Token order within each document
is preserved across batch boundaries. A source's last document may be shortened
and closed with EOS to meet its quota exactly. The final stream boundary keeps a
real lookahead token. Runtime training reads this fixed order without shuffling.

Each evaluation file contains exactly 65,537 IDs: 65,536 inputs and one lookahead.
The final document's unused tail is discarded, and that document is never reused
in another stream. The manifest fixes playback order. Memory starts fresh for
each file and continues through its 16 consecutive batches and document
separators. Shared backbone, memory and connection parameters stay fixed; the
evaluator disables outer autograd while allowing local gradients for inner
memory updates.

### Source selection and provenance

| Corpus | Source revision | Split rule |
| --- | --- | --- |
| [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu) | `87f09149ef4734204d70ed1d046ddc9ca3f2b8f9` | Canonical URL groups from the first `sample/10BT` shard, partitioned by a seeded hash |
| [PG19](https://huggingface.co/datasets/deepmind/pg19) | `4d28bd77e66947ad3835cf78ed7aaeb4dd87ad8b` | Official train, validation and test book lists for training, public and private respectively |
| [WikiText-103](https://huggingface.co/datasets/Salesforce/wikitext) | `b08601e04326c79dfdd32d625aee71d232d685c3` | Whole articles reconstructed from `wikitext-103-raw-v1` training records, partitioned into public/private pools |

Selection uses seed `titans-lm-data-v1-2026-11-19`. FineWeb assigns hash buckets
0–75 to training, 76–80 to public and 81–99 to private. These source-pool ratios
allow the fixed token budgets to fill; the final corpus proportions remain the
80/20 and 50/25/25 recipes above. WikiText assigns one of five hash buckets to
public and the remainder to private. Its articles are evaluation-only; these
are custom task splits rather than official WikiText leaderboard splits. PG19
books are read in seeded hash order from the official public GCS source, with
each object's SHA-256 and generation recorded.

The selector rejects repeated URL/book/article groups and normalized exact text
copies across all selected corpora and splits. It also screens long overlapping
passages using sampled five-word shingles: at least eight matches covering 80%
of the smaller signature reject the later document. This heuristic does not
establish absence of paraphrases or short shared passages. No model scores are
used during selection.

The prepared selection contains:

| Phase | FineWeb documents | PG19 books | WikiText articles |
| --- | ---: | ---: | ---: |
| Training | 6,907 | 18 | 0 |
| Public evaluation | 514 | 6 | 70 |
| Private evaluation | 1,893 | 23 | 247 |

All 9,678 document groups and normalized text hashes are distinct. Selection
rejected nine repeated groups and one exact copy; none crossed the near-copy
threshold. The 81 token files occupy 62,925,252 bytes, about 60 MiB, excluding
tokenizer and provenance files. The audit checks that provenance ranges cover
every stored position and reproduce each source's exact input quota.

Downloaded source bytes and their sidecars live in `experiment/source-cache/`;
the dataset, cache and reports are Git-ignored. `documents.jsonl` and the source
cache are author-side records and are not needed by the runtime. Keep the private
split outside candidate data and image inputs. Public and private evaluation can
use separate roots containing only the relevant split and its manifest.

### Scalar output and current validation

`evaluate` returns one Python `float`, in nats per scored token:

\[
L_{\mathrm{eval}} = 0.50 L_{\mathrm{FineWeb}} + 0.25 L_{\mathrm{PG19}}
                   + 0.25 L_{\mathrm{WikiText}}.
\]

Each corpus loss is its summed next-token cross-entropy divided by its scored
token count. The output is not perplexity. Missing or short streams and
nonfinite losses raise an error; they do not change the denominator or produce a
partial score. The final prediction of a batch scores the first input token of
the next batch before that token enters memory. No target is scored twice.

[scripts/check_train_eval.py](scripts/check_train_eval.py) is an ad hoc offline
CPU probe. Follow the [local setup guide](../../../README.md#local-setup-and-checks)
to run it against the current Titans checkout. It checks the fixed quotas and
packing, scalar aggregation, target causality, loss against an independent
reference across token 4,096, fresh evaluation streams, failure cleanup, and two
real optimizer steps with clipping. It exercises both Titans MAC and an
independent memory whose inner update uses `torch.autograd.grad`.

The probe passed with pretokenized fixtures and tiny real Llama decoders,
including checks that make tokenizer calls fail during training and evaluation.
[scripts/check_preparation.py](scripts/check_preparation.py) checks document
screening, WikiText article reconstruction and exact-budget packing, then can
audit the real data's checksums, token ranges, quotas and split separation.
Both checks passed. No 10M-token training run or GPU job was launched. These
functions are not an isolated private verifier; runtime packaging and evaluation
isolation remain separate work.

## Agent development environment

[environment/Dockerfile](environment/Dockerfile) fetches the pinned repository during the image build and keeps its Git checkout at `/app/titans`. The image starts in that directory as `candidate`, who can edit the source and installed environment. The editable installation uses the checkout's `pyproject.toml` and `uv.lock`, including its GPU extras and development dependencies. Python commands use `/opt/titans-venv`.

The image includes CUDA development tools. A runner must attach a compatible GPU for GPU work. It does not download model weights or a training corpus. The prepared local inputs still need runtime packaging, and the compute allowance is undecided. Build and startup validation are pending because the local Docker daemon is unavailable. There is no candidate step or verifier yet, so this image is not a complete runnable benchmark task.

## Earlier QA holdout for a later task

The selected holdout contains **125 cases**: five cases in each combination of
QA1–QA5 and the context-length buckets **4K, 64K, 256K, 512K, and 1M**. This is
25 cases per task and 25 per length. Each case contains one context, one question,
and one reference answer. The lengths are the published BABILong GPT-2-tokenizer
bucket labels, not exact Qwen token counts. Their nominal total is 45.9 million
context tokens for one pass over the holdout.

This section and its manifest are author-only. Keep them out of candidate images,
training inputs, development examples, and uploaded candidate task bundles.

### Source and selected cases

Use the 100-sample [RMT-team/babilong release](https://huggingface.co/datasets/RMT-team/babilong),
pinned to revision
[`ee0d588794c7ac098062ee0d247c733d62e94fe2`](https://huggingface.co/datasets/RMT-team/babilong/tree/ee0d588794c7ac098062ee0d247c733d62e94fe2).
Each source file is `data/{qa}/{length}.json`, with `qa` in `qa1` through `qa5`
and `length` in `4k`, `64k`, `256k`, `512k`, `1M`. Use this pinned release rather
than the separate 1K-sample release, which does not supply the selected long buckets.
Reference answers come directly from the source, without LLM answer generation
or judging.

The numbers below are zero-based rows in the corresponding `data/qaN/0k.json`
file, identifying the underlying facts, question, and answer. They are not assumed
to be row positions in a long-context file. The exact source records are located
by the byte ranges and checksums in the manifest below. Within each cell, the five
listed base rows correspond to case suffixes `01` through `05`.

| Task | 4K base rows | 64K base rows | 256K base rows | 512K base rows | 1M base rows |
| --- | --- | --- | --- | --- | --- |
| QA1 — Single supporting fact | 47, 48, 49, 51, 52 | 33, 34, 35, 36, 37 | 39, 40, 41, 43, 44 | 11, 12, 13, 15, 16 | 17, 18, 19, 20, 21 |
| QA2 — Two supporting facts | 15, 17, 18, 20, 21 | 22, 23, 24, 25, 27 | 41, 42, 43, 44, 45 | 11, 13, 14, 28, 29 | 9, 10, 31, 33, 34 |
| QA3 — Three supporting facts / earlier state | 10, 11, 13, 15, 17 | 32, 33, 34, 35, 36 | 6, 7, 8, 9, 18 | 19, 20, 21, 22, 23 | 24, 26, 27, 29, 30 |
| QA4 — Two-argument relations | 22, 23, 24, 25, 26 | 14, 15, 16, 17, 18 | 12, 13, 19, 20, 21 | 28, 29, 30, 31, 32 | 33, 34, 35, 36, 37 |
| QA5 — Three-argument relations | 2, 3, 5, 7, 8 | 9, 11, 12, 14, 15 | 16, 17, 18, 19, 20 | 33, 34, 35, 36, 37 | 38, 39, 41, 42, 43 |

All 125 selected long-context records were read. Their extracted bAbI fact
sequences, questions, and answers match their base rows after collapsing
whitespace. The 125 fact sequences are distinct, and no selected sequence is a
complete prefix of another, including across lengths and task types. Changing
background text alone does not count as a unique case. These checks do not claim
125 different reasoning structures or independently identified simulation episodes;
the released records do not include original episode IDs.

### Selection and playback

Selection used the fixed seed string `titans-private-holdout-v1-2026-11-18`.
For each cell, a SHA-256 digest of `{seed}|{qa}|{length}` supplied a deterministic
starting byte offset in the first half of its source file: interpret the first
eight digest bytes as an unsigned big-endian integer and take the remainder
modulo `floor(file_size / 2)`. Scan forward through complete records and accept
five whose facts/question/answer match a base row and whose fact sequence neither
equals, extends, nor is a complete prefix of a previously selected sequence.
Visit tasks QA1 through QA5 and lengths in the table's order. Selection did not
use model predictions or performance. The source's own story/background generation
seeds were not changed; the seed here chooses existing records.

Playback mixes tasks and lengths in one fixed order. Sort case IDs by the
hexadecimal SHA-256 of the UTF-8 string
`titans-private-holdout-order-v1-2026-11-18|{case_id}`, with the case ID as a tie
breaker. The manifest's `playback` column records that order explicitly. Use the
same manifest for each submission. Preserve token order inside every context;
reveal the question after its context, and keep the reference answer unavailable
to the submitted model before scoring.

The selection fixes case identity and order. Whether neural memory and optimizer
state reset between cases or persist across the ordered stream remains a separate
protocol decision. Do not claim this selection alone establishes a cross-example
continual-learning evaluation. A persistent-state protocol also needs explicit
story boundaries so recurring entity names do not silently merge unrelated worlds.

### Exact case manifest

`byte_start` and `byte_end_inclusive` locate a complete UTF-8 JSON object in the
pinned `data/{qa}/{length}.json` file named by the case ID. Fetch that inclusive
byte range, require a matching HTTP `Content-Range`, verify `record_sha256` against
the raw bytes, and then decode the object. An unavailable source or checksum
mismatch is a preparation error; do not silently substitute another case.

The SHA-256 of the CSV block, encoded as UTF-8 with LF line endings and one final
newline, is `fd50fb39749879635ddada409f389b1844984f75551c8706036993c637a6a18a`.

<details>
<summary>125 selected cases in playback order</summary>

```csv
playback,case_id,base_row,byte_start,byte_end_inclusive,record_sha256
1,qa1-512k-04,15,30431011,32508725,9fc52e25a0e75f215cbeafda7cfffda1d246aa0d6f7e51099a8e1f83c9be3cab
2,qa5-1M-04,42,168649705,172691947,b06ab52499e7b0cee6f9121885206a3b7db2f863cf73e731f2f69236ff7b9590
3,qa1-512k-05,16,32508728,34533375,f6f47f73aa070259ac61b29c3c4b37a6d7d26de7aa1c24b0af3b2a562613ea82
4,qa5-64k-02,11,2872850,3127948,38b5ade74d1c46be459f1c1faa604dcc8720283dcdd3eead3a466e2216aa9bdb
5,qa4-4k-05,26,383260,398214,922fcc66da21bc9e76f8655e9751a9fcb1e75bb6b2d0505a1711bb0d0e380e32
6,qa2-4k-04,20,296996,311874,5a9e4911246a716cc8c6b75b89be7cd519dc4de22fb0bc55080ab412feb2200d
7,qa2-64k-04,25,6562698,6813198,1d976ea8d23eca3804e25bec1b500de3d6395183a5e3d2fc2c12c2b30bc79a1c
8,qa4-256k-05,21,21315909,22387065,fee384776db9e685b7f303994382726095d676e11cd63dc0f459e4b91b7dae5e
9,qa5-64k-04,14,3641783,3907423,75c3e30864f94b200e2b28c6e7b4f29cf34107ffcde735fa4f62e236afb8c07c
10,qa5-256k-02,17,17734675,18745324,ea7c9eb8631609fd08acf1fd8e7482dae2f5455cdab62f8ad35a8c94f2889b94
11,qa4-4k-01,22,324930,340504,03254ae1261e5ed99cfbe3e1ac72a1be9d971efaf61698b5cccc7783eb4fb093
12,qa1-1M-04,20,80502608,84215374,e8ebb63efeed30481e1b12faf410480de215d07398124a251e904a73095a1289
13,qa2-64k-01,22,5777416,6045687,567653e85ac5011e9ce7a3324c1e48d8ab57ce87122a5c0de0540686d59f7af0
14,qa5-4k-01,2,30686,43292,1f96cc1a893bc3cac1f66d4078ec570559c3ed75ab2c19ea62a456a49b9615a8
15,qa3-256k-05,18,18755025,19754161,ac231593e49b410186a9d62c3d60ab24d72d4e07a38abf2f37d1f564a396cc5e
16,qa2-512k-02,13,26640547,28724894,b05fb0a842da098510a7a40e1d6d6ab4e220ab3e831793b98009d6487d2b6f09
17,qa1-512k-03,13,26188407,28321643,95bf8a4d07211b8da602fbfd168df83fc2e11f6a799d2451e4f900ae93f77f67
18,qa4-64k-01,14,3578873,3847971,1bd2ee3efa27722fc0f65e2bf33438ee24af2bf6fcd0b28036e286a48d9d3d67
19,qa3-512k-02,20,41358206,43408643,bcf7c6f44c1d6b039c2148ab35fd088fbfb319ee00630fd47f7e45a0e4d96749
20,qa1-256k-01,39,40311119,41365838,bcc263493cf5ce4f77f2c5524d1b95f0211b6886be976899aaa1b741f173c026
21,qa1-256k-02,40,41365841,42388971,03a9067503b9f4cec2cb8365f7e2e65e5f9a7289295dfb7855fb1683647d1cff
22,qa4-512k-04,31,63721256,65864192,f63bafcf4e1bbce5f7a3ba779a6fdb370660693b05e294b8de5f38cc75b942b8
23,qa2-4k-02,17,251520,267053,2715896ba3eadaa192052cc4ad24606db7f654644cf4bf585827fc92f0fa982b
24,qa3-4k-05,17,262837,279803,cdc136109bdaa80d84bb26a4a35ed4b649d0074470c87bb648b0ad510ce028ce
25,qa3-64k-03,34,8737449,8993322,7f72f13c057cec7f83f215e12c7dfcded6a1d72e6844c8dde25e04d5a461d08e
26,qa5-1M-05,43,172691950,176531342,37b9ea5e9aaac77788242ae7b99388822defe498e7417a51361a2a549e129322
27,qa3-512k-03,21,43408646,45504579,e527c8687cc4660eb4b8f7bae7f608cb48cba9d2a8d2ddc2cdcb833e25766a6a
28,qa1-4k-04,51,768512,783797,86d84c0c555878d4f2c3a7e0afed0a75b0c5cedede9483b9cfb5f30d35318435
29,qa2-256k-02,42,43534612,44603278,7145962accfad5012c75ade4f1491914959c0ea1aafa43b240e5a1996fdce708
30,qa3-64k-04,35,8993325,9267363,3b0031053936dd200e7cb5fdbb45e09e45e6b3a0d1b4d6935e8be4a116186cfb
31,qa3-4k-03,13,202001,217591,5ee18b884fa23db0f70deac34327809d92ac363ba26035afb9b1b1956a84489e
32,qa1-512k-01,11,22175377,24249305,5b9798cf7fdb28333885907564711c94b6792f34361a4275c6a4245b809b275e
33,qa5-64k-01,9,2361151,2621534,87d18bdb502b4ec638ca5ec5621896918bffa2d11ac8c6087f56d93e0c4b4576
34,qa3-1M-02,26,104847726,108692794,fae6001151a79339ba1d6de5fe72449b13b515e1ebdf11c80791c5631cdd3af5
35,qa1-64k-05,37,9529429,9797383,de92e33dd356ba0f803e7e3cf002da33ac7e09ebc01c33ff9e1c2c0eba3f129f
36,qa1-4k-05,52,783800,798265,d80451c997d1dfdb098710f39a924f52990e33a6ffc6c3ab4df93c03c5ccf2cd
37,qa4-512k-05,32,65864195,67892345,54b18a6076cfe1086865d5c1e6920c7071b3a8efc4eddbb5f4c1913f131f602d
38,qa5-4k-04,7,105989,120179,c61efc0ea1cde3413b1fe086a8e6788c38c1aa93b86c1b5b1374fd531116a14c
39,qa1-4k-01,47,708064,723278,b5a8e67d402284db93fe7a427a3a4f00288fa8d83ec8c2d34cabbcce3c1d257a
40,qa3-64k-05,36,9267366,9514909,260249fe6de2093f0824642da783d5c6c85ff5cff683806605bcbaeef964c012
41,qa2-1M-04,33,131722102,135531650,2b242b7a41e80161a9541bb1b1e4a70d1ec36576669862922b4deab75ce2919f
42,qa4-256k-04,20,20255644,21315906,90fd1617f5ac671d580e417fa877607d710491125b76f965106f2caa168da598
43,qa3-64k-02,33,8476304,8737446,f96e5a1ff9072ed1ffe6985149485e223af88d01364e1f71ec8b0e4bf5638b8e
44,qa2-64k-05,27,7060983,7311367,bc4270f9e949383ec8f0b00fad5efea4081d2d7845cc84a95d2cdd897a931ab1
45,qa2-256k-03,43,44603281,45635359,4091893eeac6a8c5dc6d440f7c603d1f832ab06cbbf5cfb059b6c670ff124c55
46,qa3-256k-02,7,7291324,8354080,7e8e8c7fbd14fced7cee8fb1d835622f6eeb02bf792ac4295a526a39d5f2f6e6
47,qa1-64k-03,35,8999908,9257480,236df79b3eae4760c67640a916823bbcac70bf5780c13fea9cb6eb77c686eab2
48,qa3-512k-04,22,45504582,47567291,9252c35435c3b71b70608393f60a747d1985e3b396dc58fbdd0a8e96cf59337b
49,qa4-512k-03,30,61757952,63721253,6c3e8cfc75e62fed15d3d0a79f31c3b8f0f461b94768a7e0a82489e13353c449
50,qa1-1M-01,17,68714220,72500617,094d68ab96b610418230f76dc312be4eedc4d933a5e24c03afdc190bf5195198
51,qa1-256k-05,44,45384000,46423968,7b72606b86b78a5c1da8bcd823e7b3e4043114b8860529552d8547d5c7fa1957
52,qa2-1M-02,10,40102435,44234083,197eefa2de9996cb7b0a0795cacc98eecfa95a91952f72eef8300fe0d7fc1456
53,qa5-512k-02,34,70649821,72682709,b4df887336919783a3a2ef2ead5b2f62a2e98c6eb7e36c058fe58d0ef69f2e52
54,qa2-1M-03,31,123833804,127907350,3011ee051ca33c049591099da51e3e05b501b2a6a094d234f356a80f120ce258
55,qa5-64k-03,12,3127951,3386989,4096b0ae45e7bed01633f8ba4516dfe18f6360c98b4f1a0a44f9f9cd9e9f8de3
56,qa2-512k-03,14,28724897,30822213,d68383e3acadc64e42c0cb32727b5918114bea9ed676f6ec32261f4b12b084a4
57,qa4-256k-03,19,19204751,20255641,0f6c255571569fe7a8cf5782f16b56e4490bbd3b599f599253fae217ecb12567
58,qa4-4k-02,23,340507,354264,d5ce453c5f77fd2cc85b8887e7a59ec304768dc3098efade749ff0ab25f8de27
59,qa5-512k-03,35,72682712,74740527,847a1fd97247a401c5df6ed7128157aa11b69f4826f67be28cef2752725d1ca0
60,qa5-4k-02,3,43295,59291,80acc04b977e5f386c445d56512fbe3c93add44cfe998b4109162638496f0046
61,qa5-1M-01,38,152839993,156962735,6caca11c365b928c2d93580e41bcbe30697e5c6755d23bdfd4d6247534957245
62,qa4-1M-05,37,148663092,152671058,2fedce673150141572db939d12c0f6a5b1edbd2ab64e1da3e5f652fdf1b769b0
63,qa2-512k-04,28,57576252,59624184,d5f1e55d786a8f523fac8e6d5eeb73db88146baa79036f8b770a046df807507d
64,qa4-1M-04,36,144777748,148663089,e5a288a1bd5bae7b344a710e05a2e5cb4fdb608878777f48ccbd57697c87b648
65,qa4-1M-03,35,140678696,144777745,d063450c7e788db7c5d5fa53d58ac62d512ec8dc0d3150a89e774ba217ce7945
66,qa4-256k-02,13,13153181,14212266,26c2e7ccc0f2ca135fc2ec80e8bfe67555b1394588cfa5fed9d0e683cebf3863
67,qa1-64k-02,34,8738759,8999905,616b4301257c65a91cd3e523ff5577b5117bf35c7b97c6c01f4fb0b3eebdd8eb
68,qa1-1M-05,21,84215377,87980371,e3ae9000cbf61bc00f15e48c7480a8f5222779fa5c878f5a2f73fd053d29a598
69,qa3-4k-01,10,155373,171213,d163c319b55de0ffb56ab5926c325cf1fa73c2bf80f1c2a4bf61062b6e9622d4
70,qa5-512k-01,33,68596108,70649818,328163057a18363032f3a4f2dc5cd563d2d972a91bea4fa3248539328db88c36
71,qa5-64k-05,15,3907426,4155988,6bcfb7d5c82b6756113f2e860c38f8546ae5da1b78c0152c6c28ed86aa37be8b
72,qa3-1M-03,27,108692797,112724401,8f3561139884413a2a49e5bd6567880d2560bf9348aa7002ec2f3dcf08841323
73,qa5-1M-02,39,156962738,161088203,89e78fe55b1943f064cca47d98603cb77fe8fe32f811ddc832c6d0ab2fc2b13e
74,qa4-4k-03,24,354267,368571,cca72e8ea5ddf48d0812bbe35bad67623e8bef999830385457316a1f281f8407
75,qa1-256k-04,43,44311129,45383997,71fcddf817d03554ea8f078041847bc4cb45385834f1f03abc485609bc6ce881
76,qa4-256k-01,12,12157819,13153178,19d29ea40f41297585c9fa0ee1c85e530f56b9f66c3249e297e829efa3a50f07
77,qa2-512k-01,11,22430183,24565796,8a989b7f76c9a468175067702eb9959cb735ec0bbd3e53c8ed0ac197adb83fed
78,qa2-64k-02,23,6045690,6301188,80d72428302abc50364ee201b29a1331c80a759736abf226663fccf9e943b457
79,qa5-4k-05,8,120182,135465,ecd697e26155d2297be7daa437c6c7c242e5fbade57bf100f6489a6fd493fb74
80,qa5-256k-04,19,19769511,20810835,509e58b64fc8d2dad7afbd4d4af476108659715427aee45cb1ebf4b88db9dd15
81,qa1-4k-03,49,738220,753125,f7b6614fd86cab3063baf37483969d405228f8d1d6d8a05ead4a1e7c8ee42893
82,qa2-4k-03,18,267056,281958,8f199a9a3b7ce41383a9c2aeb253fcad249fc0655dbc721c3a705bc61e64352a
83,qa2-4k-01,15,221019,235770,cb9136e426432f4660afe3c320509efd29e0aeddb38858f56f772eed683981a5
84,qa5-512k-04,36,74740530,76777618,e1b71a1086320b6f55cdf567152bfb4bf4e2c83125cf13af356e9ec9c9695c8e
85,qa5-256k-05,20,20810838,21846748,b3bee9102b6b46c65ec5be5c4a4d5607a58a03acfb32b2e244bf5f192d02f2e0
86,qa2-256k-05,45,46655731,47715701,c68bef4c49df06cbc42ffe6a6d44de0f6feb8075ace4499f532de019e87e37a4
87,qa2-64k-03,24,6301191,6562695,06fe00895a416dd63a061ea75b7b364d7e725ea0bf19fabb3f2f13e740ba5a7f
88,qa3-4k-02,11,171216,186730,2e51ce0e2dd541d2ee879afbc5122135af0b79108ce6daa1a6a01b65c2ebe2dd
89,qa2-256k-04,44,45635362,46655728,53b51e4c76226d6df9f6a628de79cb675615d2abfafbe8a06144900ddc6db907
90,qa3-512k-01,19,39301664,41358203,1e5169ec7f1fb0a4b6e7ee0a7c65523d2b7358d6d51483440e720d9b99c49e4a
91,qa1-64k-01,33,8492433,8738756,fad661001bf8e4b91d353237e9df11bed683545356a539118397021c05cead21
92,qa2-1M-05,34,135531653,139572269,99fba9d11c3f9be35bdb5f60794fd96bc4b53f822113f073b3c87c6a6707ad30
93,qa4-4k-04,25,368574,383257,d777047a40ccf1ac5fd8e4005720d5b08568ae8599dfed4c3ba01a8a0493fa69
94,qa2-4k-05,21,311877,326506,7621d8f9f6dd7dc81b23c6b8fdd5523ab9436e2a91653cd8106f0d3a127ec786
95,qa1-512k-02,12,24249308,26188404,1013c5a61edbaaa90f241e403b8677beb7ab369288df59db1ca4e006bc628004
96,qa3-256k-04,9,9393549,10475759,40986d187a0a1934ddfd3916059d5ce6dc1b1a61de306bcf7f7aadb0ea0e71bd
97,qa1-1M-02,18,72500620,76375432,ec4cbc58b4a5df2c3582c0bf7b73b1d14892aadf99a38601b6ff6207a6f99d0a
98,qa1-64k-04,36,9257483,9529426,5e18263a8d9f86f132f3bd4c16d5fe2dddbb97a13c256e2be2b8365e38dcadb2
99,qa4-64k-04,17,4375847,4635561,407e5a500bc5c503a2eb67d7bac844a41915724bd91533f5ff5e72a7b3d64c02
100,qa1-256k-03,41,42388974,43290103,255bc2b48cdacb1fec462acdc2af7e4ba27caf8906b49d86d00c18a547e3ed56
101,qa2-256k-01,41,42495387,43534609,07721a01897d210da2bf1f4f1423427668f11581c374cd274e720303663c8652
102,qa2-512k-05,29,59624187,61439590,719ac127d79d3e32f3654543987b2a585f318fa993f01ea877dbc8c9dfa5609a
103,qa5-256k-03,18,18745327,19769508,e062da88918c5331e98085f91a1cceb7eafe9d78895b8815fc5d1943ffd73bfa
104,qa3-4k-04,15,233101,245619,389d680a999820b90cf4f952b7496e520f062c20fc18d77a3539ff2b7dfb0afe
105,qa4-512k-02,29,59760979,61757949,e161483d59f07d8820746905d94c1cc78e19807ee0e3e349a73accd18606ad90
106,qa4-1M-01,33,132731181,136588100,5097db64761ca1f108db76a0491afe4ab54086c75d9598a3d064b35c9ce200ae
107,qa3-64k-01,32,8222758,8476301,2d482a5184da9d05a99700f56782df9085a58ae0b6c150aa4f2e95ba8cdfa7c9
108,qa4-512k-01,28,57693751,59760976,f31571b93c85c6d0e337e07d4bb55a35b759c8878b5cfa0e4c386690507cb074
109,qa1-4k-02,48,723281,738217,7191ae0fb05197c1dadc2bbff0df26faf61fae7e82fdb96a17301e35a9588561
110,qa4-64k-05,18,4635564,4897207,eb9537f4155e69d0bab5eba283d5e5249ca8a888480e2f5cd76912b5b3321514
111,qa4-64k-03,16,4114076,4375844,74f315230dcc7b5dfd764828c9ae0af75728df32e042b0a8b467d46d6b57dbd0
112,qa3-1M-05,30,120583176,124660845,f0e4b21324cbd5a7e64f47fa10798879510e1cea81440f48cf02b07cc6cce46b
113,qa5-4k-03,5,75270,90781,0fcfc584152fd7825d60e6fc7ed0055c71f3f66569a28650aa3bb032a04e348a
114,qa3-1M-01,24,96718136,100818689,1db359a01ed324c91f31e7cbe71c9d6df4029f5b51463b66c156d0e38e236d46
115,qa3-512k-05,23,47567294,49687312,14c88c7b1e88741cd46c91cb67dea524ec8018950f1f50595cb877ab186eadb9
116,qa4-1M-02,34,136588103,140678693,ade0050d5840fff3c8556a62630d9d4c48f7e770699c3640434f917c6b384046
117,qa5-256k-01,16,16672663,17734672,6a2ee4c82d23572f5b32de43cc5e1da7ba9c10247f1dccfa9a64a25b5de843cb
118,qa5-512k-05,37,76777621,78840098,6c8b1c3515f92d3bca22a33507dd53a06ff1a6048b098f18c452e5946fb64d51
119,qa5-1M-03,41,164850816,168649702,1ea9bdca7f247c46939a736978c5ee8bd01e05fce65ba17bf3a31234ca45ac90
120,qa4-64k-02,15,3847974,4114073,91e3ad37fc5426b349e82d3c0427b1757a97415ac09111b840f5b2c4b6f9b716
121,qa3-256k-01,6,6240528,7291321,bec3542b8b96d1ebd6e53073db82afdd23f706dd870f70014cce9000669a7726
122,qa3-1M-04,29,116707566,120583173,3dc36cf5dc607f37a5a47147c3b2735be19cf7ad2002bec77d6d9f70bcbc9e78
123,qa3-256k-03,8,8354083,9393546,d10422b2a092a64f868c62251d34adfb886d72b615b6057172e651e9f69b66c0
124,qa2-1M-01,9,36030176,40102432,f3925213848873861f47d94f02bf0fe880ab87affe65d6cb1f49d92934021a12
125,qa1-1M-03,19,76375435,80502605,8925474d07b760c724a2fde2e8a1852c16d2831e8f1673c547b5aa3fe45d4887
```

</details>

### Validation status

The selection checks passed for 125 cases, 25 cells with five cases each, unique
case IDs, unique raw-record hashes, matching base facts/questions/answers, and
no repeated or complete-prefix fact sequences. Independent byte-range re-fetches
also reproduced the recorded hashes for `qa1-4k-01`, `qa3-256k-03`, and `qa5-1M-05`.

No model inference, post-training, test-time learning, Modal GPU run, or difficulty
calibration was performed. Five questions per cell means each answer changes that
cell's accuracy by 20 percentage points; this small holdout cannot reliably rank
small per-cell improvements. Supporting-fact placement and answer-label balance
have not been calibrated. Before execution, choose the state policy, training-data
exclusions, hardware/resource allowance, scoring implementation, and success target,
and validate the actual verifier in a fresh container.

## Hackability assessment

Status: **YELLOW / MEDIUM** for the selected data; execution boundaries remain
**YELLOW / UNASSESSED**. The source questions and answers are public. This is a
private selection of public benchmark records, not newly generated secret stories.
A candidate with access to the full source dataset could memorize answers, and
publishing this manifest would reveal the exact selection. Excluding this README
from candidate images is necessary but does not establish dataset secrecy or
absence from pretrained weights.

Before scored use, exclude the selected underlying examples and their length
variants from task-provided training/development data and audit permitted data
access. The current image's explicit build inputs exclude this README, but no
adversarial access test or training-overlap audit has run. If the task requires
unseen secret content, replace this selection with independently generated stories
and validate their answers; that is not what was selected here.

## Earlier baseline proposal

The original proposed starting point was [lucidrains/titans-pytorch](https://github.com/lucidrains/titans-pytorch), an unofficial PyTorch implementation under the MIT license. The inspected revision was [`35a549f137548d48aecc26e33c6f8a34a6efc97c`](https://github.com/lucidrains/titans-pytorch/commit/35a549f137548d48aecc26e33c6f8a34a6efc97c), dated November 4, 2026. The observations and proposed contract in this section refer to that baseline.

The repository provides a Memory as Context transformer, a neural-memory implementation, and an enwik8 training example. Its [tests](https://github.com/lucidrains/titans-pytorch/blob/35a549f137548d48aecc26e33c6f8a34a6efc97c/tests/test_titans.py) cover memory chaining, state equivalence, sampling, and accelerated operations. Their presence does not establish that they pass in the eventual task environment.

The inspected [training script](https://github.com/lucidrains/titans-pytorch/blob/35a549f137548d48aecc26e33c6f8a34a6efc97c/train_mac.py) uses 512-byte sequences, an eight-layer model with width 384, and neural memory in layers 2, 4, and 6. It requests CUDA and enables FlexAttention and accelerated scan. Validation samples a single batch at each validation interval. The script has no checkpoint saving or resume path, and includes extensions beyond the original paper. Treat this revision as the implementation being improved; do not describe its results as a faithful paper reproduction.

Proposed assignment: improve recall of information outside the model's local attention window under a fixed training compute allowance, while preserving ordinary language-modeling quality. Let the candidate investigate the training recipe and memory behavior, then deliver modified source, a trained checkpoint, reproducible configurations, and evidence explaining the improvement. Optimization methods should remain open within disclosed architecture and resource limits.

Before making this candidate-facing, choose a recall dataset or generator with training and development examples, define the evaluation context lengths and answer format, and measure the untouched baseline. The existing enwik8 example supplies a training starting point; it does not establish a long-context recall baseline. If training efficiency becomes the primary objective, use time to a declared quality target instead and revise the contract explicitly.

| Proposed requirement | Evidence and pass condition to specify |
| --- | --- |
| Better long-context recall | Evaluate baseline and submission on the same held-out cases. Declare aggregation across lengths, missing-answer handling, and the required improvement after calibration. |
| Preserved language-modeling quality | Independently compute held-out loss using fixed preprocessing and state-reset rules. Publish the allowed regression. |
| Causal predictions | Changing future input tokens must not change earlier predictions beyond a declared numerical tolerance. Cover memory updates as well as attention. |
| Isolated memory state | A fresh sequence must start from the declared initial state, independently of earlier evaluation examples and batch order. Test-time updates may use only information already available for the prediction. |
| Resource compliance | Measure training cost and peak memory externally on specified hardware. Define whether compilation, evaluation, and exploratory runs consume the allowance. |
| Reproducible artifacts | Reload the submitted checkpoint in a fresh process and rerun evaluation. Record configuration, source revision, seeds, and training provenance. |

Select the GPU model and count, wall-clock allowance, parameter and attention-window limits, permitted changes to memory architecture, data access, and checkpoint policy before implementing dependent checks. Set thresholds from baseline and working-solution measurements across seeds. Include memory-disabled controls to investigate whether any gain depends on the memory mechanism; their expected score is not yet an acceptance criterion.

The [Titans paper](https://arxiv.org/abs/2501.00663) distinguishes outer-loop training from memory updates during inference. [TNT](https://arxiv.org/abs/2511.07343) studies chunk size and training efficiency in test-time memory models and is relevant background for optimization ideas. Neither paper supplies a measured target for this repository and budget.

Status: the Abundant library's development image is defined above but has not been built or run here. No task verifier, candidate instruction, or task-trained baseline is available. GPU feasibility, learning quality, and achievable improvement under this task's eventual budget remain unverified.

## Development log

### 2026-11-17

Added this task's development log while consolidating the repository layout.
The directory currently contains these design notes only. No task configuration,
candidate instruction, environment, verifier, or oracle is present. The proposed
evaluation data, compute budget, and success thresholds remain unresolved. This
update did not run training or validate the proposal's feasibility.

The repository source and documentation checks passed, including the dated-log
requirement for this draft.

Use a Git-ignored `experiment/` folder here for local experiments when needed.
Record their dated findings in this README and retain reproducible source files
outside the ignored folder when they become part of the task.

Later on the same date, switched the root optional `abundant-titans` dependency
from SSH to public HTTPS and regenerated the lockfile without changing its pinned
revision. Added the agent development image so the editable source and locked GPU
dependencies are present before the agent starts. The image selects only its
Dockerfile and ignore file as local build inputs; task author notes are excluded.
The earlier lucidrains design is retained above as historical proposal context.
An anonymous HTTPS fetch checked out the exact pinned commit successfully.
The frozen Python 3.12 Linux x86-64 GPU sync dry run resolved 174 packages.
The root lockfile check, Titans-group sync dry run, repository source checks,
and `git diff --check` passed. These checks do not establish that the image
builds or that CUDA runs. The Docker CLI is installed outside `PATH`, but its
configured daemon socket is unavailable. Container build and startup checks
remain pending; no training was launched.

### 2026-11-18

Selected and documented 125 BABILong holdout cases: five for each QA1–QA5 and
4K/64K/256K/512K/1M combination. Pinned the public dataset revision and recorded
base-row identities, exact JSON byte ranges, raw-record SHA-256 checksums, and
one fixed order mixing tasks and lengths. Read every selected long-context record
and checked its facts, question, and answer against the pinned base data. All
125 fact sequences are distinct, with no complete-prefix overlap; three separate
range re-fetches reproduced their checksums. Selection used no model scores.

Kept the existing development-image and historical baseline notes. Documented the
public-source memorization risk and the unresolved reset/carry-over policy rather
than treating source selection as proof of a private continual-learning benchmark.
Selection artifacts stayed in local scratch storage; only this author README was
changed for this request. No GPU run, training, verifier implementation, or Harbor
review was performed. Runtime isolation, training overlap, scoring, difficulty,
and feasibility remain unvalidated.

The README manifest checks and `git diff --check` passed. Repository source
checks also passed, covering 154 source files and one configured v2 task.

### 2026-11-19

Implemented task-level `train(model, ...)` and `evaluate(model, ...)` entry
points with the accepted 80/20 training mix, 50/25/25 evaluation mix, and fixed
token budgets. Training delegates to the library's continuous FP32 pretraining
loop. Evaluation returns only the weighted mean next-token loss and permits
inner memory updates while freezing shared parameters. Added local JSONL loading
and one-token-lookahead packing without changing the algorithm protocols.

The ad hoc CPU probe passed for Titans MAC and a separate scalar memory using
local autograd. It covered a full 4,096-token boundary plus a shorter final block,
independent reference losses, hidden-target causality, repeated evaluation,
exact aggregation, malformed/short inputs, and real clipped AdamW steps.
Validation used synthetic documents and tiny decoders against the current local
Titans checkout. Corpus preparation, full-budget training, GPU measurements,
the dependency/image revision update and an isolated final verifier are pending.

Ruff checks, repository source checks and `git diff --check` passed. The CPU
probe also verified restoration of preexisting gradients and module modes after
evaluation failures, FP32 execution inside an outer BF16 autocast scope, and
rejection of nonfinite loss. No GPU test or training job was run.

Added `eval_every_steps=512` to the task-level training function. Intermediate
public evaluations save a checkpoint and append the weighted loss to a JSONL
history; the final saved checkpoint is evaluated once as well. Training keeps
one optimizer and continuing memory throughout. Evaluation restores Python,
NumPy and PyTorch RNG state and never reads the private split.

The CPU probe compared two matching fresh model copies with and without
periodic evaluation, using a 4,096-token block and a shorter final block. Final
parameters, active-memory buffers and mean training loss matched exactly for
Titans MAC and the independent memory implementation. Checkpoint paths, log
entries, interval validation, final-step deduplication and RNG preservation also
passed, along with Ruff, repository checks and `git diff --check`.

An initial version of this probe reused a tiny model trained by an earlier
check; its baseline run hit a nonfinite gradient before any periodic evaluation.
The parity probe now starts with matching fresh copies. These short CPU checks
do not establish convergence or stability of repeated or full-budget training.

Prepared the full fixed corpus mix from pinned FineWeb-Edu, PG19 and WikiText
sources. Training has 10,485,760 input tokens, public evaluation has 1,048,576,
and private evaluation has 4,194,304. All text is tokenized before training;
runtime loaders now validate manifests and memory-map uint32 token files,
converting only the current batch to int64. This replaces the earlier JSONL
runtime tokenization. The train/evaluate interfaces and public-evaluation
schedule remain unchanged, and the data layer makes no algorithm-class checks.

Added the author-side downloader, document selector, duplicate screening,
packer and artifact audit. The selected 9,678 documents have distinct source
groups and normalized text hashes. Source-range coverage and exact per-corpus
budgets passed for all 81 token streams. A second build from the verified source
cache with PyArrow 23.0.1 reproduced all 90 artifact files byte for byte, including
token arrays, manifests, provenance and tokenizer files. Data and reports are
under the Git-ignored `experiment/` directory; raw source files remain separate
from runtime inputs. Duplicate screening is heuristic and does not establish
absence of semantic overlap or source material in pretrained weights.

The preparation checks passed for repeated identities, normalized copies,
long excerpts, WikiText article boundaries across Parquet shards, trimmed EOS
boundaries and both final-lookahead cases. The train/eval CPU probe passed again
with runtime tokenizer calls set to fail, including periodic-evaluation parity
for Titans and the independent memory implementation. Function annotations and
docstrings, Ruff, the dependency lock check, repository checks and
`git diff --check` passed. No full-budget training or GPU job was launched.
The published library/image pin still predates the required pretrain API;
updating that pin, packaging the prepared inputs and isolating the final
verifier remain pending.

Started preparing the authorized multi-hour scratch-learning experiment. The
manual launcher is `scripts/run_modal_training.py`; its remote training function
is in `common/titans_task/experiment.py`. It uses the current local library source,
pretokenized training/public inputs, one H100, FP32, 4,096-token blocks, AdamW at
`1e-4`, and gradient clipping at 1.0. W&B credentials are passed from the local
`.env` as an ephemeral Modal secret and are excluded from source and artifacts.
The available Modal environment is `testing`; this workspace has no default
environment. The W&B destination is `ppo2-abundant/titans-scratch-pretraining`.

The experiment logs per-block NLL/perplexity, gradient norm, learning rate,
throughput, peak GPU memory and token count. Fixed 4,096-token prefixes from one
public stream per corpus provide a separately labeled probe at initialization,
every 25 steps and completion. The full public evaluation runs after the longer
training run. Checkpoints are saved every 100 steps and at completion to the
`titans-learning-runs` Modal volume, alongside source fingerprints and JSONL
metrics. A two-step full-size preflight precedes the three-hour experiment.
At this entry, the preflight image is building; learning and numerical stability
have not yet been established. Static checks and repository checks passed.

The H100 preflight completed two optimizer steps and saved its checkpoint.
W&B run: https://wandb.ai/ppo2-abundant/titans-scratch-pretraining/runs/q8y9rz3s .
The initial/final fixed public probe losses were 10.555995 and 10.559255 nats.
Raw gradient norms were 2.6636e9 and 2.2205e14 before clipping; both steps were
finite, but learning is not established. The second step processed about 444
input tokens/s with 10.94 GiB peak allocated memory. A bounded 20-step diagnostic
was launched to identify the dominant parameter gradients before the long run.
Its W&B run is https://wandb.ai/ppo2-abundant/titans-scratch-pretraining/runs/9cti7au1 ;
Modal call `fc-01M7RV0B2NAHYMJ0S6CY63CM61`, app
`ap-XgtPsZLEP3fGbyCX2pCG21` in `testing`. The remote call is still active at this
entry. Its saved handle is under `experiment/diagnostic-20261119-024337.handle.json`.

The default diagnostic failed at step 13 when PyTorch's FP32 gradient-norm
reduction reported a nonfinite result. Added an experiment-level global clip
that scales by the maximum gradient magnitude before reducing the norm, avoiding
squared-norm overflow while still rejecting NaN/Inf gradient entries. CPU tests
matched an FP64 reference and AdamW updates through gradients of magnitude 1e35.
This preserves FP32 gradients, the single global norm bound and full-block BPTT.
It does not by itself establish numerical stability of the learning dynamics.

With this clip, run `kvqysjyp` completed 20 steps, but the public probe remained
flat (10.555995 to 10.556691). Gradient norms remained extremely large. A separate
20-step diagnostic now tests `max_inner_learning_rate=1e-4` (default `0.01`) and
initial forget-gate bias `-10` (default `-5`). This is a recorded initialization
and hyperparameter experiment, not a change to the algorithm protocol or a claim
that the library defaults are fixed. Results are pending. The multi-hour run
has not yet started.

The adjusted-memory diagnostic `upvxue75` completed 20 steps (81,920 tokens).
Training NLL fell from 10.5549 to 7.2006, and the fixed public probe fell from
10.556046 to 8.280895. Per-corpus final probe NLL: FineWeb 8.269385, PG19 7.502111,
WikiText 9.082699. Most raw gradient norms were approximately 1.4–12, with one
spike to 2,474 at step 10 that was clipped successfully. This establishes early
learning on this small probe, not sustained training stability or a memory
advantage over an ordinary decoder. The two memory-setting changes were tested
together; their individual causal contributions are not isolated.

Launching the longer run from a fresh random initialization using those recorded
settings. It retains the one-pass 10,485,760-token maximum and a three-hour
training-loop wall-clock cap. Full public evaluation now runs before training,
every 512 steps, and after training; initial/final evaluation is outside that
loop's time cap. The run timeout is six hours. The 25-step prefix probe remains
a separate metric. Private data is not uploaded or used by this experiment.

Long run launched successfully: W&B
https://wandb.ai/ppo2-abundant/titans-scratch-pretraining/runs/gwxwy4fm .
Modal app `ap-OM147MaqhV8F8n2GOJscSE`, call
`fc-01M7RVFC0CH4BK0PM28HDCYWK1`, environment `testing`.
Run directory: `scratch-3h-20261119-025149` on volume `titans-learning-runs`.
The local handle is `experiment/scratch-3h-20261119-025149.handle.json`.
At this entry it has authenticated to W&B and is running the initial evaluation;
the multi-hour experiment remains in progress. Do not launch a replacement
unless Modal confirms this call has stopped. The CLI's PTY session is 75527.

Live verification of `gwxwy4fm`: W&B API history confirms uploaded metrics and
running status. Full untrained public loss is 10.561224725 nats/token. The public
prefix probe fell from 10.556046 to 8.048423 at step 25, 7.334259 at step 50,
7.174597 at step 75, and 6.981143 at step 100. Step 100 processed 409,600 training
tokens; its training loss was 6.673718. Peak allocated GPU memory remained near
10.92 GiB. Modal volume inspection confirms `checkpoint-000100`, metrics JSONL,
gradient diagnostics, run metadata and source/data provenance are persisted.
The run remains active; these are intermediate results, not the final learning
assessment or a completed multi-hour run.
