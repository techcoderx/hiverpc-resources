# HiveSense embeddings benchmark

Measures how fast a llama.cpp backend generates the two kinds of embeddings
HiveSense needs:

- **post embeddings** — real Hivemind posts are cleaned and chunked exactly
  like the hivesense block processor, then embedded in batches through
  `POST /v1/embeddings`;
- **search query embeddings** — post titles are embedded as search queries
  (`Query: ` prefix), both sequentially (interactive latency) and concurrently
  (throughput), the way the search endpoints call the model.

The defaults replicate the stock `haf_api_node` deployment
(`hivesense.yaml` → `hivesense-install-schema` / `hivesense-llama-cpu`), so a
run answers: *how much embedding work can one node configured like this do?*

## Prerequisites

- `uv` on `PATH` (dependencies are installed automatically), plus `psql`-less
  Python access to a Hivemind database — the sampler connects with `psycopg`.
- A llama.cpp build. By default the runner launches
  `~/llama.cpp/build/bin/llama-server`; override with `--llama-server` or
  point at an already-running server with `--server-url`.
- Network access on first run: the tokenizer (`~7 MB`) and, when using the
  default model, the GGUF file (`v5-small-retrieval-F16.gguf`, `~1.2 GB`) are
  downloaded and cached (`~/.cache/llama.cpp`).

## Quick start

```sh
# full run: 1000 posts + 1000 queries against a freshly launched llama-server
./run_benchmark.sh

# quick smoke test (still samples from the DB unless a cache exists)
./run_benchmark.sh --posts 20 --queries 20

# benchmark an already-running server (no launch, no model download)
./run_benchmark.sh --server-url http://127.0.0.1:8080

# only one workload, custom sample size, report files
./run_benchmark.sh --phases posts --posts 200 --csv results/posts.csv
./run_benchmark.sh --phases queries --queries 500
```

Run `./run_benchmark.sh --help` for every option.

## Defaults (mirroring `~/haf_api_node/hivesense.yaml`)

| Setting | Default |
| --- | --- |
| model | `jinaai/jina-embeddings-v5-text-small-retrieval:F16` |
| llama-server | `--embeddings -c 8192 -b 2048 -ub 512` (llama.cpp defaults for `-b`/`-ub`) |
| embedding API | OpenAI `/v1/embeddings` (`embedding_api=openai`) |
| batch size | `50` (`HIVESENSE_EMBEDDING_BATCH_SIZE`) |
| workers | `16` (`HIVESENSE_WORKERS`) |
| document prefix | `Document: ` |
| query prefix | `Query: ` |
| tokens per chunk | `2048` (`HIVESENSE_TOKENS_PER_CHUNK`) |
| overlap | `0.10` (`HIVESENSE_OVERLAP_AMOUNT`) |
| min token threshold | `75` |
| sample | 1000 posts / 1000 query titles from the last 90 days |
| sample DB | `postgresql://hivemind@192.168.1.101/haf_block_log` |

The post pipeline mirrors `db/posts_preprocessing.sql` (`post_clean_content` +
`chunk_post`): HTML/markdown cleaning, pySBD sentence splitting with the same
regex fallbacks, the same overlap back-fill and encode-and-trim loop, and the
same `title || E'.\n\n' || body` input the block processor feeds the chunker.

## Output

- Console summary with throughput and latency percentiles.
- `results/bench_<timestamp>.json` — full config, server/model info, sample
  stats and all metrics.
- Optional `--csv` per-request records (`latency_ms` per batch/query).

Key metrics:

- `chunks_per_sec` / `chunk_tokens_per_sec` — post embedding throughput. The
  embedding phase is pipelined with preprocessing (200-post slices) like the
  block processor, so `embed_secs` is the GPU-bound number.
- `batch_latency_ms` — per `/v1/embeddings` request latency distribution.
- `sequential` query latency — end-to-end HTTP latency for one query
  embedding, including client/JSON overhead (what an interactive search call
  waits for).
- `concurrent` queries/s — throughput with `--query-workers` parallel search
  requests.

## Notes

- The sampled posts/queries are cached in `results/sample.json`; later runs
  reuse them so numbers are comparable. Use `--refresh-sample` to draw a new
  sample, or `--queries-file` to benchmark your own query strings.
- llama-server's `--parallel` slot count is left at its default (the stock
  deployment sets no `-np`), so concurrent post batches may serialize
  server-side. Pass `--extra-server-arg=-np --extra-server-arg=16` to compare
  against an explicitly multi-slot server.
- The batch sizes default to llama.cpp's own defaults (`-b 2048 -ub 512`).
  The stock `hivesense-llama-cpu` service passes `-b 8192 -ub 8192` instead;
  reproduce that with `--server-batch-size 8192 --server-ubatch-size 8192`
  (on memory-constrained machines, e.g. a 16 GB M1 Pro, that combination plus
  the auto-parallel slots can exhaust GPU memory as `Insufficient Memory`
  from Metal — add `--extra-server-arg=-np --extra-server-arg=1` if it does;
  the server log in `results/llama-server.log` shows the failure).
- The preprocessing port is line-for-line from `db/posts_preprocessing.sql`
  but lives outside the database; if the SQL changes, keep this file in sync.
  A run against a Hivemind database without the hivesense schema is expected —
  only raw post rows are read.
- On macOS the locally built llama-server uses Metal; on Linux/CUDA boxes the
  same script works with `--llama-server /path/to/llama-server`.
