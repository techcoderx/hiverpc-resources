#!/usr/bin/env python3
"""Sample real posts and query strings from a Hivemind database.

The sample is cached to JSON so repeated benchmark runs embed exactly the
same posts and queries, keeping results comparable without re-querying the
(remote) Hivemind instance every time.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

POSTS_SQL = """
SELECT hp.id,
       ha.name AS author,
       hpl.permlink AS permlink,
       hpd.title,
       hpd.body
  FROM hivemind_app.hive_posts hp
  JOIN hivemind_app.hive_post_data hpd ON hpd.id = hp.id
  JOIN hivemind_app.hive_accounts ha ON ha.id = hp.author_id
  JOIN hivemind_app.hive_permlink_data hpl ON hpl.id = hp.permlink_id
 WHERE hp.depth = 0
   AND hp.is_valid
   AND NOT hp.is_muted
   AND NOT hp.is_hidden
   AND hp.counter_deleted = 0
   AND hp.created_at >= now() - make_interval(days => %(days)s)
 ORDER BY random()
 LIMIT %(count)s
"""

QUERIES_SQL = """
SELECT hpd.title
  FROM hivemind_app.hive_posts hp
  JOIN hivemind_app.hive_post_data hpd ON hpd.id = hp.id
 WHERE hp.depth = 0
   AND hp.is_valid
   AND NOT hp.is_muted
   AND NOT hp.is_hidden
   AND hp.counter_deleted = 0
   AND char_length(hpd.title) BETWEEN 10 AND 200
   AND hp.created_at >= now() - make_interval(days => %(days)s)
 ORDER BY random()
 LIMIT %(count)s
"""


def fetch_sample(db_url, posts, queries, window_days):
    """Fetch posts and query titles from the Hivemind database."""
    posts_out, queries_out = [], []

    with psycopg.connect(db_url, row_factory=dict_row, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            if posts > 0:
                print("Sampling %d posts from %s (last %d days)..."
                      % (posts, db_url, window_days), file=sys.stderr)
                cur.execute(POSTS_SQL, {"days": window_days, "count": posts})
                for row in cur.fetchall():
                    if not row["body"]:
                        continue
                    posts_out.append({
                        "id": row["id"],
                        "author": row["author"],
                        "permlink": row["permlink"],
                        "title": row["title"],
                        "body": row["body"],
                    })
            if queries > 0:
                print("Sampling %d query titles..." % queries, file=sys.stderr)
                cur.execute(QUERIES_SQL, {"days": window_days, "count": queries})
                queries_out = [row["title"] for row in cur.fetchall()]

    print("Sampled %d post(s) and %d query title(s)"
          % (len(posts_out), len(queries_out)), file=sys.stderr)
    return posts_out, queries_out


def save_sample(cache_path, db_url, window_days, posts, queries):
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    sample = {
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "db_url": db_url,
        "window_days": window_days,
        "posts": posts,
        "queries": queries,
    }
    with open(cache_path, "w") as out:
        json.dump(sample, out)
    print("Saved sample cache to %s" % cache_path, file=sys.stderr)


def load_sample(cache_path):
    with open(cache_path) as inp:
        sample = json.load(inp)
    return sample["posts"], sample["queries"]


def load_or_sample(cache_path, db_url, posts, queries, window_days, refresh=False):
    """Return (posts, queries), loading the cache when possible.

    The cache is reused only when it holds at least as many posts and
    queries as requested; otherwise the database is re-sampled (and the
    cache overwritten) so every run embeds a deterministic sample.
    """
    cache_path = Path(cache_path)
    if not refresh and cache_path.exists():
        cached_posts, cached_queries = load_sample(cache_path)
        if len(cached_posts) >= posts and len(cached_queries) >= queries:
            print("Reusing sample cache %s (%d posts, %d queries)"
                  % (cache_path, len(cached_posts), len(cached_queries)),
                  file=sys.stderr)
            return cached_posts[:posts], cached_queries[:queries]

    fetched_posts, fetched_queries = fetch_sample(
        db_url, posts, queries, window_days)
    if not fetched_posts and posts > 0:
        raise RuntimeError(
            "no posts sampled from %s; check --db-url/--sample-window-days" % db_url)
    save_sample(cache_path, db_url, window_days, fetched_posts, fetched_queries)
    return fetched_posts, fetched_queries
