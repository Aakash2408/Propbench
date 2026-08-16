"""One cache, one API call, shared by every tool that needs a PR's files.

WHY
---
validate_provenance.py and extract_seed.py both called
    GET /repos/{repo}/pulls/{n}/files
into SEPARATE cache files (.provenance_cache.json and .patch_cache.json). Same
endpoint, same response, counted twice against the rate limit. A full run over
the 634 resolvable entries cost ~1,270 calls where ~650 suffices.

replay.py additionally needs the base SHA, which is a different endpoint
(GET /repos/{repo}/pulls/{n}) and is cached separately here -- so a full run is
2 endpoints per entry, not 3 calls.

The unified record is a superset of what either tool needed, so nothing is lost:
filename, patch, additions, deletions, status.

Transient failures are NEVER cached -- a rate-limited or 5xx response is not
evidence about the entry. Caching it would make a false verdict permanent, the
same defect the provenance validator had until the adversarial fixture exposed
it (403 recorded as "unreachable").
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
FILES_CACHE = HERE / ".patch_cache.json"      # repo#num -> [file records] | None
BASE_CACHE = HERE / ".base_cache.json"        # repo#num -> sha | None
LEGACY_PROV = HERE / ".provenance_cache.json"  # pre-unification, read-only


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _save(p: Path, d: dict) -> None:
    p.write_text(json.dumps(d))


def token() -> str:
    return os.environ.get("GITHUB_TOKEN", "")


class Transient(Exception):
    """Could not ask -- rate limit, auth, outage. Not a verdict on the entry."""


def _get(path: str):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    tok = token()
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # definitive: does not exist
        hint = " -- rate limited; set GITHUB_TOKEN" if e.code in (403, 429) else ""
        raise Transient(f"HTTP {e.code}{hint}") from e
    except Exception as e:  # noqa: BLE001 - network shapes vary
        raise Transient(type(e).__name__) from e


def pr_files(repo: str, num: str | int) -> list[dict] | None:
    """File records for a PR. None means the PR does not exist (404).

    Raises Transient when the answer is unknown, so callers can distinguish
    "does not exist" from "could not check".
    """
    key = f"{repo}#{num}"
    cache = _load(FILES_CACHE)
    if key in cache:
        return cache[key]

    # Reuse a pre-unification provenance result rather than re-spending a call.
    legacy = _load(LEGACY_PROV).get(f"gh_pr:{repo}:{num}")
    if legacy and legacy.get("ok") and legacy.get("files"):
        # Names only -- no patches. Enough for provenance, not for extraction,
        # so it is NOT written into the unified cache as if it were complete.
        return [{"filename": f, "patch": None, "additions": 0,
                 "deletions": 0, "status": None} for f in legacy["files"]]

    data = _get(f"/repos/{repo}/pulls/{num}/files?per_page=100")
    if data is None:
        cache[key] = None
        _save(FILES_CACHE, cache)
        return None
    out = [{"filename": f["filename"], "patch": f.get("patch"),
            "additions": f.get("additions", 0), "deletions": f.get("deletions", 0),
            "status": f.get("status")} for f in data]
    cache[key] = out
    _save(FILES_CACHE, cache)
    return out


def pr_base_sha(repo: str, num: str | int) -> str | None:
    key = f"{repo}#{num}"
    cache = _load(BASE_CACHE)
    if key in cache:
        return cache[key]
    data = _get(f"/repos/{repo}/pulls/{num}")
    sha = None if data is None else data["base"]["sha"]
    cache[key] = sha
    _save(BASE_CACHE, cache)
    return sha


def commit_files(repo: str, sha: str) -> list[dict] | None:
    key = f"commit:{repo}#{sha}"
    cache = _load(FILES_CACHE)
    if key in cache:
        return cache[key]
    data = _get(f"/repos/{repo}/commits/{sha}")
    if data is None:
        cache[key] = None
        _save(FILES_CACHE, cache)
        return None
    out = [{"filename": f["filename"], "patch": f.get("patch"),
            "additions": f.get("additions", 0), "deletions": f.get("deletions", 0),
            "status": f.get("status")} for f in (data.get("files") or [])]
    cache[key] = out
    _save(FILES_CACHE, cache)
    return out


def stats() -> dict:
    files = _load(FILES_CACHE)
    return {
        "pr_files_cached": sum(1 for k in files if not k.startswith("commit:")),
        "commits_cached": sum(1 for k in files if k.startswith("commit:")),
        "base_shas_cached": len(_load(BASE_CACHE)),
        "legacy_provenance_entries": len(_load(LEGACY_PROV)),
        "authenticated": bool(token()),
    }


if __name__ == "__main__":
    print(json.dumps(stats(), indent=2))
