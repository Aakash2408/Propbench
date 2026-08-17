"""Sub-classify the `symbol_absent_other` misses. ANALYSIS ONLY -- no matcher.

WHY NOT WRITE A MATCHER YET
---------------------------
symbol_absent_other is the dominant miss category (301 of 448 misses on the
137-entry corpus). It is defined by ABSENCE: the file had real deletions, is in a
language Ripple matches, and contains neither the symbol nor any acronym
derivable from it. That says nothing about WHY, and a matcher built on a guess is
tuned to noise.

Every hypothesis below is mechanical and falsifiable against the cached content
and diffs. Nothing here infers intent.

HYPOTHESES
----------
substring_not_bounded   The symbol IS present as a raw substring but not as a
                        word-bounded token, so the matcher correctly rejected it
                        (e.g. `getUserName` when the symbol is `userName`). A
                        boundary/compound question, not an absence.
partial_token_overlap   A >=5-char component of a multi-word symbol appears
                        (`fresh_var` from `fresh_var_for_kind_with_span`).
                        Consumers referenced a related name, not this one.
seed_basename_present   The seed FILE's basename appears -- an import of the file
                        rather than a use of the symbol.
same_dir_as_seed        The file sits in the seed's directory: it changed because
                        its neighbour did. Path locality already covers this for
                        package vectors, but not for symbol vectors.
shares_package_prefix   Shares 2+ leading path segments with the seed. Weaker
                        form of the same coupling.
is_generated            Generated or vendored -- regenerated wholesale.
is_test                 Test or fixture file, changed because the thing it
                        exercises changed, with no textual link.
no_link_found           None of the above. Genuine judgment: propagation with no
                        textual trace, which is what PropBench exists to measure
                        and what no matcher can reach.

A file can satisfy several, so results are reported BOTH as first-match buckets
(ordered by how actionable a fix would be) and as independent counts -- the
overlap is itself informative.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent

TEST_HINT = re.compile(
    r"(^|/)(tests?|__tests__|spec|e2e|testdata|fixtures?|golden)(/|$)"
    r"|_test\.|\.test\.|test_|Test\.java|Tests\.cs|_spec\.")
GEN_HINT = re.compile(
    r"(^|/)(vendor|node_modules|generated|gen|dist|build|target)(/|$)"
    r"|\.pb\.go$|_pb2\.py$|\.g\.dart$|\.generated\.|autogen")


def tokens(symbol: str) -> list[str]:
    """>=5-char components of a multi-word identifier."""
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", symbol)
    return [p for p in parts if len(p) >= 5]


def bounded(text: str, ident: str) -> bool:
    return bool(re.search(
        rf"(?<![A-Za-z0-9]){re.escape(ident)}(?![A-Za-z0-9])", text))


def classify(path: str, content: str, symbol: str, seed: str) -> set[str]:
    tags: set[str] = set()
    seed_dir = seed.rstrip("/").rsplit("/", 1)[0] if "/" in seed else ""
    file_dir = path.rsplit("/", 1)[0] if "/" in path else ""

    if seed_dir and file_dir == seed_dir:
        tags.add("same_dir_as_seed")
    elif seed_dir:
        shared = 0
        for x, y in zip(seed_dir.split("/"), file_dir.split("/")):
            if x != y:
                break
            shared += 1
        if shared >= 2:
            tags.add("shares_package_prefix")

    if symbol and symbol in content and not bounded(content, symbol):
        tags.add("substring_not_bounded")

    for t in tokens(symbol):
        if bounded(content, t):
            tags.add("partial_token_overlap")
            break

    stem = seed.rstrip("/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if len(stem) >= 4 and stem in content:
        tags.add("seed_basename_present")

    if TEST_HINT.search(path):
        tags.add("is_test")
    if GEN_HINT.search(path):
        tags.add("is_generated")

    if not tags:
        tags.add("no_link_found")
    return tags


# Ordered by how actionable a fix would be, most actionable first.
PRIORITY = [
    "substring_not_bounded",
    "partial_token_overlap",
    "seed_basename_present",
    "same_dir_as_seed",
    "shares_package_prefix",
    "is_generated",
    "is_test",
    "no_link_found",
]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="yaml_shell")
    ap.add_argument("--ripple", default="/home/aakkaash/.meshclaw/workspace/ripple")
    args = ap.parse_args()

    sys.path.insert(0, args.ripple)
    sys.path.insert(0, str(HERE))
    from app.rag_engine import _detect_language
    from app.smart_consumer_finder import generate_variants
    from replay import fetch_content
    from extract_seed import extract
    from classify_misses import classify as miss_class
    from validate_provenance import load_entries, reference

    results = json.loads((HERE / ".replay_results.json").read_text())
    if args.tag not in results:
        print(f"no results for tag {args.tag!r}; have {list(results)}", file=sys.stderr)
        return 2
    patches = json.loads((HERE / ".patch_cache.json").read_text())
    bases = json.loads((HERE / ".base_cache.json").read_text())

    titles = {}
    for en in load_entries(Path(args.ripple).parent / "judgment-engine" / "datasets"):
        rf = reference(en)
        if rf and rf[0] == "gh_pr":
            titles[f"{rf[1][0]}#{rf[1][1]}"] = str(en.get("title", ""))

    first_bucket: collections.Counter = collections.Counter()
    independent: collections.Counter = collections.Counter()
    examples: dict[str, list[str]] = collections.defaultdict(list)
    total = unavailable = 0

    for e in results[args.tag]["entries"]:
        key = f"{e['repo']}#{e['pr']}"
        if key not in patches or not patches[key]:
            continue
        r = extract(patches[key])
        if "skipped_reason" in r:
            continue
        sha = bases.get(key)
        if not sha:
            continue
        meta = {f["filename"]: f for f in patches[key]}
        variants = generate_variants(r["symbol"])

        for path in e["missed_files"]:
            m = meta.get(path, {})
            lang = _detect_language(path)
            content = fetch_content(e["repo"], sha, path)
            cat = miss_class(path, content, lang, r["symbol"],
                             m.get("additions", 0), m.get("deletions", 0),
                             variants, title=titles.get(key, ""))
            if cat != "symbol_absent_other":
                continue
            total += 1
            if content is None:
                unavailable += 1
                continue
            tags = classify(path, content, r["symbol"], r["seed"])
            for t in tags:
                independent[t] += 1
            for p in PRIORITY:
                if p in tags:
                    first_bucket[p] += 1
                    if len(examples[p]) < 3:
                        examples[p].append(
                            f"{e['repo']}#{e['pr']} {path[-50:]} sym={r['symbol'][:22]}")
                    break

    scored = total - unavailable
    print(f"symbol_absent_other analysed: {total}"
          f"  (content unavailable: {unavailable})\n")
    if not scored:
        print("nothing to classify")
        return 0

    print("FIRST-MATCH BUCKETS (most actionable first)")
    for p in PRIORITY:
        n = first_bucket.get(p, 0)
        if n:
            print(f"  {p:24} {n:4}  {100.0*n/scored:5.1f}%")
    print()
    print("INDEPENDENT COUNTS (a file may satisfy several)")
    for t, n in independent.most_common():
        print(f"  {t:24} {n:4}  {100.0*n/scored:5.1f}%")
    print()
    print("EXAMPLES")
    for p in PRIORITY:
        if examples.get(p):
            print(f"  {p}:")
            for x in examples[p]:
                print(f"      {x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
