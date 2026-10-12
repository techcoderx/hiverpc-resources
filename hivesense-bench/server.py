#!/usr/bin/env python3
"""Manage the llama.cpp embedding server used by the benchmark.

Launches llama-server with the same arguments the default haf_api_node
deployment uses (see hivesense-llama-cpu in hivesense.yaml), waits for the
HTTP endpoint to become ready and shuts it down cleanly afterwards.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class LlamaServer:
    def __init__(self, binary, model, port, ctx_size, batch_size, ubatch_size,
                 extra_args=None, log_path=None, start_timeout=900):
        self.binary = Path(binary)
        self.model = model
        self.port = port
        self.ctx_size = ctx_size
        self.batch_size = batch_size
        self.ubatch_size = ubatch_size
        self.extra_args = list(extra_args or [])
        self.log_path = Path(log_path) if log_path else None
        self.start_timeout = start_timeout
        self.proc = None
        self._log_file = None

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.port

    def command(self):
        cmd = [
            str(self.binary),
            "-hf", self.model,
            "--embeddings",
            "-c", str(self.ctx_size),
            "-b", str(self.batch_size),
            "-ub", str(self.ubatch_size),
            "--host", "127.0.0.1",
            "--port", str(self.port),
        ]
        return cmd + self.extra_args

    def start(self):
        if not self.binary.exists():
            raise FileNotFoundError(
                "llama-server not found at %s; build llama.cpp there or pass "
                "--llama-server/--server-url" % self.binary)

        cmd = self.command()
        print("Starting llama-server: %s" % " ".join(cmd), file=sys.stderr)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self.log_path, "wb")
            stdout = self._log_file
        else:
            stdout = subprocess.DEVNULL

        self.proc = subprocess.Popen(cmd, stdout=stdout,
                                     stderr=subprocess.STDOUT)
        self._wait_ready()
        return self

    def _wait_ready(self):
        deadline = time.monotonic() + self.start_timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    "llama-server exited with code %s before becoming ready"
                    "%s" % (self.proc.returncode,
                            ("; see %s" % self.log_path) if self.log_path else ""))
            try:
                with urlopen(self.url + "/health", timeout=2) as resp:
                    if resp.getcode() == 200:
                        print("llama-server ready at %s (loaded after %.0fs)"
                              % (self.url, self.start_timeout
                                 - (deadline - time.monotonic())),
                              file=sys.stderr)
                        return
            except (HTTPError, URLError, OSError):
                pass
            time.sleep(1)
        raise TimeoutError(
            "llama-server did not become ready within %ds%s"
            % (self.start_timeout,
               ("; see %s" % self.log_path) if self.log_path else ""))

    def props(self):
        """Best-effort server/model info from GET /props."""
        try:
            with urlopen(self.url + "/props", timeout=5) as resp:
                data = json.loads(resp.read().decode())
            return {
                "model": data.get("model_path") or data.get("model_name"),
                "n_ctx": data.get("default_generation_settings", {}).get("n_ctx"),
            }
        except (HTTPError, URLError, OSError, ValueError):
            return {}

    def stop(self):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self.proc = None
        if self._log_file:
            self._log_file.close()
            self._log_file = None
