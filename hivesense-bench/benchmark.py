#!/usr/bin/env python3
"""Benchmark HiveSense embedding generation against a llama.cpp backend.

Two workloads, both replicating the default haf_api_node configuration:

  * posts   - sample real root posts from Hivemind, clean and chunk them
              exactly like the hivesense block processor (jina tokenizer,
              2048-token chunks, 10% overlap, "Document: " prefix) and embed
              the chunks in batches of 50 through llama-server's
              /v1/embeddings.
  * queries - embed post titles as search queries ("Query: " prefix) one at a
              time, both sequentially (interactive latency) and concurrently
              (throughput), the way the search endpoints call the model.

Results are printed as a summary and written as JSON (plus optional CSV).
"""

import argparse
import csv
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

from embed_client import EmbeddingClient
from preprocessing import DEFAULT_TOKENIZER_URL, PostChunker, ensure_tokenizer
from sampler import load_or_sample
from server import LlamaServer

HERE = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = HERE / "results"
DEFAULT_SERVER_BINARY = Path.home() / "llama.cpp" / "build" / "bin" / "llama-server"
DEFAULT_DB_URL = "postgresql://hivemind@192.168.1.101/haf_block_log"
DEFAULT_MODEL = "jinaai/jina-embeddings-v5-text-small-retrieval:F16"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    server = parser.add_argument_group("llama.cpp server")
    server.add_argument("--llama-server", default=str(DEFAULT_SERVER_BINARY),
                        help="llama-server binary (launched unless --server-url is given)")
    server.add_argument("--server-url", default=None,
                        help="use an already-running llama-server instead of launching one")
    server.add_argument("--port", type=int, default=8080,
                        help="port for the launched llama-server")
    server.add_argument("--model", default=DEFAULT_MODEL,
                        help="HF repo[:quant] passed to llama-server -hf")
    server.add_argument("--ctx-size", type=int, default=8192)
    server.add_argument("--server-batch-size", type=int, default=2048,
                        help="llama-server -b (logical batch, llama.cpp default)")
    server.add_argument("--server-ubatch-size", type=int, default=512,
                        help="llama-server -ub (physical batch, llama.cpp default)")
    server.add_argument("--extra-server-arg", action="append", default=[],
                        metavar="ARG", help="extra llama-server argument (repeatable)")
    server.add_argument("--server-start-timeout", type=int, default=900,
                        help="seconds to wait for /health (first run downloads the model)")
    server.add_argument("--keep-server", action="store_true",
                        help="leave the launched llama-server running on exit")

    sampling = parser.add_argument_group("sampling")
    sampling.add_argument("--db-url", default=DEFAULT_DB_URL,
                          help="Hivemind PostgreSQL connection URL")
    sampling.add_argument("--posts", type=int, default=1000,
                          help="number of posts to sample")
    sampling.add_argument("--queries", type=int, default=1000,
                          help="number of query titles to sample")
    sampling.add_argument("--sample-window-days", type=int, default=90,
                          help="only sample posts created within this many days")
    sampling.add_argument("--sample-cache", default=str(DEFAULT_RESULTS_DIR / "sample.json"),
                          help="JSON cache of the sampled posts/queries")
    sampling.add_argument("--refresh-sample", action="store_true",
                          help="re-sample from the database even if the cache exists")
    sampling.add_argument("--queries-file", default=None,
                          help="use this file (one query per line) instead of sampled titles")

    embedding = parser.add_argument_group("embedding (haf_api_node defaults)")
    embedding.add_argument("--batch-size", type=int, default=50,
                           help="texts per /v1/embeddings request")
    embedding.add_argument("--workers", type=int, default=16,
                           help="concurrent embedding requests for posts")
    embedding.add_argument("--document-prefix", default="Document: ")
    embedding.add_argument("--query-prefix", default="Query: ")
    embedding.add_argument("--tokens-per-chunk", type=int, default=2048)
    embedding.add_argument("--overlap-amount", type=float, default=0.10,
                           help="fraction of tokens overlapped between chunks")
    embedding.add_argument("--min-token-threshold", type=int, default=75,
                           help="posts with fewer tokens are not embedded")
    embedding.add_argument("--max-embeddings-per-post", type=int, default=None,
                           help="cap chunks per post (default: unlimited)")
    embedding.add_argument("--prep-slice-posts", type=int, default=200,
                           help="posts per preprocessing slice (pipelined with embedding)")
    embedding.add_argument("--tokenizer", default=str(HERE / "tokenizer.json"),
                           help="path to the jina-v5-small tokenizer.json")
    embedding.add_argument("--tokenizer-url", default=DEFAULT_TOKENIZER_URL)
    embedding.add_argument("--timeout", type=int, default=300,
                           help="per-request HTTP timeout in seconds")
    embedding.add_argument("--retries", type=int, default=0,
                           help="retries per request (0 = fail fast)")

    phases = parser.add_argument_group("phases and output")
    phases.add_argument("--phases", default="posts,queries",
                        help="comma-separated subset of: posts, queries")
    phases.add_argument("--query-workers", type=int, default=16,
                        help="concurrency for the query throughput pass")
    phases.add_argument("--json", default=None,
                        help="JSON report path (default: results/bench_<timestamp>.json)")
    phases.add_argument("--csv", default=None,
                        help="optional per-request CSV path")
    phases.add_argument("--label", default=None,
                        help="free-form label stored in the report")

    args = parser.parse_args(argv)
    args.phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    invalid = [p for p in args.phases if p not in ("posts", "queries")]
    if invalid:
        parser.error("unknown phase(s): %s" % ", ".join(invalid))
    if args.overlap_amount < 0 or args.overlap_amount >= 1:
        parser.error("--overlap-amount must be in [0, 1)")
    return args


def latency_summary_ms(values):
    """min/mean/p50/p90/p95/p99/max of a list of millisecond values."""
    if not values:
        return {}
    values = sorted(values)

    def pct(p):
        if len(values) == 1:
            return values[0]
        k = (len(values) - 1) * p
        lo = int(k)
        hi = min(lo + 1, len(values) - 1)
        return values[lo] + (values[hi] - values[lo]) * (k - lo)

    return {
        "min": round(values[0], 3),
        "mean": round(statistics.fmean(values), 3),
        "p50": round(pct(0.50), 3),
        "p90": round(pct(0.90), 3),
        "p95": round(pct(0.95), 3),
        "p99": round(pct(0.99), 3),
        "max": round(values[-1], 3),
    }


def preprocess_slice(chunker, posts, min_token_threshold):
    """Preprocess a slice of posts, mirroring prepare_post_chunks().

    Returns (chunks, discarded, post_tokens) where chunks is a list of
    (post_id, chunk_number, text, token_count); posts below the minimum
    token threshold produce no chunks (dropped from the vector store).
    """
    chunks = []
    discarded = 0
    post_tokens = 0
    for post in posts:
        text = (post["title"] or "") + ".\n\n" + (post["body"] or "")
        result = chunker.preprocess_post(text, post["id"])
        if result is None:
            discarded += 1
            continue
        post_chunks, token_count = result
        if token_count < min_token_threshold:
            discarded += 1
            continue
        post_tokens += token_count
        for number, chunk_text in enumerate(post_chunks):
            chunks.append((post["id"], number, chunk_text,
                           chunker.count_tokens(chunk_text)))
    return chunks, discarded, post_tokens


def run_posts_phase(args, chunker, client, posts, csv_writer):
    slices = [posts[i:i + args.prep_slice_posts]
              for i in range(0, len(posts), args.prep_slice_posts)]

    discarded = 0
    chunks_total = 0
    chunk_tokens_total = 0
    post_tokens_total = 0
    prep_secs = 0.0
    embed_started = None
    latencies = []
    embedding_dim = None
    futures = []

    pool = ThreadPoolExecutor(max_workers=args.workers)
    try:
        for slice_posts in slices:
            started = time.monotonic()
            chunks, slice_discarded, slice_post_tokens = preprocess_slice(
                chunker, slice_posts, args.min_token_threshold)
            prep_secs += time.monotonic() - started

            discarded += slice_discarded
            post_tokens_total += slice_post_tokens
            chunks_total += len(chunks)
            chunk_tokens_total += sum(c[3] for c in chunks)

            if not chunks:
                continue
            if embed_started is None:
                embed_started = time.monotonic()

            for base in range(0, len(chunks), args.batch_size):
                batch = chunks[base:base + args.batch_size]
                futures.append(pool.submit(
                    client.embed_batch, [c[2] for c in batch]))

        for future in futures:
            vectors, elapsed = future.result()
            if embedding_dim is None and vectors:
                embedding_dim = len(vectors[0])
            latencies.append(elapsed * 1000)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    embed_secs = (time.monotonic() - embed_started) if embed_started else 0.0

    if csv_writer is not None:
        for batch_no, latency in enumerate(latencies):
            csv_writer.writerow(["posts", batch_no, args.batch_size,
                                 "", round(latency, 3)])

    result = {
        "posts_fetched": len(posts),
        "posts_discarded": discarded,
        "posts_embedded": len(posts) - discarded,
        "chunks": chunks_total,
        "embedding_dim": embedding_dim,
        "post_tokens": post_tokens_total,
        "chunk_tokens": chunk_tokens_total,
        "requests": len(latencies),
        "prep_secs": round(prep_secs, 3),
        "embed_secs": round(embed_secs, 3),
        "chunks_per_sec": round(chunks_total / embed_secs, 1) if embed_secs else None,
        "chunk_tokens_per_sec": round(chunk_tokens_total / embed_secs, 1) if embed_secs else None,
        "posts_per_sec": round((len(posts) - discarded) / embed_secs, 1) if embed_secs else None,
        "batch_latency_ms": latency_summary_ms(latencies),
        "truncated_chunks": chunker.truncated_chunks,
        "regex_fallbacks": chunker.regex_fallbacks,
    }
    return result


def run_queries_phase(args, chunker, client, queries, csv_writer):
    query_texts = [(args.query_prefix or "") + q for q in queries]
    query_tokens = [chunker.count_tokens(t) for t in query_texts]

    sequential = []
    embedding_dim = None
    for text in query_texts:
        vectors, elapsed = client.embed_batch([text])
        if embedding_dim is None and vectors:
            embedding_dim = len(vectors[0])
        sequential.append(elapsed * 1000)

    concurrent = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.query_workers)) as pool:
        futures = {pool.submit(client.embed_batch, [t]): i
                   for i, t in enumerate(query_texts)}
        for future in as_completed(futures):
            _vectors, elapsed = future.result()
            concurrent.append((futures[future], elapsed * 1000))
    concurrent_wall = time.monotonic() - started
    concurrent_latencies = [latency for _idx, latency in concurrent]

    if csv_writer is not None:
        for idx, (tokens, latency) in enumerate(zip(query_tokens, sequential)):
            csv_writer.writerow(["query_sequential", idx, 1, tokens, round(latency, 3)])
        for idx, latency in concurrent:
            csv_writer.writerow(["query_concurrent", idx, 1, query_tokens[idx], round(latency, 3)])

    total_tokens = sum(query_tokens)
    return {
        "count": len(query_texts),
        "embedding_dim": embedding_dim,
        "query_tokens": {
            "total": total_tokens,
            "mean": round(total_tokens / len(query_texts), 1) if query_texts else 0,
            "max": max(query_tokens) if query_tokens else 0,
        },
        "sequential": {
            "latency_ms": latency_summary_ms(sequential),
            "queries_per_sec": round(
                len(sequential) / (sum(sequential) / 1000.0), 1) if sequential else None,
        },
        "concurrent": {
            "workers": max(1, args.query_workers),
            "wall_secs": round(concurrent_wall, 3),
            "latency_ms": latency_summary_ms(concurrent_latencies),
            "queries_per_sec": round(
                len(concurrent_latencies) / concurrent_wall, 1) if concurrent_wall else None,
        },
    }


def print_summary(report):
    cfg = report["config"]
    print()
    print("=== HiveSense embeddings benchmark ===")
    print("server:  %s  (model %s)" % (report["server"].get("url", "?"),
                                       cfg["model"]))
    print("sample:  %d posts, %d queries (window %d days)"
          % (report["sample"]["posts"], report["sample"]["queries"],
             cfg["sample_window_days"]))
    print("embed:   batch=%d workers=%d prefix=%r tokens_per_chunk=%d overlap=%.2f"
          % (cfg["batch_size"], cfg["workers"], cfg["document_prefix"],
             cfg["tokens_per_chunk"], cfg["overlap_amount"]))

    posts = report.get("posts")
    if posts:
        print()
        print("--- post embeddings ---")
        print("posts:   %d embedded, %d discarded (<%d tokens)"
              % (posts["posts_embedded"], posts["posts_discarded"],
                 cfg["min_token_threshold"]))
        print("chunks:  %d (dim %s, %d post tokens, %d chunk tokens)"
              % (posts["chunks"], posts.get("embedding_dim") or "?",
                 posts["post_tokens"], posts["chunk_tokens"]))
        print("throughput: %.1f chunks/s, %.1f chunk-tokens/s, %.1f posts/s"
              % (posts["chunks_per_sec"] or 0,
                 posts["chunk_tokens_per_sec"] or 0,
                 posts["posts_per_sec"] or 0))
        print("prep:    %.2fs   embed: %.2fs (%.0f requests)"
              % (posts["prep_secs"], posts["embed_secs"], posts["requests"]))
        print("batch latency (ms): %s" % _fmt_latency(posts["batch_latency_ms"]))
        if posts["truncated_chunks"] or posts["regex_fallbacks"]:
            print("splitter: %d truncated chunk(s), %d regex fallback(s)"
                  % (posts["truncated_chunks"], posts["regex_fallbacks"]))

    queries = report.get("queries")
    if queries:
        print()
        print("--- search query embeddings ---")
        print("queries: %d (dim %s, mean %.1f tokens, max %d)"
              % (queries["count"], queries.get("embedding_dim") or "?",
                 queries["query_tokens"]["mean"],
                 queries["query_tokens"]["max"]))
        seq = queries["sequential"]
        print("sequential: %.1f queries/s, latency (ms): %s"
              % (seq["queries_per_sec"] or 0, _fmt_latency(seq["latency_ms"])))
        con = queries["concurrent"]
        print("concurrent: %d workers, %.1f queries/s, latency (ms): %s"
              % (con["workers"], con["queries_per_sec"] or 0,
                 _fmt_latency(con["latency_ms"])))
    print()


def _fmt_latency(stats):
    if not stats:
        return "n/a"
    return ("min=%.1f mean=%.1f p50=%.1f p90=%.1f p95=%.1f p99=%.1f max=%.1f"
            % (stats["min"], stats["mean"], stats["p50"], stats["p90"],
               stats["p95"], stats["p99"], stats["max"]))


def main(argv=None):
    args = parse_args(argv)
    started_at = datetime.now(timezone.utc)
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")

    tokenizer_path = ensure_tokenizer(args.tokenizer, args.tokenizer_url)
    chunker = PostChunker(
        tokenizer_path,
        document_prefix=args.document_prefix,
        max_tokens=args.tokens_per_chunk,
        min_new_ratio=1 - args.overlap_amount,
        max_chunks=args.max_embeddings_per_post,
        min_token_threshold=0,
    )

    need_posts = "posts" in args.phases
    need_sampled_queries = "queries" in args.phases and args.queries_file is None

    posts, queries = [], []
    if need_posts or need_sampled_queries:
        sampled_posts, sampled_queries = load_or_sample(
            args.sample_cache, args.db_url,
            args.posts if need_posts else 0,
            args.queries if need_sampled_queries else 0,
            args.sample_window_days, refresh=args.refresh_sample)
        if need_posts:
            posts = sampled_posts
        if need_sampled_queries:
            queries = sampled_queries
    if args.queries_file is not None and "queries" in args.phases:
        with open(args.queries_file) as inp:
            queries = [line.strip() for line in inp if line.strip()]
        if not queries:
            raise RuntimeError("no queries found in %s" % args.queries_file)

    server = None
    launched = False
    try:
        if args.server_url:
            server_url = args.server_url.rstrip("/")
            server_info = {"url": server_url, "started": False, "args": []}
        else:
            server = LlamaServer(
                binary=args.llama_server,
                model=args.model,
                port=args.port,
                ctx_size=args.ctx_size,
                batch_size=args.server_batch_size,
                ubatch_size=args.server_ubatch_size,
                extra_args=args.extra_server_arg,
                log_path=DEFAULT_RESULTS_DIR / "llama-server.log",
                start_timeout=args.server_start_timeout,
            )
            server.start()
            launched = True
            server_url = server.url
            server_info = {"url": server_url, "started": True,
                           "args": server.command()}

        props = server.props() if server else {}
        if props:
            server_info.update(props)

        client = EmbeddingClient(server_url, model=args.model,
                                 timeout=args.timeout, retries=args.retries)

        csv_file = csv_writer = None
        if args.csv:
            Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
            csv_file = open(args.csv, "w", newline="")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["phase", "index", "inputs", "tokens", "latency_ms"])

        report = {
            "generated_at": started_at.isoformat(),
            "label": args.label,
            "server": server_info,
            "sample": {
                "db_url": args.db_url,
                "posts": len(posts),
                "queries": len(queries),
                "sample_cache": args.sample_cache,
            },
            "config": {
                "model": args.model,
                "batch_size": args.batch_size,
                "workers": args.workers,
                "query_workers": args.query_workers,
                "document_prefix": args.document_prefix,
                "query_prefix": args.query_prefix,
                "tokens_per_chunk": args.tokens_per_chunk,
                "overlap_amount": args.overlap_amount,
                "min_token_threshold": args.min_token_threshold,
                "max_embeddings_per_post": args.max_embeddings_per_post,
                "prep_slice_posts": args.prep_slice_posts,
                "ctx_size": args.ctx_size,
                "server_batch_size": args.server_batch_size,
                "server_ubatch_size": args.server_ubatch_size,
                "sample_window_days": args.sample_window_days,
                "timeout": args.timeout,
            },
            "posts": None,
            "queries": None,
        }

        try:
            if "posts" in args.phases:
                print("Benchmarking post embeddings (%d posts)..." % len(posts),
                      file=sys.stderr)
                report["posts"] = run_posts_phase(
                    args, chunker, client, posts, csv_writer)
            if "queries" in args.phases:
                print("Benchmarking search query embeddings (%d queries)..."
                      % len(queries), file=sys.stderr)
                report["queries"] = run_queries_phase(
                    args, chunker, client, queries, csv_writer)
        except (HTTPError, URLError, OSError) as exc:
            print("ERROR: embedding request failed: %s" % exc, file=sys.stderr)
            if launched:
                print("The launched llama-server may have crashed (out of GPU "
                      "memory?); see %s" % (DEFAULT_RESULTS_DIR / "llama-server.log"),
                      file=sys.stderr)
                print("On memory-constrained machines try: "
                      "--extra-server-arg=-np --extra-server-arg=1", file=sys.stderr)
            raise
        finally:
            if csv_file:
                csv_file.close()

        json_path = Path(args.json) if args.json else (
            DEFAULT_RESULTS_DIR / ("bench_%s.json" % timestamp))
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w") as out:
            json.dump(report, out, indent=2)

        print_summary(report)
        print("JSON report: %s" % json_path)
        if args.csv:
            print("CSV records: %s" % args.csv)
        return 0
    finally:
        if server and launched and not args.keep_server:
            server.stop()
        elif server and args.keep_server:
            print("llama-server left running at %s (pid %s)"
                  % (server.url, server.proc.pid if server.proc else "?"),
                  file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
