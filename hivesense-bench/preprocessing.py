#!/usr/bin/env python3
"""Faithful Python port of the HiveSense post preprocessing SQL.

Mirrors db/posts_preprocessing.sql (post_clean_content, chunk_post,
preprocess_post) so the benchmark sees the same chunk boundaries, token
counts and discard rules as a node running the default configuration of
haf_api_node. The chunking algorithm (including the overlap back-fill and
the encode-and-trim verification loop) is kept line-for-line to avoid
measurement drift; the SQL functions remain the source of truth.
"""

import html
import re
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pysbd
from bs4 import BeautifulSoup
from tokenizers import Tokenizer

DEFAULT_TOKENIZER_URL = (
    "https://huggingface.co/jinaai/jina-embeddings-v5-text-small/"
    "resolve/main/tokenizer.json"
)

_CLEAN_PATTERNS = {
    # images & bare URLs
    "remove_markdown": re.compile(r'(!\[.*?\]\(.*?\)|https?://\S+)', re.IGNORECASE),

    # [title](url) => title
    "remove_markdown_links": re.compile(
        r'\[([^\]]+)\]\([^\)]+\)|!\[\]\([^)]*\)|!\S+\.(jpg|jpeg|png|gif)',
        re.IGNORECASE,
    ),

    "remove_unwanted": re.compile(r'Posted via.*$|[*_]+', re.MULTILINE),

    "remove_base64": re.compile(r'data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+'),

    # C0 control characters (except \t \n \r) and DEL: pure noise for the
    # embedding model, and raw separators like \x1c crash pySBD's
    # numbered-list parser (int('\x1c2') ValueError, seen at block ~8.9M)
    "remove_control_chars": re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]'),
}


def clean_content(text):
    """Port of hivesense_app.post_clean_content()."""
    text = _CLEAN_PATTERNS["remove_control_chars"].sub('', text)
    text = html.unescape(text)

    soup = BeautifulSoup(text, 'lxml')
    for tag in soup(['script', 'style', 'img', 'table']):
        tag.decompose()

    extracted = soup.get_text(separator=' ')
    extracted = _CLEAN_PATTERNS["remove_markdown_links"].sub(r'\1', extracted)
    extracted = _CLEAN_PATTERNS["remove_markdown"].sub('', extracted)
    extracted = _CLEAN_PATTERNS["remove_base64"].sub('', extracted)
    return _CLEAN_PATTERNS["remove_unwanted"].sub('', extracted)


class PostChunker:
    """Port of hivesense_app.chunk_post()/preprocess_post().

    The cached state (tokenizer, prefix ids, sentence splitters, counters)
    mirrors the PL/Python GD dict caches in the SQL functions.
    """

    def __init__(self, tokenizer_path, document_prefix="Document: ",
                 max_tokens=2048, min_new_ratio=0.90, max_chunks=None,
                 truncate_long_sentences=True, min_token_threshold=75):
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.document_prefix = document_prefix or ''
        self.max_tokens = max_tokens
        self.min_new_ratio = min_new_ratio
        self.max_chunks = max_chunks
        self.truncate_long_sentences = truncate_long_sentences
        self.min_token_threshold = min_token_threshold

        prefix_ids = self.tokenizer.encode(self.document_prefix,
                                           add_special_tokens=False).ids
        specials = self.tokenizer.num_special_tokens_to_add(is_pair=False)
        self.prefix_len = len(prefix_ids)
        self.fixed_overhead = len(prefix_ids) + specials
        self.max_content_tokens = self.max_tokens - self.fixed_overhead
        if self.max_content_tokens <= 0:
            raise ValueError(
                "DOCUMENT_PREFIX %r exceeds token budget %d"
                % (self.document_prefix, self.max_tokens)
            )

        self._patterns = {
            "normalize_whitespace": re.compile(r'\s+'),

            "cjk_sentence_end": re.compile(r'(?<=[。？！…\.?!])\s*|\r?\n+'),

            # Last-resort sentence terminators across scripts, used when the
            # primary splitter finds no boundary in an oversized "sentence".
            "universal_sentence_end": re.compile(
                r'(?<=[。？！।॥۔؟։።။។])\s*|(?<=[\.?!…])\s+|\r?\n+'),

            "ja_characters": re.compile(r"[\u3040-\u309F\u30A0-\u30FF]"),
            "zh_characters": re.compile(r"[\u4E00-\u9FFF]"),
            "ko_characters": re.compile(r"[\uAC00-\uD7AF]"),
            # detect when to apply workaround for PySBD bug
            "catastrophic_backtracking_trigger": re.compile(r"\[[^\]]*\d{5,}[^\]]*\]"),
        }

        # sentence splitters cached per language
        self._segmenters = {}

        # chunker telemetry, mirroring hivesense_truncated_chunks and
        # hivesense_regex_fallbacks in the PL/Python GD dict
        self.truncated_chunks = 0
        self.regex_fallbacks = 0

    # ------------------------------------------------------------------
    # sentence splitting helpers
    # ------------------------------------------------------------------
    def _split_cjk(self, text):
        parts = re.split(self._patterns["cjk_sentence_end"], text)
        return [p for p in parts if p]

    def _guess_language(self, text):
        if self._patterns["ko_characters"].search(text):
            return 'ko'
        if self._patterns["ja_characters"].search(text):
            return 'ja'
        if self._patterns["zh_characters"].search(text):
            return 'zh'
        return 'en'

    def _split_sentences(self, text, assumed_language):
        if assumed_language == 'ko':
            # sbd doesn't have Korean language support, so fall back to a
            # simple regex splitter
            return self._split_cjk(text)

        if assumed_language not in self._segmenters:
            self._segmenters[assumed_language] = pysbd.Segmenter(
                language=assumed_language, clean=False)

        if self._patterns["catastrophic_backtracking_trigger"].search(text):
            self.regex_fallbacks += 1
            return self._patterns["universal_sentence_end"].split(text)
        try:
            return self._segmenters[assumed_language].segment(text)
        except Exception:
            # pySBD has more parsing bugs than the backtracking one above
            # (e.g. int() on stray digits in its list detection). One bad post
            # must not kill a multi-day generation run: fall back to the same
            # simple splitter and keep going.
            self.regex_fallbacks += 1
            return self._patterns["universal_sentence_end"].split(text)

    def _normalize_whitespace(self, text):
        return self._patterns["normalize_whitespace"].sub(' ', text).strip()

    def _split_sentences_to_token_count(self, text, target_max_length):
        language = self._guess_language(text)
        raw_sents = self._split_sentences(text, language)

        cleaned = [self._normalize_whitespace(s) for s in raw_sents if s.strip()]

        output = []
        for s in cleaned:
            token_ids = self.tokenizer.encode(s, add_special_tokens=False).ids
            if len(token_ids) <= target_max_length:
                output.append((s, token_ids))
                continue

            # --- oversized chunk!
            # SBD will refuse to split multi-sentence quotes and parentheticals.
            # try to unwrap quotes/parens and re-split
            unwrapped = False
            for open_ch, close_ch in [('"', '"'), ('“', '”'), ("'", "'"),
                                      ('(', ')'), ('[', ']')]:
                if s.startswith(open_ch) and s.endswith(close_ch):
                    inner = s[len(open_ch):-len(close_ch)]
                    for sub in self._split_sentences(inner, language):
                        sub_clean = self._normalize_whitespace(sub)
                        if not sub_clean:
                            continue
                        sub_tokens = self.tokenizer.encode(
                            sub_clean, add_special_tokens=False).ids
                        output.append((sub_clean, sub_tokens))
                    unwrapped = True
                    break

            if unwrapped:
                continue

            # --- fallback: brute-force split on sentence terminators from any
            # script (pySBD only handles 22 languages; Bengali/Hindi/Urdu prose
            # and similar used to arrive here as one giant "sentence" and get
            # hard-truncated despite ending every sentence with a danda)
            parts = self._patterns["universal_sentence_end"].split(s)
            if len(parts) > 1:
                for sub in parts:
                    sub_clean = self._normalize_whitespace(sub)
                    if not sub_clean:
                        continue
                    sub_tokens = self.tokenizer.encode(
                        sub_clean, add_special_tokens=False).ids
                    output.append((sub_clean, sub_tokens))
            else:
                # give up and accept the giant sentence
                output.append((s, token_ids))

        return output

    # ------------------------------------------------------------------
    # chunking
    # ------------------------------------------------------------------
    def _encode_len(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=True).ids)

    def count_tokens(self, text):
        """Token length of a chunk text including prefix and specials."""
        return self._encode_len(text)

    def chunk_post(self, body, post_id):
        """Port of hivesense_app.chunk_post(). Returns (chunks, token_count)
        or None when the post is below the minimum token threshold."""
        max_content_tokens = self.max_content_tokens
        prefix = self.document_prefix

        sentence_tokens = self._split_sentences_to_token_count(
            body, max_content_tokens)

        # here is our total token count for the entire (cleaned) post:
        token_count = sum(len(ids) for _txt, ids in sentence_tokens)

        if token_count < self.min_token_threshold:
            # returns None if the post is "too short"
            return None

        chunks = []
        prev_sentences = []  # context for overlap
        i = 0                # cursor into sentence_tokens

        while i < len(sentence_tokens):
            chunk = []         # sentences in display order
            added_stack = []   # sentences in *addition* order
            chunk_tokens = 0
            new_tokens = 0
            new_budget = int(max_content_tokens * self.min_new_ratio)

            # ---- Phase 1: fresh content up to new_budget ----
            while i < len(sentence_tokens):
                txt, ids = sentence_tokens[i]
                tlen = len(ids)

                # special case: very long first sentence
                if not chunk and tlen > new_budget:
                    if tlen <= max_content_tokens:
                        # accept whole
                        chunk.append((txt, ids))
                        added_stack.append(
                            {'txt': txt, 'ids': ids, 'src': 'new'})
                        new_tokens += tlen
                        chunk_tokens += tlen
                        i += 1
                    elif self.truncate_long_sentences:
                        # count every truncation for the caller's telemetry
                        self.truncated_chunks += 1
                        trunc_ids = ids[:max_content_tokens]
                        trunc_txt = self.tokenizer.decode(trunc_ids)
                        chunk.append((trunc_txt, trunc_ids))
                        added_stack.append(
                            {'txt': trunc_txt, 'ids': trunc_ids, 'src': 'new'})
                        new_tokens += len(trunc_ids)
                        chunk_tokens += len(trunc_ids)
                        i += 1
                    break

                if new_tokens + tlen > new_budget:
                    break

                chunk.append((txt, ids))
                added_stack.append({'txt': txt, 'ids': ids, 'src': 'new'})
                new_tokens += tlen
                chunk_tokens += tlen
                i += 1

            # ---- Phase 2: prepend overlap from previous chunk ----
            for ptxt, pids in reversed(prev_sentences):
                plen = len(pids)
                if chunk_tokens + plen <= max_content_tokens:
                    chunk.insert(0, (ptxt, pids))
                    added_stack.append(
                        {'txt': ptxt, 'ids': pids, 'src': 'prev'})
                    chunk_tokens += plen
                else:
                    break

            # ---- Phase 3: back-fill with more new sentences ----
            while i < len(sentence_tokens):
                txt, ids = sentence_tokens[i]
                tlen = len(ids)
                if chunk_tokens + tlen > max_content_tokens:
                    break
                chunk.append((txt, ids))
                added_stack.append({'txt': txt, 'ids': ids, 'src': 'new'})
                chunk_tokens += tlen
                i += 1

            # ---- Phase 4: verify & trim until the real encode fits ----
            full_txt = prefix + " ".join(t for t, _ in chunk)

            while self._encode_len(full_txt) > self.max_tokens:
                if not added_stack:
                    raise RuntimeError(
                        "post %s: no sentence left to pop but still too long"
                        % post_id)

                last = added_stack.pop()  # most-recently-added
                chunk.remove((last['txt'], last['ids']))

                if len(chunk) == 0:
                    # last['ids'] is the ONLY remaining content; chop it
                    # token-by-token
                    ids = last['ids'][:]
                    while ids and self._encode_len(
                            prefix + self.tokenizer.decode(ids)) > self.max_tokens:
                        ids.pop()  # drop ONE token-id
                    if not ids:
                        raise RuntimeError(
                            "post %s: even one token would overflow" % post_id)
                    shrunk_txt = self.tokenizer.decode(ids)
                    chunk.append((shrunk_txt, ids))
                    added_stack.append(
                        {'txt': shrunk_txt, 'ids': ids, 'src': 'new'})
                else:
                    # if the popped item came from fresh content we must
                    # re-process it
                    if last['src'] == 'new':
                        i -= 1  # rewind so the next chunk sees it

                full_txt = prefix + " ".join(t for t, _ in chunk)

            chunks.append(full_txt)

            # build the context list for the next loop
            prev_sentences = chunk

            if self.max_chunks is not None and len(chunks) >= self.max_chunks:
                break

        return chunks, token_count

    def preprocess_post(self, text, post_id):
        """Port of hivesense_app.preprocess_post(). Returns
        (chunks, token_count) or None when the post is rejected."""
        cleaned = clean_content(text)
        if cleaned is None or len(cleaned) == 0:
            return None
        return self.chunk_post(cleaned, post_id)

    def pop_counters(self):
        truncated, fallback = self.truncated_chunks, self.regex_fallbacks
        self.truncated_chunks = 0
        self.regex_fallbacks = 0
        return truncated, fallback


def ensure_tokenizer(path, url=DEFAULT_TOKENIZER_URL):
    """Download the jina-v5-small tokenizer.json if it is not cached yet.

    Same source as scripts/setup_ubuntu.sh (jinaai/jina-embeddings-v5-text-small),
    which is the tokenizer hivesense uses for chunking.
    """
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading tokenizer from %s ..." % url, file=sys.stderr)
    with urlopen(url, timeout=60) as resp, open(path, "wb") as out:
        out.write(resp.read())

    if path.stat().st_size == 0:
        path.unlink()
        raise RuntimeError("downloaded tokenizer is empty: %s" % url)
    return path


def main():
    """Ad-hoc self check: chunk a sample text and print chunk stats."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tokenizer", default=str(Path(__file__).parent / "tokenizer.json"))
    parser.add_argument("--document-prefix", default="Document: ")
    parser.add_argument("--tokens-per-chunk", type=int, default=2048)
    parser.add_argument("--overlap-amount", type=float, default=0.10)
    parser.add_argument("--min-token-threshold", type=int, default=75)
    parser.add_argument("--text-file", help="read the post text from this file instead")
    args = parser.parse_args()

    ensure_tokenizer(args.tokenizer)
    chunker = PostChunker(
        args.tokenizer,
        document_prefix=args.document_prefix,
        max_tokens=args.tokens_per_chunk,
        min_new_ratio=1 - args.overlap_amount,
        min_token_threshold=args.min_token_threshold,
    )
    text = open(args.text_file).read() if args.text_file else (
        "Title of the post.\n\n" + "This is a sample sentence. " * 600)

    started = time.monotonic()
    result = chunker.preprocess_post(text, 0)
    elapsed = time.monotonic() - started
    if result is None:
        print("discarded (below %d tokens)" % args.min_token_threshold)
        return
    chunks, token_count = result
    print("post tokens: %d, chunks: %d, prep: %.3fs" % (token_count, len(chunks), elapsed))
    for idx, chunk in enumerate(chunks):
        print("  chunk %d: %d tokens" % (idx, chunker.count_tokens(chunk)))


if __name__ == "__main__":
    main()
