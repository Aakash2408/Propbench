#!/usr/bin/env python3
"""
judgment-engine/tools/git_miner.py

Mine git history for PropBench replay entries.

Every multi-file commit is a potential benchmark entry:
- The "trigger" file = the primary change (heuristic: largest diff, or matches commit subject)
- The "consequence" files = everything else that changed

Usage:
    python3 tools/git_miner.py /path/to/repo [--since 2025-01-01] [--min-files 2] [--max-files 20] [--limit 100]
    python3 tools/git_miner.py /path/to/repo --output datasets/families/auto-mined/

Output: YAML files in PropBench format, one per qualifying commit.
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required. Install: pip install pyyaml")
    sys.exit(1)


def run_git(repo_path: str, *args) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", "-C", repo_path] + list(args),
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_commits(repo_path: str, since: str, limit: int) -> list[dict]:
    """Get commits with their metadata."""
    # Format: hash|author|date|subject
    log_format = "%H|%an|%ai|%s"
    output = run_git(
        repo_path, "log",
        f"--since={since}",
        f"--format={log_format}",
        f"-n{limit * 3}",  # get more than needed, we'll filter
        "--no-merges",
    )
    
    commits = []
    for line in output.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        commits.append({
            "hash": parts[0],
            "author": parts[1],
            "date": parts[2][:10],  # YYYY-MM-DD
            "subject": parts[3],
        })
    
    return commits


def get_commit_files(repo_path: str, commit_hash: str) -> list[dict]:
    """Get files changed in a commit with stats."""
    # numstat gives: additions \t deletions \t filename
    output = run_git(repo_path, "diff-tree", "--no-commit-id", "-r", "--numstat", commit_hash)
    
    files = []
    for line in output.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        
        additions = int(parts[0]) if parts[0] != "-" else 0
        deletions = int(parts[1]) if parts[1] != "-" else 0
        filepath = parts[2]
        
        # Skip binary files, generated files, lock files
        if _is_noise_file(filepath):
            continue
        
        files.append({
            "path": filepath,
            "additions": additions,
            "deletions": deletions,
            "total_changes": additions + deletions,
        })
    
    return files


def _is_noise_file(filepath: str) -> bool:
    """Filter out files that don't represent meaningful engineering changes."""
    noise_patterns = [
        r"\.lock$",
        r"package-lock\.json$",
        r"yarn\.lock$",
        r"\.min\.(js|css)$",
        r"\.map$",
        r"__pycache__",
        r"\.pyc$",
        r"node_modules/",
        r"\.git/",
        r"build/",
        r"dist/",
        r"\.class$",
        r"generated",  # be careful — some generated files ARE the point
    ]
    for pattern in noise_patterns:
        if re.search(pattern, filepath, re.IGNORECASE):
            return True
    return False


def identify_trigger(files: list[dict], commit_subject: str) -> tuple[dict, list[dict]]:
    """
    Heuristic: identify which file is the "trigger" (primary change)
    and which are "consequences" (downstream changes).
    
    Heuristics (in order):
    1. File that matches the commit subject keywords
    2. Non-test, non-config file with largest diff
    3. First file alphabetically (fallback)
    """
    if not files:
        return None, []
    
    subject_lower = commit_subject.lower()
    
    # Heuristic 1: match commit subject keywords to filenames
    for f in files:
        filename = f["path"].split("/")[-1].lower()
        # Check if any word from the filename appears in the subject
        name_parts = re.split(r'[_\-./]', filename.replace(".java", "").replace(".ts", "").replace(".py", "").replace(".go", ""))
        matches = sum(1 for part in name_parts if len(part) > 3 and part in subject_lower)
        if matches >= 2:
            consequences = [x for x in files if x != f]
            return f, consequences
    
    # Heuristic 2: largest non-test, non-config file
    source_files = [f for f in files if not _is_likely_consequence(f["path"])]
    if source_files:
        trigger = max(source_files, key=lambda f: f["total_changes"])
        consequences = [x for x in files if x != trigger]
        return trigger, consequences
    
    # Heuristic 3: largest file overall
    trigger = max(files, key=lambda f: f["total_changes"])
    consequences = [x for x in files if x != trigger]
    return trigger, consequences


def _is_likely_consequence(filepath: str) -> bool:
    """Files that are more likely to be consequences than triggers."""
    patterns = [
        r"_test\.",
        r"Test\.",
        r"\.test\.",
        r"spec\.",
        r"/test/",
        r"/tests/",
        r"CHANGELOG",
        r"changelog",
        r"\.md$",
        r"docs/",
        r"website/",
        r"Config$",  # Brazil Config file
        r"swagger",
        r"openapi",
    ]
    for pattern in patterns:
        if re.search(pattern, filepath):
            return True
    return False


def classify_family(files: list[dict], commit_subject: str) -> str:
    """Auto-classify the change family based on files and subject."""
    subject_lower = commit_subject.lower()
    all_paths = " ".join(f["path"] for f in files).lower()
    
    if any(w in subject_lower for w in ["test", "spec", "integ"]):
        return "test-evolution"
    if any(w in subject_lower for w in ["upgrade", "bump", "dependency", "dep "]):
        return "dependency-evolution"
    if any(w in subject_lower for w in ["cdk", "terraform", "cloudformation", "iam"]):
        return "infrastructure-evolution"
    if any(w in all_paths for w in [".proto", "schema", "graphql", "openapi"]):
        return "interface-evolution"
    if any(w in all_paths for w in ["config", ".yaml", ".yml", ".json"]):
        return "configuration-evolution"
    if any(w in subject_lower for w in ["refactor", "rename", "move", "reorganize"]):
        return "refactor"
    if any(w in subject_lower for w in ["fix", "bug", "patch", "hotfix"]):
        return "bugfix"
    
    return "uncategorized"


def estimate_difficulty(files: list[dict], trigger: dict, consequences: list[dict]) -> str:
    """Estimate difficulty based on propagation characteristics."""
    n_files = len(files)
    
    # Many different directories = likely harder
    dirs = set(f["path"].rsplit("/", 1)[0] if "/" in f["path"] else "." for f in files)
    
    if n_files <= 2:
        return "easy"
    elif n_files <= 5 and len(dirs) <= 2:
        return "medium"
    elif n_files <= 10:
        return "medium"
    else:
        return "hard"


def generate_entry(
    repo_name: str,
    commit: dict,
    trigger: dict,
    consequences: list[dict],
    all_files: list[dict],
    entry_id: str,
) -> dict:
    """Generate a PropBench YAML entry from mined data."""
    family = classify_family(all_files, commit["subject"])
    difficulty = estimate_difficulty(all_files, trigger, consequences)
    
    return {
        "id": entry_id,
        "title": commit["subject"][:100],
        "family": family,
        "date": commit["date"],
        "author": commit["author"],
        "source": "git-mined",
        "source_repo": repo_name,
        "source_commit": commit["hash"],
        "difficulty": difficulty,
        "trigger": {
            "package": repo_name,
            "files": [trigger["path"]],
            "intent": commit["subject"],
            "diff_summary": f"Primary change: {trigger['path']} (+{trigger['additions']}/-{trigger['deletions']})",
        },
        "consequences": [
            {
                "package": repo_name,
                "files": [c["path"]],
                "description": f"Co-changed: {c['path']} (+{c['additions']}/-{c['deletions']})",
                "mechanical": _is_likely_consequence(c["path"]),
                "relationship": "co-change",
                "confidence_an_expert_would_predict": 0.5,  # unknown — needs human review
                "reasoning": "Auto-mined from git history (needs human review)",
            }
            for c in consequences
        ],
        "tags": ["git-mined", "needs-review"],
        "effort": {
            "packages_touched": 1,
            "files_changed": len(all_files),
        },
        "notes": f"Auto-mined from {repo_name} commit {commit['hash'][:8]}. Trigger heuristic may be wrong. Needs human review to confirm trigger/consequence split and add expert_reasoning.",
    }


def mine_repo(
    repo_path: str,
    since: str = "2025-01-01",
    min_files: int = 2,
    max_files: int = 20,
    limit: int = 100,
) -> list[dict]:
    """Mine a single repo for PropBench entries."""
    repo_name = Path(repo_path).name
    
    print(f"\n  Mining: {repo_name}")
    print(f"  Path:  {repo_path}")
    print(f"  Since: {since}, min_files={min_files}, max_files={max_files}")
    
    commits = get_commits(repo_path, since, limit)
    print(f"  Found {len(commits)} non-merge commits")
    
    entries = []
    skipped = 0
    
    for i, commit in enumerate(commits):
        files = get_commit_files(repo_path, commit["hash"])
        
        # Filter by file count
        if len(files) < min_files or len(files) > max_files:
            skipped += 1
            continue
        
        trigger, consequences = identify_trigger(files, commit["subject"])
        if not trigger or not consequences:
            skipped += 1
            continue
        
        entry_id = f"mined-{repo_name.lower()}-{len(entries)+1:03d}"
        entry = generate_entry(repo_name, commit, trigger, consequences, files, entry_id)
        entries.append(entry)
        
        if len(entries) >= limit:
            break
    
    print(f"  Generated {len(entries)} entries (skipped {skipped})")
    return entries


def write_entries(entries: list[dict], output_dir: Path):
    """Write entries as YAML files to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for entry in entries:
        filename = f"{entry['id']}.yaml"
        filepath = output_dir / filename
        
        with open(filepath, "w") as f:
            yaml.dump(entry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"\n  Wrote {len(entries)} YAML files to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Mine git history for PropBench entries")
    parser.add_argument("repo_path", help="Path to git repository")
    parser.add_argument("--since", default="2025-06-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--min-files", type=int, default=2, help="Min files per commit")
    parser.add_argument("--max-files", type=int, default=20, help="Max files per commit")
    parser.add_argument("--limit", type=int, default=50, help="Max entries to generate")
    parser.add_argument("--output", default=None, help="Output directory (default: stdout summary)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be mined without writing")
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.repo_path):
        print(f"ERROR: {args.repo_path} is not a directory")
        sys.exit(1)
    
    if not os.path.isdir(os.path.join(args.repo_path, ".git")):
        print(f"ERROR: {args.repo_path} is not a git repository")
        sys.exit(1)
    
    entries = mine_repo(
        args.repo_path,
        since=args.since,
        min_files=args.min_files,
        max_files=args.max_files,
        limit=args.limit,
    )
    
    if not entries:
        print("\n  No qualifying entries found.")
        sys.exit(0)
    
    # Summary
    families = {}
    for e in entries:
        families[e["family"]] = families.get(e["family"], 0) + 1
    
    print(f"\n  ═══════════════════════════════════════")
    print(f"  MINING SUMMARY")
    print(f"  ═══════════════════════════════════════")
    print(f"  Total entries:  {len(entries)}")
    print(f"  Families:")
    for fam, count in sorted(families.items(), key=lambda x: -x[1]):
        print(f"    {fam:25s} {count}")
    print(f"  ═══════════════════════════════════════")
    
    if args.dry_run:
        print("\n  [DRY RUN — no files written]")
        # Show first 3 entries as sample
        for entry in entries[:3]:
            print(f"\n  --- {entry['id']} ---")
            print(f"  Title: {entry['title']}")
            print(f"  Trigger: {entry['trigger']['files'][0]}")
            print(f"  Consequences: {[c['files'][0] for c in entry['consequences']]}")
        return
    
    if args.output:
        output_dir = Path(args.output)
    else:
        repo_name = Path(args.repo_path).name.lower()
        output_dir = Path("datasets/families/mined-" + repo_name)
    
    write_entries(entries, output_dir)


if __name__ == "__main__":
    main()
