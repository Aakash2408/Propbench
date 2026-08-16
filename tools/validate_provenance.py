"""Provenance validator for PropBench entries.

WHY THIS EXISTS
---------------
tools/validate_dataset.py checks STRUCTURE -- required fields, path shapes,
duplicates. It never checks whether an entry corresponds to anything real. So
entries citing pull requests that do not exist passed validation and shipped in
the published dataset:

    oss-react-01    -> facebook/react#28270      does not exist
    oss-fastapi-01  -> tiangolo/fastapi#11117    does not exist
    oss-fastapi-03  -> tiangolo/fastapi#9816     does not exist
    oss-django-01   -> django/django#16553       exists, but is titled
                                                 "Increase coverage" -- unrelated
    oss-k8s-01      -> kubernetes/kubernetes#109798  REAL and matching

A benchmark's ground truth must be OBSERVED, not authored. Once consequence
files are asserted rather than read off a diff, nothing constrains them to be
true. This validator makes provenance falsifiable.

CLASSIFICATION
--------------
Offline (no network), from the identifier fields alone:

    resolvable            entry cites a public repo + PR or commit
    internal_unverifiable entry cites an internal (non-github) repo
    no_reference          entry cites nothing resolvable at all

Online (requires a token for meaningful throughput):

    verified     reference resolves AND the entry's consequence files overlap
                 the real changed-file set
    mismatched   reference resolves but the file lists do not intersect --
                 the citation points at an unrelated change
    unreachable  reference 404s or errors

USAGE
    python3 tools/validate_provenance.py                     # offline only
    python3 tools/validate_provenance.py --resolve            # + online
    python3 tools/validate_provenance.py --resolve --sample 20 # bounded
    GITHUB_TOKEN=... python3 tools/validate_provenance.py --resolve

Exits non-zero when any resolvable entry is mismatched or unreachable, so this
can gate CI once the dataset is cleaned.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

CACHE = Path(__file__).parent / ".provenance_cache.json"
GH_URL = re.compile(r"github\.com/([^/]+)/([^/]+)/(pull|commit)/([^/\s]+)")
SHA = re.compile(r"^[0-9a-f]{7,40}$")


def load_entries(datasets_dir: Path) -> list[dict]:
    out = []
    for yf in sorted(datasets_dir.glob("**/*.yaml")):
        try:
            docs = list(yaml.safe_load_all(yf.read_text()))
        except Exception:
            continue
        for d in docs:
            if isinstance(d, dict) and d.get("consequences"):
                d["_file"] = str(yf)
                out.append(d)
    return out


def source_type(entry: dict) -> str:
    s = str(entry.get("source", "?"))
    return "curated-url" if s.startswith("http") else s


def reference(entry: dict) -> tuple[str, tuple] | None:
    """What real-world artifact does this entry claim to describe?

    Returns (kind, params) or None. Internal repos are detected by absence of
    an 'owner/name' shape -- Amazon package names like 'GAMCoreModel' have no
    slash, so they cannot be github coordinates.
    """
    repo = entry.get("source_repo") or entry.get("repo") or ""
    pr = entry.get("source_pr")
    sha = entry.get("source_commit")
    src = str(entry.get("source", ""))

    m = GH_URL.search(src)
    if m:
        owner, name, kind, ident = m.groups()
        return ("gh_pr" if kind == "pull" else "gh_commit", (f"{owner}/{name}", ident))

    if repo and "/" in repo:
        if pr:
            return ("gh_pr", (repo, str(pr)))
        if sha and SHA.match(str(sha)):
            return ("gh_commit", (repo, str(sha)))
        return None
    if repo:
        # No slash -> not a github coordinate. Internal package name.
        return ("internal", (repo, str(sha or "")))
    return None


def entry_files(entry: dict) -> set[str]:
    files = set()
    for c in entry.get("consequences") or []:
        if isinstance(c, dict):
            fs = c.get("files")
            if isinstance(fs, list):
                files.update(f for f in fs if isinstance(f, str))
            elif isinstance(c.get("file"), str):
                files.add(c["file"])
    return files


class Resolver:
    def __init__(self, token: str = ""):
        self.token = token
        self.cache: dict = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        self.calls = 0

    def _get(self, path: str):
        req = urllib.request.Request(f"https://api.github.com{path}")
        req.add_header("Accept", "application/vnd.github+json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        self.calls += 1
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def resolve(self, kind: str, params: tuple) -> dict:
        key = f"{kind}:{params[0]}:{params[1]}"
        if key in self.cache:
            return self.cache[key]
        repo, ident = params
        path = (f"/repos/{repo}/pulls/{ident}/files?per_page=100" if kind == "gh_pr"
                else f"/repos/{repo}/commits/{ident}")
        try:
            data = self._get(path)
            if kind == "gh_pr":
                files = [f["filename"] for f in data] if isinstance(data, list) else []
                # An empty file list means the PR number resolved to something
                # without files -- treat as unreachable rather than verified.
                res = {"ok": bool(files), "files": files}
            else:
                files = [f["filename"] for f in (data.get("files") or [])]
                res = {"ok": True, "files": files}
        except urllib.error.HTTPError as e:
            # 404 means the reference DOES NOT EXIST -- a real finding.
            # 403/429/5xx mean we could not ask: rate limiting, auth, or an
            # outage. Conflating them is dangerous in both directions: a
            # rate-limited run would brand good entries as fabricated, and
            # caching that verdict would poison every later run. Discovered by
            # the adversarial fixture, which returned 403 for two entries after
            # the unauthenticated budget ran out and was reported as
            # "unreachable 2 (100%)" -- the right verdict for the wrong reason.
            if e.code == 404:
                res = {"ok": False, "definitive": True, "files": [],
                       "error": "HTTP 404 (does not exist)"}
            else:
                hint = " -- rate limited; set GITHUB_TOKEN" if e.code in (403, 429) else ""
                return {"ok": False, "definitive": False, "files": [],
                        "error": f"HTTP {e.code}{hint}"}  # NOT cached
        except Exception as e:
            return {"ok": False, "definitive": False, "files": [],
                    "error": f"{type(e).__name__}"}  # NOT cached
        self.cache[key] = res
        return res

    def save(self):
        CACHE.write_text(json.dumps(self.cache))


def write_manifest(entries: list[dict], offline_cls: dict, online_cls: dict,
                   out_dir: Path) -> None:
    """Emit the verified/unverified split as a GENERATED manifest.

    Deliberately not a directory move. The online status of most entries is
    still unresolved (resolving 634 references needs a token; unauthenticated is
    60 calls/hour), and physically filing them under verified/ or unverified/
    would assert a classification that has not been made. `unresolved` is a
    first-class state here, distinct from both verified and broken.
    """
    rows = []
    for e in entries:
        ref = reference(e)
        kind = ref[0] if ref else None
        key = f"{kind}:{ref[1][0]}:{ref[1][1]}" if ref and kind != "internal" else None
        rows.append({
            "id": e.get("id"),
            "file": e.get("_file", "").split("datasets/")[-1],
            "source_type": source_type(e),
            "provenance": offline_cls.get(e.get("id"), "?"),
            "resolution": online_cls.get(key, "unresolved") if key else "n/a",
            "consequence_files": len(entry_files(e)),
        })
    (out_dir / "provenance.json").write_text(json.dumps(rows, indent=2))

    counts = collections.Counter(r["provenance"] for r in rows)
    res = collections.Counter(r["resolution"] for r in rows)
    lines = [
        "# PropBench provenance manifest",
        "",
        "Generated by `tools/validate_provenance.py --manifest`. Do not edit by hand.",
        "",
        "`provenance` is computed offline from identifier fields. `resolution` "
        "requires network access; entries not yet checked are **unresolved**, "
        "which is NOT the same as verified.",
        "",
        "## Provenance (offline)",
        "",
        "| class | count |",
        "|---|---|",
    ]
    for k, v in counts.most_common():
        lines.append(f"| `{k}` | {v} |")
    lines += ["", "## Resolution (online)", "", "| state | count |", "|---|---|"]
    for k, v in res.most_common():
        lines.append(f"| `{k}` | {v} |")
    lines += [
        "",
        "## Machine-readable",
        "",
        "`provenance.json` carries one row per entry with the same fields, for "
        "tooling that needs to filter the corpus (e.g. the replay harness "
        "selecting only verified, removal-shaped entries).",
        "",
    ]
    (out_dir / "PROVENANCE.md").write_text("\n".join(lines))
    print(f"\n  manifest -> {out_dir / 'PROVENANCE.md'}")
    print(f"  manifest -> {out_dir / 'provenance.json'}  ({len(rows)} rows)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default=str(Path(__file__).parent.parent / "datasets"))
    ap.add_argument("--resolve", action="store_true", help="make network calls")
    ap.add_argument("--sample", type=int, default=0, help="resolve only N (0=all)")
    ap.add_argument("--manifest", action="store_true",
                    help="write PROVENANCE.md + provenance.json")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    entries = load_entries(Path(args.datasets))
    print(f"PropBench provenance audit -- {len(entries)} entries\n")

    offline = collections.Counter()
    by_src = collections.defaultdict(collections.Counter)
    resolvable = []
    offline_cls: dict = {}
    for e in entries:
        st = source_type(e)
        ref = reference(e)
        if ref is None:
            cls = "no_reference"
        elif ref[0] == "internal":
            cls = "internal_unverifiable"
        else:
            cls = "resolvable"
            resolvable.append((e, ref))
        offline[cls] += 1
        by_src[st][cls] += 1
        offline_cls[e.get("id")] = cls

    print("OFFLINE CLASSIFICATION (no network -- identifier fields only)")
    for cls, n in offline.most_common():
        print(f"  {cls:24} {n:4}  ({100*n/len(entries):.1f}%)")
    print("\n  by source type:")
    for st, c in sorted(by_src.items(), key=lambda x: -sum(x[1].values())):
        detail = "  ".join(f"{k}={v}" for k, v in c.most_common())
        print(f"    {st:22} {sum(c.values()):4}   {detail}")

    # Resolution states from any prior cached run -- so the manifest reflects
    # what has actually been checked, without re-spending API budget.
    prov = Path(__file__).parent / ".provenance_cache.json"
    online_cls: dict = {}
    if prov.exists():
        for k, v in json.loads(prov.read_text()).items():
            online_cls[k] = "verified" if v.get("ok") else "unreachable"

    if not args.resolve:
        print(f"\n{len(resolvable)} entries cite a public reference. Re-run with "
              f"--resolve (and GITHUB_TOKEN) to check they exist.")
        if args.manifest:
            write_manifest(entries, offline_cls, online_cls, Path(args.datasets))
        return 0

    token = os.environ.get("GITHUB_TOKEN", "")
    print(f"\nONLINE RESOLUTION  (token: {'yes' if token else 'NO -- 60 calls/hour'})")
    targets = resolvable
    if args.sample and args.sample < len(targets):
        random.seed(args.seed)
        targets = random.sample(targets, args.sample)
        print(f"  sampling {len(targets)} of {len(resolvable)} (seed={args.seed})")

    r = Resolver(token)
    online = collections.Counter()
    problems = []
    for e, ref in targets:
        res = r.resolve(*ref)
        claimed = entry_files(e)
        real = set(res.get("files") or [])
        if not res.get("ok"):
            # A transient failure is NOT evidence the entry is broken.
            cls = "unreachable" if res.get("definitive") else "unresolved_transient"
        elif claimed and real and not (claimed & real):
            cls = "mismatched"
        elif claimed and real:
            cls = "verified"
        else:
            cls = "verified_no_overlap_check"
        online[cls] += 1
        if cls in ("unreachable", "mismatched", "unresolved_transient"):
            problems.append((e.get("id"), ref, cls, res.get("error", ""),
                             len(claimed), len(real)))
    r.save()

    n = sum(online.values())
    print(f"  resolved {n} entries in {r.calls} API call(s)\n")
    for cls, c in online.most_common():
        print(f"  {cls:26} {c:4}  ({100*c/n:.1f}%)")

    if problems:
        print(f"\n  PROBLEMS ({len(problems)}):")
        for pid, ref, cls, err, nc, nr in problems[:25]:
            print(f"    {cls:11} {str(pid)[:34]:36} {ref[1][0]}#{ref[1][1]} "
                  f"{err} claimed={nc} real={nr}")

    if args.manifest:
        write_manifest(entries, offline_cls, online_cls, Path(args.datasets))

    verified = online["verified"] + online["verified_no_overlap_check"]
    print(f"\n  survival on this set: {verified}/{n} "
          f"({100*verified/n:.1f}%)" if n else "")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
