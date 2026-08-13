#!/usr/bin/env python3
"""
judgment-engine/tools/github_miner.py

Mine GitHub PRs for PropBench entries using the GitHub API.
No git clone needed — fetches PR file lists via REST API.

Usage:
    python3 tools/github_miner.py hashicorp/terraform-provider-aws --limit 30
    python3 tools/github_miner.py kubernetes/kubernetes --limit 20 --min-files 3
    python3 tools/github_miner.py facebook/react --limit 20

Note: GitHub API rate limit is 60 requests/hour for unauthenticated.
Set GITHUB_TOKEN env var for 5000 requests/hour.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from time import sleep

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required")
    sys.exit(1)

GITHUB_API = "https://api.github.com"
MAX_RETRIES = 3
RATE_LIMIT_THRESHOLD = 100
AUTO_GENERATED_FILES = frozenset([
    "package-lock.json", "yarn.lock", "go.sum", "Cargo.lock",
    "pnpm-lock.yaml", "composer.lock", "Gemfile.lock", "poetry.lock",
])
AUTO_GENERATED_EXTENSIONS = (".pb.go", ".generated.go", ".gen.go")
SKIP_TITLE_PATTERNS = re.compile(
    r"^(chore|docs|ci|test-only)[\s:(]", re.IGNORECASE
)


def github_get(path: str) -> tuple[dict | list | None, dict]:
    """Make authenticated GitHub API request with retry and rate-limit handling.
    Returns (data, headers_dict)."""
    url = f"{GITHUB_API}{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_headers = dict(resp.headers)
                # Rate limit check
                remaining = int(resp_headers.get("X-RateLimit-Remaining", "999"))
                if remaining < RATE_LIMIT_THRESHOLD:
                    reset_at = int(resp_headers.get("X-RateLimit-Reset", "0"))
                    import time
                    wait = max(reset_at - int(time.time()), 1)
                    print(f"  ⏳ Rate limit low ({remaining} remaining), sleeping {wait}s...")
                    sleep(min(wait, 60))
                return json.loads(resp.read().decode()), resp_headers
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                backoff = 2 ** attempt
                print(f"  ⚠️  HTTP {e.code}, retry {attempt+1}/{MAX_RETRIES} in {backoff}s...")
                sleep(backoff)
                continue
            if e.code == 403:
                print(f"  ⚠️  Rate limited. Set GITHUB_TOKEN env var for higher limits.")
                return None, {}
            if e.code == 404:
                return None, {}
            raise
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                sleep(2 ** attempt)
                continue
            print(f"  ⚠️  API error: {e}")
            return None, {}
    return None, {}


def load_existing_triggers(output_dir: Path) -> set[str]:
    """Load trigger_commit identifiers from existing entries for idempotency."""
    existing = set()
    if not output_dir.exists():
        return existing
    for f in output_dir.glob("*.yaml"):
        try:
            with open(f) as fh:
                entry = yaml.safe_load(fh)
            if entry and "source_pr" in entry:
                existing.add(f"{entry.get('source_repo', '')}#{entry['source_pr']}")
        except Exception:
            continue
    return existing


def _is_auto_generated(filepath: str) -> bool:
    """Check if a file is auto-generated (lockfiles, protobuf output, etc.)."""
    basename = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
    if basename in AUTO_GENERATED_FILES:
        return True
    return filepath.endswith(AUTO_GENERATED_EXTENSIONS)


def _is_noise_file(filepath: str) -> bool:
    """Filter noise files."""
    noise = ["CHANGELOG", "changelog", ".github/", ".circleci/"]
    for n in noise:
        if n in filepath:
            return True
    if filepath.endswith((".md", ".txt")) and "/" not in filepath:
        return True
    return False


def _is_likely_consequence(filepath: str) -> bool:
    """Files more likely to be consequences."""
    patterns = ["_test.", "Test.", ".test.", "spec.", "/test/", "/tests/",
                "website/docs/", "CHANGELOG", ".changelog/"]
    return any(p in filepath for p in patterns)


def get_merged_prs(repo: str, limit: int = 30) -> list[dict]:
    """Get recently merged PRs for a repo."""
    prs, _ = github_get(
        f"/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page={min(limit * 2, 100)}"
    )
    if not prs:
        return []
    merged = [pr for pr in prs if pr.get("merged_at")]
    return merged[:limit]


def get_pr_files(repo: str, pr_number: int) -> list[dict]:
    """Get files changed in a PR."""
    files, _ = github_get(f"/repos/{repo}/pulls/{pr_number}/files?per_page=100")
    if not files:
        return []
    return [
        {
            "path": f["filename"],
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "total_changes": f.get("changes", 0),
            "status": f.get("status", "modified"),
        }
        for f in files
        if not _is_noise_file(f["filename"])
    ]


def identify_trigger(files: list[dict], pr_title: str) -> tuple[dict | None, list[dict]]:
    """Identify primary change file via heuristic."""
    if not files:
        return None, []
    source_files = [f for f in files if not _is_likely_consequence(f["path"])]
    if source_files:
        trigger = max(source_files, key=lambda f: f["total_changes"])
    else:
        trigger = max(files, key=lambda f: f["total_changes"])
    consequences = [x for x in files if x != trigger]
    return trigger, consequences


def classify_family(files: list[dict], title: str) -> str:
    """Auto-classify change family."""
    title_lower = title.lower()
    all_paths = " ".join(f["path"] for f in files).lower()
    if any(w in title_lower for w in ["upgrade", "bump", "dep", "update version"]):
        return "dependency-evolution"
    if any(w in all_paths for w in [".proto", "schema", "graphql", "openapi", "types.go"]):
        return "interface-evolution"
    if any(w in title_lower for w in ["add", "new", "support", "implement"]):
        return "interface-evolution"
    if any(w in title_lower for w in ["fix", "bug", "patch", "resolve"]):
        return "bugfix"
    if any(w in title_lower for w in ["refactor", "rename", "move", "cleanup"]):
        return "refactor"
    return "uncategorized"


def mine_github_repo(
    repo: str, limit: int = 20, min_files: int = 3, max_files: int = 30,
    output_dir: Path | None = None,
) -> list[dict]:
    """Mine a GitHub repo for PropBench entries with full robustness."""
    repo_short = repo.split("/")[-1]

    # Idempotency: load existing entries
    if output_dir is None:
        output_dir = Path(f"datasets/families/oss-{repo_short.lower()}")
    existing_keys = load_existing_triggers(output_dir)

    print(f"\n  Mining: {repo}")
    print(f"  Fetching merged PRs...")

    prs = get_merged_prs(repo, limit * 3)
    print(f"  Found {len(prs)} merged PRs")

    entries = []
    skipped_duplicate = 0
    skipped_trivial = 0
    skipped_too_large = 0

    for pr in prs:
        if len(entries) >= limit:
            break

        pr_number = pr["number"]
        pr_key = f"{repo}#{pr_number}"
        title = pr.get("title", "")

        # Idempotency check
        if pr_key in existing_keys:
            skipped_duplicate += 1
            continue

        # Skip merge commits
        if pr.get("merge_commit_sha") and title.lower().startswith("merge "):
            skipped_trivial += 1
            continue

        # Skip chore/docs/ci/test-only PRs
        if SKIP_TITLE_PATTERNS.search(title):
            skipped_trivial += 1
            continue

        sleep(0.3)
        files = get_pr_files(repo, pr_number)

        # Validation: 0 files or > 50 files
        if len(files) == 0:
            skipped_trivial += 1
            continue
        if len(files) > 50:
            skipped_too_large += 1
            continue

        # Check if trigger file is auto-generated
        trigger_candidate, _ = identify_trigger(files, title)
        if trigger_candidate and _is_auto_generated(trigger_candidate["path"]):
            skipped_trivial += 1
            continue

        # Apply min/max files filter
        if len(files) < min_files or len(files) > max_files:
            continue

        trigger, consequences = identify_trigger(files, title)
        if not trigger or not consequences:
            continue

        entry_id = f"oss-{repo_short.lower()}-{pr_number}"
        entry = {
            "id": entry_id,
            "title": title[:100],
            "family": classify_family(files, title),
            "date": pr["merged_at"][:10],
            "author": pr["user"]["login"],
            "source": "github-api-mined",
            "source_repo": repo,
            "source_url": pr["html_url"],
            "source_pr": pr_number,
            "difficulty": "medium",
            "trigger": {
                "package": repo,
                "files": [trigger["path"]],
                "intent": title,
                "diff_summary": f"Primary: {trigger['path']} (+{trigger['additions']}/-{trigger['deletions']})",
            },
            "consequences": [
                {
                    "package": repo,
                    "files": [c["path"]],
                    "description": f"{c['status']}: {c['path']} (+{c['additions']}/-{c['deletions']})",
                    "mechanical": _is_likely_consequence(c["path"]),
                    "relationship": "co-change",
                    "confidence_an_expert_would_predict": 0.5,
                    "reasoning": "Auto-mined from GitHub PR (needs human review)",
                }
                for c in consequences
            ],
            "tags": ["github-mined", "needs-review", "open-source"],
            "propagation_unit": "file",
            "effort": {"files_changed": len(files)},
            "notes": f"Mined from {repo} PR #{pr_number}. Trigger heuristic applied. Needs review.",
        }

        entries.append(entry)
        print(f"  ✓ Entry {len(entries)}/{limit}: {entry_id}")

    total_skipped = skipped_duplicate + skipped_trivial + skipped_too_large
    print(f"\n  Mined {len(entries)} entries, skipped {total_skipped} "
          f"({skipped_duplicate} duplicates, {skipped_trivial} trivial, {skipped_too_large} too-large)")
    return entries


def main():
    parser = argparse.ArgumentParser(description="Mine GitHub PRs for PropBench")
    parser.add_argument("repo", help="GitHub repo (org/name)")
    parser.add_argument("--limit", type=int, default=20, help="Max entries")
    parser.add_argument("--min-files", type=int, default=3, help="Min files per PR")
    parser.add_argument("--max-files", type=int, default=30, help="Max files per PR")
    parser.add_argument("--output", default=None, help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")

    args = parser.parse_args()

    repo_short = args.repo.split("/")[-1].lower()
    output_dir = Path(args.output) if args.output else Path(f"datasets/families/oss-{repo_short}")

    entries = mine_github_repo(args.repo, args.limit, args.min_files, args.max_files, output_dir)

    if not entries:
        print("\n  No entries generated.")
        sys.exit(0)

    families = {}
    for e in entries:
        families[e["family"]] = families.get(e["family"], 0) + 1

    print(f"\n  ═══════════════════════════════════════")
    print(f"  GITHUB MINING SUMMARY: {args.repo}")
    print(f"  ═══════════════════════════════════════")
    print(f"  Entries:  {len(entries)}")
    print(f"  Families:")
    for fam, count in sorted(families.items(), key=lambda x: -x[1]):
        print(f"    {fam:25s} {count}")

    if args.dry_run:
        print("\n  [DRY RUN]")
        for e in entries[:3]:
            print(f"\n  {e['id']}: {e['title'][:60]}")
            print(f"    Trigger: {e['trigger']['files'][0]}")
            print(f"    Consequences: {len(e['consequences'])} files")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        filepath = output_dir / f"{entry['id']}.yaml"
        with open(filepath, "w") as f:
            yaml.dump(entry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"\n  Wrote {len(entries)} files to {output_dir}")


if __name__ == "__main__":
    main()
