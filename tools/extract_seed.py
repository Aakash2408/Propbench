"""Derive the SEED file and the removed SYMBOL from a real diff, mechanically.

WHY
---
PropBench's labels were authored, so they are incomplete: measured against the
real diffs of 18 verified entries, the stored consequence lists capture only
80.2% of what actually changed (and for kubernetes#109798, 3 files out of 78).
Scoring a tool against an incomplete label punishes it for finding files that
genuinely needed changing but were never written down.

This replaces authored labels with observed ones. The label becomes the changed
set from the diff; nothing is asserted.

THE HARD PART
-------------
A PR changes N files. Which is the trigger, and which identifier is the
propagation vector? The existing miner guesses and admits in every entry that
the "trigger heuristic may be wrong".

Rather than guess, pick the candidate that BEST EXPLAINS THE REST OF THE SET:

  1. From every file's deleted lines, collect declaration-shaped identifiers.
  2. For each candidate, count how many OTHER changed files mention it.
  3. The winner is the identifier that most of the changed set references.
  4. The seed is the file where that identifier was declared.

That is derivable from the diff alone, needs no judgment, and optimises for
exactly what a consumer-finder consumes: a symbol to search for.

Entries where no candidate explains any other file are SKIPPED and counted --
they are propagation with no shared removed symbol, a real category the
benchmark should report rather than fabricate a symbol for.

CORPUS COMPOSITION (measured, 2026-08-16)
-----------------------------------------
The dominant skip reason is not a weakness in the patterns above -- it is that
PropBench mined CO-CHANGE PRs, not BREAKING-CHANGE PRs. Of 629 github-api-mined
entries, only 61 (9.7%) are removal-shaped by title/intent. grpc-go#9221 is
typical of the rest: +714/-2, a pure feature addition, so there is no removed
symbol to find and correctly none is invented.

Co-change is a superset of breaking-change propagation. Both are legitimate
research targets, but only the removal-shaped subset exercises a tool whose job
is fixing consumers after a contract breaks. Use --removal-only to target it.
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CACHE = Path(__file__).parent / ".patch_cache.json"

# A PR is removal-shaped when its stated intent describes taking something away.
REMOVAL_INTENT = re.compile(
    r"\b(remov|delet|drop|rename|deprecat|break|migrat|replac|retir|purge)", re.I
)

# Declaration-shaped identifier patterns per language. Deliberately NOT a
# general parser -- we only need identifiers DECLARED on a removed line, which
# is a much smaller problem than parsing the language.
#
# All patterns are ANCHORED at line start. An earlier version allowed an
# optional receiver group (`\(?[^)]*\)?`) before the capture, which let the
# match begin at an arbitrary offset INSIDE an identifier: `type
# PodSecurityPolicyProvider` yielded the fragment `Policy`, so the real symbol
# was never a candidate and no ranking rule could have recovered it. Same family
# as the `[^}]*` proto bug and the `\b` underscore bug -- a regex matching
# somewhere it should not.
_ID = r"([A-Za-z_][A-Za-z0-9_]*)"
DECL = [
    # go: type X / func X( / func (recv T) X(
    re.compile(rf"^\s*type\s+{_ID}"),
    re.compile(rf"^\s*func\s+{_ID}\s*[\(\[]"),
    re.compile(rf"^\s*func\s+\([^)]*\)\s+{_ID}\s*\("),
    # python / ruby / js / ts
    re.compile(rf"^\s*(?:async\s+)?def\s+{_ID}\s*\("),
    re.compile(rf"^\s*(?:export\s+)?(?:abstract\s+)?(?:class|interface|enum|trait|struct|module)\s+{_ID}"),
    re.compile(rf"^\s*(?:export\s+)?(?:async\s+)?function\s+{_ID}\s*\("),
    re.compile(rf"^\s*(?:export\s+)?(?:const|let|var|val)\s+{_ID}\s*[:=]"),
    # rust
    re.compile(rf"^\s*(?:pub\s+)?(?:async\s+)?fn\s+{_ID}\s*[<\(]"),
    re.compile(rf"^\s*(?:pub\s+)?(?:struct|enum|trait|type)\s+{_ID}"),
    # java / c# / kotlin members and types
    re.compile(rf"^\s*(?:@\w+\s+)*(?:public|private|protected|internal)\s+(?:static\s+)?(?:final\s+)?(?:class|interface|enum|record)\s+{_ID}"),
    re.compile(rf"^\s*(?:public|private|protected|internal)\s+[\w<>\[\],\s\.]+?\s+{_ID}\s*[\(;=]"),
    # proto / thrift field:  optional string phone_number = 4;
    re.compile(rf"^\s*(?:optional|required|repeated)?\s*[\w.<>]+\s+{_ID}\s*=\s*\d+\s*;"),
    # A removed PARAMETER declaration -- `name: Type` (kotlin/swift/ts/python) or
    # `name: Type,` inside a signature. Removing a parameter is one of the most
    # common breaking changes there is, and it was invisible here: the previous
    # pattern was `{_ID}\s*:\s*[\w\[\]!]+\s*$`, whose character class excludes
    # generics, so `sessionIsAliveFlagFile: Lazy<File>` never became a candidate.
    #
    # On JetBrains/kotlin#7223 that mattered a lot. The PR removed
    # sessionIsAliveFlagFile from a signature across ~10 sibling files, all of
    # which name it. With it unavailable the extractor selected
    # `compileInProcess`, which those siblings do NOT name -- so every one of
    # them was recorded as a miss, and the sub-classification attributed them to
    # path locality. They were symbol misses with the wrong symbol.
    re.compile(rf"^\s*{_ID}\s*:\s*[\w\[\]<>,.?!\s|&]+,?\s*$"),
    # graphql / yaml-ish key removal
    re.compile(rf"^\s*{_ID}\s*:\s*[\w\[\]!]+\s*$"),
    # module-level constant
    re.compile(rf"^\s*([A-Z][A-Z0-9_]{{3,}})\s*=\s*"),
]

# Identifiers too generic to be a propagation vector.
STOP = {
    "error", "err", "test", "tests", "true", "false", "null", "nil", "none",
    "string", "int", "bool", "float", "self", "this", "value", "values",
    "result", "data", "name", "type", "types", "config", "options", "context",
    "request", "response", "client", "server", "handler", "params", "args",
    "main", "init", "new", "get", "set", "add", "remove", "delete", "update",
    "list", "map", "func", "class", "struct", "interface", "const", "var",
    "import", "export", "default", "return", "length", "count", "index",
}

TEST_HINT = re.compile(r"(^|/)(tests?|__tests__|spec|e2e|testdata)(/|$)|_test\.|\.test\.|test_|Test\.java|Tests\.cs")
DOC_HINT = re.compile(r"(^|/)(docs?|documentation|website|examples?)(/|$)|\.(md|txt|rst|adoc)$")


def is_test(path: str) -> bool:
    return bool(TEST_HINT.search(path))


def is_doc(path: str) -> bool:
    return bool(DOC_HINT.search(path))


def deleted_lines(patch: str) -> list[str]:
    return [ln[1:] for ln in (patch or "").splitlines()
            if ln.startswith("-") and not ln.startswith("---")]


def all_lines(patch: str) -> str:
    return "\n".join(ln[1:] for ln in (patch or "").splitlines()
                     if ln and ln[0] in "+- ")


def pre_lines(patch: str) -> str:
    """Only lines that existed BEFORE the change: context and deletions.

    A propagation vector must have been PRESENT in the files that had to adapt.
    Scoring against added lines too lets a symbol the PR INTRODUCED win: on
    elasticsearch#153666 that selected `ruleChain`, which appears 0 times in all
    7 label files at the base commit -- so the matcher correctly scored 0/7 and
    the harness looked like a Ripple failure when the label was simply wrong.
    """
    return "\n".join(ln[1:] for ln in (patch or "").splitlines()
                     if ln and ln[0] in "- ")


def candidates(patch: str) -> set[str]:
    """Declaration-shaped identifiers on removed lines.

    Dunders and underscore-wrapped names are stripped before the STOP check.
    `'__init__'.lower()` is not in STOP (which contains 'init'), so __init__ was
    accepted as a propagation symbol -- and on tiangolo/fastapi#9816 it was
    SELECTED, because a dunder present in nearly every Python package trivially
    "explains" every other changed file. That single entry then produced 58 of
    the corpus's 448 misses (13%), depressing measured recall by ~3 points with a
    label defect rather than a tool limitation.
    """
    found = set()
    for line in deleted_lines(patch):
        for pat in DECL:
            for m in pat.finditer(line):
                ident = m.group(1)
                # Compare on the bare name: __init__ -> init, _private -> private
                bare = ident.strip("_")
                if not bare or bare.lower() in STOP or len(bare) < 3:
                    continue
                found.add(ident)
    return found


def mentions(text: str, ident: str) -> int:
    """Count references, using the underscore-safe boundary -- \\b fails on
    Go's Status_LEGACY because '_' is a word character. Same trap that has now
    appeared four times in Ripple."""
    return len(re.findall(rf"(?<![A-Za-z0-9]){re.escape(ident)}(?![A-Za-z0-9])", text))


def path_affinity(ident: str, paths: list[str]) -> int:
    """How many changed file PATHS contain this identifier.

    This is the discriminator that content-frequency alone lacks. Ranking purely
    by "explains the most files" picks generic method names: on
    kubernetes#109798 it chose `Validate`, which appears in 30 of 78 changed
    files and means nothing, over `PodSecurityPolicy`, the API actually removed.

    A propagation vector NAMES the thing being removed, so it tends to appear in
    the paths of the files affected -- pkg/security/podsecuritypolicy/... --
    whereas boilerplate like Validate or Get does not. Comparison strips
    separators and case so PodSecurityPolicy matches pod_security_policy and
    podsecuritypolicy/.
    """
    needle = re.sub(r"[^a-z0-9]", "", ident.lower())
    if len(needle) < 6:  # too short for a path match to be meaningful
        return 0
    return sum(1 for p in paths
               if needle in re.sub(r"[^a-z0-9]", "", p.lower()))


def package_vector(files: list[dict]) -> dict | None:
    """Detect a PACKAGE-DELETION change, which has no propagation SYMBOL.

    kubernetes#109798 ("Remove PodSecurityPolicy admission plugin") is the
    canonical case: 63 of 78 files are status=removed and 42 share the prefix
    pkg/security/podsecuritypolicy/. The unit removed is a DIRECTORY, and the
    type `PodSecurityPolicy` is not even in the diff -- it lives in
    pkg/apis/policy/types.go, removed by a different PR.

    This matters because a symbol query is the wrong query here. Ranking
    identifiers on this PR produced `Policy`, then `mustRunAs` -- neither is the
    vector. Consumers of a deleted package are (a) its own members and (b) files
    importing its path; both are path-shaped, not name-shaped.

    Recording the vector KIND is part of the label, not a detail.
    """
    removed = [f["filename"] for f in files if f.get("status") == "removed"]
    if len(removed) < 3 or len(removed) < 0.4 * len(files):
        return None
    counts: collections.Counter = collections.Counter()
    for path in removed:
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            counts["/".join(parts[:i])] += 1
    best, n = None, 0
    for prefix, c in counts.items():
        if c >= max(3, 0.5 * len(removed)) and (best is None or len(prefix) > len(best)):
            best, n = prefix, c
    if not best:
        return None
    return {
        "vector": "package",
        "seed": best + "/",
        "symbol": best.rsplit("/", 1)[-1],
        "removed_in_package": n,
        "removed_total": len(removed),
    }


def extract(files: list[dict]) -> dict:
    """files: [{filename, patch, additions, deletions, status}]

    Returns {vector, seed, symbol, label, ...} or {skipped_reason}.
    """
    # A package deletion takes precedence: it has no single symbol, so ranking
    # identifiers yields an arbitrary winner.
    _pkg = package_vector(files)
    if _pkg:
        _patches = {f["filename"] for f in files}
        _label = sorted(p for p in _patches if not p.startswith(_pkg["seed"]))
        _pkg["label"] = _label
        _pkg["label_size"] = len(_label)
        _pkg["members"] = len(_patches) - len(_label)
        return _pkg
    patches = {f["filename"]: (f.get("patch") or "") for f in files}
    # pre_lines, not all_lines: the vector must pre-exist in adapting files.
    texts = {p: pre_lines(t) for p, t in patches.items()}
    paths = list(patches)

    # Candidate -> (path affinity, files explained by content)
    scores: dict[tuple[str, str], tuple[int, int]] = {}
    for path, patch in patches.items():
        # Tests and docs describe the change; they do not declare the contract.
        if is_test(path) or is_doc(path):
            continue
        for ident in candidates(patch):
            others = sum(1 for p2, t2 in texts.items()
                         if p2 != path and mentions(t2, ident) > 0)
            if not others:
                continue
            aff = path_affinity(ident, paths)
            key = (path, ident)
            prev = scores.get(key, (0, 0))
            scores[key] = (max(prev[0], aff), max(prev[1], others))

    if not scores:
        return {"skipped_reason": "no declared symbol explains any other changed file"}

    # Rank by path affinity FIRST -- specificity beats frequency. Then files
    # explained, then identifier length (more specific), then fewest additions
    # in the seed (a removal, not a rewrite).
    adds = {f["filename"]: f.get("additions", 0) for f in files}
    (seed, symbol), (aff, explains) = max(
        scores.items(),
        key=lambda kv: (kv[1][0], kv[1][1], len(kv[0][1]), -adds.get(kv[0][0], 0)),
    )
    label = sorted(p for p in patches if p != seed)
    return {
        "vector": "symbol",
        "seed": seed,
        "symbol": symbol,
        "label": label,
        "explains": explains,
        "path_affinity": aff,
        "label_size": len(label),
    }


def fetch_pr_files(repo: str, num: str, token: str, cache: dict) -> list[dict] | None:
    """Delegates to gh_cache so this tool and validate_provenance share ONE
    cached call to /pulls/{n}/files instead of making the same request twice.
    `token` and `cache` are retained for signature compatibility; gh_cache owns
    both now (token from the environment, cache on disk)."""
    from gh_cache import pr_files, Transient
    try:
        return pr_files(repo, num)
    except Transient as e:
        print(f"    {repo}#{num}: {e}", file=sys.stderr)
        return None


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--removal-only", action="store_true",
                    help="only entries whose intent describes a removal -- the "
                         "subset relevant to breaking-change propagation (61 of "
                         "629 mined entries)")
    ap.add_argument("--datasets", default=str(Path(__file__).parent.parent / "datasets"))
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).parent))
    from validate_provenance import load_entries, reference, entry_files

    token = os.environ.get("GITHUB_TOKEN", "")
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    entries = load_entries(Path(args.datasets))

    # Prefer entries already proven resolvable in Stage 1.
    prov = Path(__file__).parent / ".provenance_cache.json"
    verified_keys = set()
    if prov.exists():
        for k, v in json.loads(prov.read_text()).items():
            if v.get("ok"):
                verified_keys.add(k)

    targets = []
    for e in entries:
        ref = reference(e)
        if not ref or ref[0] != "gh_pr":
            continue
        if args.removal_only:
            blurb = f"{e.get('title','')} {(e.get('trigger') or {}).get('intent','')}"
            if not REMOVAL_INTENT.search(blurb):
                continue
        key = f"{ref[0]}:{ref[1][0]}:{ref[1][1]}"
        if verified_keys and key not in verified_keys and f"{ref[1][0]}#{ref[1][1]}" not in cache:
            continue
        targets.append((e, ref))
    targets = targets[: args.limit]

    print(f"seed+symbol extraction on {len(targets)} verified entr(ies)  "
          f"(token: {'yes' if token else 'NO'})\n")
    ok, skipped = [], []
    for e, ref in targets:
        repo, num = ref[1]
        files = fetch_pr_files(repo, num, token, cache)
        if not files:
            skipped.append((e.get("id"), "fetch failed"))
            continue
        r = extract(files)
        if "skipped_reason" in r:
            skipped.append((e.get("id"), r["skipped_reason"]))
            continue
        authored = entry_files(e)
        r["authored_label_size"] = len(authored)
        r["id"] = e.get("id")
        r["repo"] = repo
        ok.append(r)
    CACHE.write_text(json.dumps(cache))

    print(f"{'id':30} {'symbol':24} {'expl':>4} {'obs':>4} {'auth':>5}  seed")
    for r in ok:
        print(f"{str(r['id'])[:30]:30} {r['symbol'][:24]:24} {r['explains']:4} "
              f"{r['label_size']:4} {r['authored_label_size']:5}  {r['seed'][:44]}")
    print()
    print(f"extracted : {len(ok)}/{len(targets)}")
    print(f"skipped   : {len(skipped)}")
    for i, why in skipped:
        print(f"    {str(i)[:34]:36} {why}")
    if ok:
        obs = sum(r["label_size"] for r in ok)
        auth = sum(r["authored_label_size"] for r in ok)
        print()
        print(f"observed label files : {obs}")
        print(f"authored label files : {auth}")
        print(f"authored labels captured {100*auth/obs:.1f}% of the observed set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
