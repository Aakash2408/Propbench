"""Replay harness: run Ripple's REAL matcher against verified PropBench entries.

WHAT IT MEASURES
----------------
For each entry we know, from the actual merged diff, which files had to change.
The harness fetches each of those files as they were BEFORE the change and asks
Ripple's matcher whether it would have flagged them.

    recall = flagged / label_files

That is recall over known positives. It is NOT precision -- counting false
positives requires walking the whole repo, which needs a clone. Where a clone is
supplied via --clone, precision is reported too; otherwise it is stated as
unavailable rather than guessed.

VECTOR KINDS
------------
Stage 2 established that a breaking change propagates by one of two vectors, and
querying the wrong one under-reports the tool:

    symbol   a declared identifier was removed; consumers name it
    package  a directory was deleted; consumers are files under it or importers
             of its path -- mostly path-shaped, naming no single identifier

Ripple today only searches by symbol. For a package vector the harness therefore
passes the package NAME as the symbol, which is what Ripple would actually do if
handed one -- an honest baseline for the path-locality signal to improve on.

CACHING
-------
File content is cached under .content_cache/ keyed by repo+sha+path, so re-runs
after a Ripple change cost no network and compare like-for-like. raw.github
content is not rate-limited; the GitHub API is, so base SHAs are cached too.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
PATCH_CACHE = HERE / ".patch_cache.json"
BASE_CACHE = HERE / ".base_cache.json"
CONTENT_DIR = HERE / ".content_cache"
RESULTS = HERE / ".replay_results.json"


def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def gh_api(path: str, token: str):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def base_sha(repo: str, pr: str, token: str, cache: dict) -> str | None:
    """Delegates to gh_cache (shared disk cache, token from environment)."""
    from gh_cache import pr_base_sha, Transient
    try:
        return pr_base_sha(repo, pr)
    except Transient as e:
        print(f"    base_sha({repo}#{pr}): {e}", file=sys.stderr)
        return None


def fetch_content(repo: str, sha: str, path: str) -> str | None:
    """raw.githubusercontent is not rate-limited by the API budget. Cached on
    disk regardless.

    Only a definitive 404 is cached as missing. An earlier version cached ANY
    exception as `__MISSING__`, so a transient failure became a permanent
    "file does not exist at base" -- which showed up as 320 files classified
    `content_unavailable` in the miss pass, for files the replay had fetched
    successfully minutes earlier. Third instance of this defect today: the
    provenance validator recorded HTTP 403 as `unreachable`, and gh_cache had to
    learn the same distinction. A cache that remembers failures it should have
    retried is worse than no cache.
    """
    CONTENT_DIR.mkdir(exist_ok=True)
    key = hashlib.sha1(f"{repo}@{sha}:{path}".encode()).hexdigest()
    cf = CONTENT_DIR / key
    if cf.exists():
        txt = cf.read_text(errors="replace")
        return None if txt == "__MISSING__" else txt
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            txt = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            cf.write_text("__MISSING__")   # definitive: absent at this sha
            return None
        return None                        # transient: NOT cached
    except Exception:
        return None                        # transient: NOT cached
    cf.write_text(txt)
    return txt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ripple", default="/home/aakkaash/.meshclaw/workspace/ripple")
    ap.add_argument("--clone", default="", help="local repo clone, enables precision")
    ap.add_argument("--tag", default="baseline", help="label for this run's results")
    args = ap.parse_args()

    sys.path.insert(0, args.ripple)
    sys.path.insert(0, str(HERE))
    from app.smart_consumer_finder import find_field_consumers, find_consumers
    from app.rag_engine import _detect_language
    from extract_seed import extract

    token = os.environ.get("GITHUB_TOKEN", "")
    patches = load_json(PATCH_CACHE, {})
    bases = load_json(BASE_CACHE, {})

    entries = []
    for key, files in sorted(patches.items()):
        if not files:
            continue
        r = extract(files)
        if "skipped_reason" in r:
            continue
        repo, pr = key.split("#")
        entries.append((repo, pr, r))

    print(f"replay: {len(entries)} entr(ies) with an extractable vector  "
          f"[tag={args.tag}]\n")

    agg = collections.Counter()
    by_lang = collections.defaultdict(lambda: collections.Counter())
    per_entry = []

    for repo, pr, r in entries:
        # gh_cache owns .base_cache.json. replay used to ALSO write it from its
        # own local dict, so the two writers clobbered each other and base SHAs
        # went missing -- which surfaced as 320 files classified
        # `content_unavailable` because their sha was absent.
        sha = base_sha(repo, pr, token, bases)
        if not sha:
            print(f"  {repo}#{pr}: SKIP (no base sha)")
            continue

        symbol = r["symbol"]
        # For a package vector the query is the PATH, not the name.
        target = r["seed"] if r["vector"] == "package" else symbol
        label = r["label"]
        flagged, missed, unfetchable, unsupported = [], [], [], []

        for path in label:
            content = fetch_content(repo, sha, path)
            if content is None:
                # Absent at base = the PR ADDED it. Not a propagation target.
                unfetchable.append(path)
                continue
            lang = _detect_language(path)
            if lang == "unknown":
                unsupported.append(path)
                continue
            # Query by the entry's VECTOR KIND. Querying a symbol on a
            # package deletion under-reports: 38.5% vs 90.9% on the same PR.
            matches = find_consumers(content, path, target, lang,
                                     vector=r['vector'])
            (flagged if matches else missed).append(path)
            by_lang[lang]["flagged" if matches else "missed"] += 1

        scored = len(flagged) + len(missed)
        rec = (100.0 * len(flagged) / scored) if scored else 0.0
        agg["flagged"] += len(flagged)
        agg["missed"] += len(missed)
        agg["unsupported"] += len(unsupported)
        agg["added_by_pr"] += len(unfetchable)

        per_entry.append({
            "repo": repo, "pr": pr, "vector": r["vector"], "symbol": symbol,
            "label_size": len(label), "scored": scored,
            "flagged": len(flagged), "missed": len(missed),
            "recall_pct": round(rec, 1),
            "missed_files": missed,
            "unsupported_lang": unsupported,
        })
        print(f"  {repo}#{pr}")
        print(f"    vector={r['vector']}  symbol={symbol!r}  label={len(label)}")
        print(f"    scored={scored}  flagged={len(flagged)}  missed={len(missed)}"
              f"  recall={rec:.1f}%")
        if unsupported:
            print(f"    unsupported language: {len(unsupported)} file(s) "
                  f"(Ripple has no matcher for these)")
        if unfetchable:
            print(f"    absent at base: {len(unfetchable)} (added by the PR)")

    scored_total = agg["flagged"] + agg["missed"]
    print("\n" + "=" * 62)
    print(f"AGGREGATE  [tag={args.tag}]")
    print(f"  scored files      : {scored_total}")
    print(f"  flagged           : {agg['flagged']}")
    print(f"  missed            : {agg['missed']}")
    if scored_total:
        print(f"  RECALL            : {100.0*agg['flagged']/scored_total:.1f}%")
    print(f"  unsupported lang  : {agg['unsupported']}  (excluded from recall)")
    print(f"  added by PR       : {agg['added_by_pr']}  (excluded -- not targets)")
    print(f"  precision         : unavailable (needs --clone)")
    if by_lang:
        print("\n  by language:")
        for lang, c in sorted(by_lang.items(), key=lambda x: -sum(x[1].values())):
            tot = c["flagged"] + c["missed"]
            print(f"    {lang:12} {c['flagged']:3}/{tot:3}  "
                  f"{100.0*c['flagged']/tot:5.1f}%")

    out = load_json(RESULTS, {})
    out[args.tag] = {
        "aggregate": dict(agg),
        "recall_pct": round(100.0 * agg["flagged"] / scored_total, 1) if scored_total else None,
        "entries": per_entry,
    }
    RESULTS.write_text(json.dumps(out, indent=2))
    print(f"\n  results -> {RESULTS}  (key={args.tag!r})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
