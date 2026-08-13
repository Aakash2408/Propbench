#!/usr/bin/env python3
"""PropBench dataset validation script.

Checks all YAML entries for quality, detects duplicates, classifies entries,
and optionally fixes issues.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import yaml


REQUIRED_FIELDS = ["id", "trigger", "consequences", "family"]
GOOD_MIN, GOOD_MAX = 1, 15
SUSPECT_MAX = 50


def get_consequence_file_count(entry: dict) -> int:
    """Extract total consequence file count from nested consequences structure."""
    consequences = entry.get("consequences", [])
    if not isinstance(consequences, list):
        return 0
    count = 0
    for c in consequences:
        if isinstance(c, dict):
            files = c.get("files", [])
            if isinstance(files, list):
                count += len(files)
    return count


def get_trigger_files(entry: dict) -> list:
    """Extract trigger files from nested trigger structure."""
    trigger = entry.get("trigger", {})
    if isinstance(trigger, dict):
        return trigger.get("files", [])
    return []


def load_entries(base_dir: Path) -> list[dict]:
    """Load all YAML entries from datasets/families/**/*.yaml."""
    entries = []
    families_dir = base_dir / "datasets" / "families"
    if not families_dir.exists():
        print(f"ERROR: {families_dir} does not exist", file=sys.stderr)
        sys.exit(1)
    for yaml_file in sorted(families_dir.rglob("*.yaml")):
        with open(yaml_file) as f:
            docs = list(yaml.safe_load_all(f))
        for data in docs:
            if data is None:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    item["_source_file"] = str(yaml_file)
                    entries.append(item)
    return entries


def check_required_fields(entry: dict) -> list[str]:
    """Return list of missing required fields."""
    missing = []
    for field in REQUIRED_FIELDS:
        if field not in entry or entry[field] is None:
            missing.append(field)
    # Check consequences has at least one file
    count = get_consequence_file_count(entry)
    if count == 0 and "consequences" in entry:
        consequences = entry.get("consequences", [])
        if not isinstance(consequences, list) or len(consequences) == 0:
            missing.append("consequences (empty)")
    return missing


def classify_entry(entry: dict) -> str:
    """Classify entry as GOOD, SUSPECT, or BAD."""
    count = get_consequence_file_count(entry)
    if count == 0:
        # Check if consequences exist but just don't have files listed
        consequences = entry.get("consequences", [])
        if isinstance(consequences, list) and len(consequences) > 0:
            return "SUSPECT"  # Has consequences but no files enumerated
        return "BAD"
    if count > SUSPECT_MAX:
        return "BAD"
    if GOOD_MIN <= count <= GOOD_MAX:
        return "GOOD"
    return "SUSPECT"


def validate_paths(entry: dict) -> list[str]:
    """Check consequence file paths are relative (not absolute)."""
    issues = []
    consequences = entry.get("consequences", [])
    if not isinstance(consequences, list):
        return ["consequences is not a list"]
    for c in consequences:
        if not isinstance(c, dict):
            continue
        for path in c.get("files", []):
            if not isinstance(path, str):
                issues.append(f"non-string path: {path}")
            elif path.startswith("/"):
                issues.append(f"absolute path: {path}")
            elif ".." in path:
                issues.append(f"parent traversal: {path}")
    return issues


def find_duplicates(entries: list[dict]) -> dict[str, list[int]]:
    """Find entries with same trigger files + id."""
    seen = defaultdict(list)
    for i, entry in enumerate(entries):
        key = entry.get("id", str(i))
        seen[key].append(i)
    return {k: v for k, v in seen.items() if len(v) > 1}


def validate_dataset(base_dir: Path) -> dict:
    """Run full validation and return report data."""
    entries = load_entries(base_dir)
    report = {
        "total_entries": len(entries),
        "good": 0, "suspect": 0, "bad": 0,
        "duplicates": 0,
        "per_family": defaultdict(lambda: {"good": 0, "suspect": 0, "bad": 0, "total": 0}),
        "bad_entries": [],
        "issues": [],
    }

    duplicates = find_duplicates(entries)
    report["duplicates"] = sum(len(v) - 1 for v in duplicates.values())

    for i, entry in enumerate(entries):
        family = entry.get("family", "unknown")
        report["per_family"][family]["total"] += 1

        # Check required fields
        missing = check_required_fields(entry)
        if missing:
            report["issues"].append({
                "index": i, "source": entry.get("_source_file", "?"),
                "type": "missing_fields", "details": missing
            })

        # Validate paths
        path_issues = validate_paths(entry)
        if path_issues:
            report["issues"].append({
                "index": i, "source": entry.get("_source_file", "?"),
                "type": "path_issues", "details": path_issues
            })

        # Classify
        quality = classify_entry(entry)
        report[quality.lower()] += 1
        report["per_family"][family][quality.lower()] += 1

        if quality == "BAD":
            report["bad_entries"].append({
                "index": i, "source": entry.get("_source_file", "?"),
                "trigger_file": entry.get("trigger_file", "?"),
                "reason": f"consequence_files count: {get_consequence_file_count(entry)}"
            })

    # Convert defaultdict for serialization
    report["per_family"] = dict(report["per_family"])
    return report


def write_report(report: dict, output_path: Path):
    """Write validation report as YAML."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Strip internal fields for clean output
    clean = {k: v for k, v in report.items() if k != "bad_entries"}
    clean["bad_entry_count"] = len(report["bad_entries"])
    clean["bad_entry_samples"] = report["bad_entries"][:20]
    with open(output_path, "w") as f:
        yaml.dump(clean, f, default_flow_style=False, sort_keys=False)
    print(f"Report written to {output_path}")


def fix_bad_entries(base_dir: Path, report: dict):
    """Remove BAD entries from source YAML files."""
    bad_sources = defaultdict(list)
    for bad in report["bad_entries"]:
        bad_sources[bad["source"]].append(bad["index"])

    entries = load_entries(base_dir)
    bad_indices = {b["index"] for b in report["bad_entries"]}
    files_to_rewrite = defaultdict(list)

    for i, entry in enumerate(entries):
        src = entry["_source_file"]
        clean = {k: v for k, v in entry.items() if k != "_source_file"}
        if i not in bad_indices:
            files_to_rewrite[src].append(clean)

    removed = 0
    for src_file, good_entries in files_to_rewrite.items():
        with open(src_file, "w") as f:
            yaml.dump(good_entries if len(good_entries) > 1 else good_entries[0],
                      f, default_flow_style=False, sort_keys=False)
        original_count = sum(1 for e in entries if e["_source_file"] == src_file)
        removed += original_count - len(good_entries)

    # Remove files that became empty
    families_dir = base_dir / "datasets" / "families"
    for yaml_file in families_dir.rglob("*.yaml"):
        with open(yaml_file) as f:
            docs = list(yaml.safe_load_all(f))
        if not any(docs):
            yaml_file.unlink()
            print(f"  Removed empty file: {yaml_file}")

    print(f"Fixed: removed {removed} BAD entries from dataset")


def main():
    parser = argparse.ArgumentParser(description="Validate PropBench dataset entries")
    parser.add_argument("--base-dir", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="Project root (default: parent of tools/)")
    parser.add_argument("--strict", action="store_true",
                        help="Exit non-zero if any BAD entries found (for CI)")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-remove BAD entries from dataset files")
    args = parser.parse_args()

    print(f"Validating dataset in {args.base_dir}")
    report = validate_dataset(args.base_dir)

    # Print summary
    print(f"\n{'='*50}")
    print(f"DATASET VALIDATION SUMMARY")
    print(f"{'='*50}")
    print(f"Total entries:  {report['total_entries']}")
    print(f"  GOOD:         {report['good']}")
    print(f"  SUSPECT:      {report['suspect']}")
    print(f"  BAD:          {report['bad']}")
    print(f"  Duplicates:   {report['duplicates']}")
    print(f"\nPer-family breakdown:")
    for family, counts in sorted(report["per_family"].items()):
        print(f"  {family:20s}  total={counts['total']:3d}  "
              f"good={counts['good']:3d}  suspect={counts['suspect']:3d}  bad={counts['bad']:3d}")

    if report["bad_entries"]:
        print(f"\nBAD entries ({len(report['bad_entries'])}):")
        for bad in report["bad_entries"][:10]:
            print(f"  - {bad['trigger_file']} ({bad['reason']}) in {Path(bad['source']).name}")
        if len(report["bad_entries"]) > 10:
            print(f"  ... and {len(report['bad_entries']) - 10} more")

    # Write report
    output_path = args.base_dir / "paper" / "validation-report.yaml"
    write_report(report, output_path)

    # Fix mode
    if args.fix and report["bad_entries"]:
        print(f"\n--fix: Removing {len(report['bad_entries'])} BAD entries...")
        fix_bad_entries(args.base_dir, report)

    # Strict mode
    if args.strict and report["bad"] > 0:
        print(f"\n❌ STRICT MODE: {report['bad']} BAD entries found. Exiting non-zero.")
        sys.exit(1)

    print("\n✅ Validation complete.")


if __name__ == "__main__":
    main()
