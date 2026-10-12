#!/usr/bin/env python3
"""OpenAI-compatible /v1/embeddings client for the benchmark.

Speaks the same wire protocol as the hivesense block processor when
embedding_api=openai (the llama-server path in db/ollama.sql): a
{"model", "input"} payload to /v1/embeddings, response sorted by index.
"""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class EmbeddingClient:
    def __init__(self, base_url, model="", timeout=300, retries=0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def embed_batch(self, texts):
        """Embed a batch of texts; returns (vectors, elapsed_seconds)."""
        payload = json.dumps({"model": self.model, "input": texts}).encode()
        url = self.base_url + "/v1/embeddings"

        delay = 1.0
        for attempt in range(self.retries + 1):
            started = time.monotonic()
            try:
                req = Request(url, data=payload,
                              headers={"Content-Type": "application/json"})
                with urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode())
                elapsed = time.monotonic() - started
                # Sort by index to guarantee alignment with the input order.
                vectors = [
                    item["embedding"]
                    for item in sorted(data.get("data", []),
                                       key=lambda o: o.get("index", 0))
                ]
                if len(vectors) != len(texts):
                    raise RuntimeError(
                        "embedding server returned %d vectors for %d inputs"
                        % (len(vectors), len(texts)))
                return vectors, elapsed
            except (HTTPError, URLError, OSError):
                if attempt >= self.retries:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 30.0)
