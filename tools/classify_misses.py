"""Classify replay misses into categories GROUNDED IN OBSERVED DATA.

Not an a priori taxonomy. Every category below was derived by inspecting an
actual miss from tools/replay.py and asking why the matcher did not fire.

CATEGORIES
----------
co_change_addition
    The file gained lines and lost none (+N/-0). Nothing in it was BROKEN by the
    seed change -- it was extended as part of the same feature work. Two of the
    three residual misses were this: deno#36441 touched ext/crypto/shared.rs
    (+36/-0) and tests/unit/webcrypto_test.ts (+56/-0), both pure additions.
    Counting these as misses penalises a breaking-change tool for not predicting
    feature work, so they are reported and excluded from recall rather than
    charged against it. This is a LABEL refinement, not a Ripple excuse: the
    observed-diff label is complete by construction, which means it also
    contains co-change that is not propagation.

unsupported_language
    Ripple has no matcher for the file's language. 24 of 36 label files in
    kubernetes#109798 are YAML manifests and shell scripts -- roughly two-thirds
    of the real work in that PR is outside Ripple's reach entirely. Reported as
    its own category because it is a capability gap, not a matching failure.

abbreviation_alias
    The file references the removed thing by a name no variant generator could
    derive. kubernetes#109798's test/e2e/framework/framework.go removes
    `SkipPrivilegedPSPBinding` -- PSP is a domain abbreviation of
    podsecuritypolicy. generate_variants() produces case and separator variants;
    it cannot invent an acronym. This is the genuinely hard residue and the kind
    of case the benchmark exists to expose.

low_confidence
    A symbol variant IS present in the file but every occurrence classified
    below min_confidence -- e.g. only inside a string literal or comment. A
    threshold or classifier question, distinct from not finding the name at all.

symbol_absent_other
    Symbol absent, deletions present, no abbreviation detected. Unexplained;
    kept as a distinct bucket so it does not silently absorb the others.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def acronym(s: str) -> str:
    """PSP from PodSecurityPolicy / pod_security_policy / podSecurityPolicy."""
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", s)
    return "".join(p[0] for p in parts if p).upper()


def alias_candidates(symbol: str, title: str = "") -> list[str]:
    """Acronyms the target could plausibly be referred to by.

    A package DIRECTORY name is all lowercase with no word boundaries --
    `podsecuritypolicy` yields only 'P', so no acronym is derivable from it. The
    PR title carries the human-readable name WITH casing ("Remove
    PodSecurityPolicy admission plugin"), so CamelCase tokens there are the
    mechanical source for PSP. No dictionary or word-splitting required.
    """
    out = []
    a = acronym(symbol)
    if len(a) >= 2:
        out.append(a)
    for tok in re.findall(r"\b[A-Z][A-Za-z0-9]{5,}\b", title or ""):
        # Only when the token IS the target under separator/case normalisation.
        if norm(tok) == norm(symbol):
            a2 = acronym(tok)
            if len(a2) >= 2:
                out.append(a2)
    return sorted(set(out))


def classify(path: str, content: str | None, lang: str, symbol: str,
             additions: int, deletions: int, variants: list[str],
             title: str = "") -> str:
    if deletions == 0 and additions > 0:
        return "co_change_addition"
    if lang == "unknown":
        return "unsupported_language"
    if content is None:
        return "content_unavailable"
    present = [v for v in variants if re.search(re.escape(v), content)]
    if present:
        return "low_confidence"
    for ac in alias_candidates(symbol, title):
        if re.search(rf"(?<![A-Za-z0-9]){ac}(?![a-z])", content):
            return "abbreviation_alias"
    return "symbol_absent_other"


def derive_difficulty(entry: dict) -> dict:
    """Difficulty from MEASURED properties, not asserted values.

    PropBench entries currently carry `difficulty: easy` and
    `confidence_an_expert_would_predict: 0.5` assigned by the miner. These are
    computed instead, so a category like "same package, symbol absent" is
    discoverable from data rather than declared.
    """
    scored = entry.get("scored", 0)
    flagged = entry.get("flagged", 0)
    cats = entry.get("miss_categories", {})
    hard = cats.get("abbreviation_alias", 0) + cats.get("symbol_absent_other", 0)
    return {
        "label_size": entry.get("label_size", 0),
        "scored": scored,
        "recall_pct": entry.get("recall_pct"),
        "unsupported_share_pct": round(
            100.0 * cats.get("unsupported_language", 0) / entry["label_size"], 1
        ) if entry.get("label_size") else None,
        "hard_miss_count": hard,
        "derived_difficulty": (
            "easy" if scored and flagged == scored
            else "hard" if hard else "medium"
        ),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="path_signal")
    ap.add_argument("--ripple", default="/home/aakkaash/.meshclaw/workspace/ripple")
    args = ap.parse_args()

    sys.path.insert(0, args.ripple)
    sys.path.insert(0, str(HERE))
    from app.rag_engine import _detect_language
    from app.smart_consumer_finder import generate_variants
    from replay import fetch_content
    from extract_seed import extract
    from validate_provenance import load_entries, reference
    # PR titles carry the human-readable name with casing; the package
    # directory name does not. Needed for acronym derivation.
    titles = {}
    for en in load_entries(Path(args.ripple).parent / "judgment-engine" / "datasets"):
        rf = reference(en)
        if rf and rf[0] == "gh_pr":
            titles[f"{rf[1][0]}#{rf[1][1]}"] = str(en.get("title", ""))

    results = json.loads((HERE / ".replay_results.json").read_text())
    if args.tag not in results:
        print(f"no results for tag {args.tag!r}", file=sys.stderr)
        return 2
    patches = json.loads((HERE / ".patch_cache.json").read_text())
    bases = json.loads((HERE / ".base_cache.json").read_text())

    print(f"miss classification  [tag={args.tag}]\n")
    totals: dict[str, int] = {}
    enriched = []

    for e in results[args.tag]["entries"]:
        key = f"{e['repo']}#{e['pr']}"
        r = extract(patches[key])
        sha = bases.get(key)
        meta = {f["filename"]: f for f in patches[key]}
        variants = generate_variants(r["symbol"])
        cats: dict[str, int] = {}
        detail = []

        # Misses the matcher reported, plus files excluded for language.
        for path in e["missed_files"] + e.get("unsupported_lang", []):
            m = meta.get(path, {})
            lang = _detect_language(path)
            content = fetch_content(e["repo"], sha, path) if sha else None
            c = classify(path, content, lang, r["symbol"],
                         m.get("additions", 0), m.get("deletions", 0), variants,
                         title=titles.get(key, ""))
            cats[c] = cats.get(c, 0) + 1
            totals[c] = totals.get(c, 0) + 1
            detail.append((c, path))

        e["miss_categories"] = cats
        e["difficulty"] = derive_difficulty(e)
        enriched.append(e)

        print(f"  {key}  vector={e['vector']}")
        for c, path in sorted(detail):
            print(f"    {c:22} {path[-58:]}")
        print(f"    derived difficulty: {e['difficulty']['derived_difficulty']}"
              f"  (unsupported {e['difficulty']['unsupported_share_pct']}% of label,"
              f" hard misses {e['difficulty']['hard_miss_count']})")

    print("\n" + "=" * 62)
    print("CATEGORY TOTALS")
    for c, n in sorted(totals.items(), key=lambda x: -x[1]):
        print(f"  {c:24} {n:4}")

    # Recall recomputed with non-propagation files excluded.
    agg = results[args.tag]["aggregate"]
    scored = agg["flagged"] + agg["missed"]
    addition_misses = totals.get("co_change_addition", 0)
    adj_scored = scored - addition_misses
    print()
    print(f"  reported recall      : {agg['flagged']}/{scored} = "
          f"{100.0*agg['flagged']/scored:.1f}%")
    if adj_scored > 0:
        print(f"  excluding pure adds  : {agg['flagged']}/{adj_scored} = "
              f"{100.0*agg['flagged']/adj_scored:.1f}%   "
              f"({addition_misses} file(s) gained lines and lost none)")

    results[args.tag]["entries"] = enriched
    results[args.tag]["miss_categories"] = totals
    (HERE / ".replay_results.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
