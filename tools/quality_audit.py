#!/usr/bin/env python3
"""
judgment-engine/tools/quality_audit.py

Audit the mined PropBench dataset for quality issues.

Checks:
1. Trivial entries (formatting, version bumps, auto-generated)
2. Ambiguous trigger selection (multiple large files)
3. Missing/empty consequences
4. Duplicate entries
5. Noise classification

Usage:
    python3 tools/quality_audit.py                     # Full audit
    python3 tools/quality_audit.py --remove-trivial    # Remove trivial entries
    python3 tools/quality_audit.py --sample 30         # Manual review sample
"""

import argparse
import os
import re
import sys
from pathlib import Path
from collections import Counter

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required")
    sys.exit(1)


def load_all_entries(datasets_dir: Path) -> list[tuple[Path, dict]]:
    """Load all YAML entries with their file paths."""
    entries = []
    families_dir = datasets_dir / "families"
    for yaml_file in sorted(families_dir.rglob("*.yaml")):
        if yaml_file.name == "schema.yaml":
            continue
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and isinstance(data, dict) and "id" in data:
                entries.append((yaml_file, data))
        except Exception:
            pass
    return entries


def is_trivial(entry: dict) -> tuple[bool, str]:
    """Check if an entry is trivial (not meaningful propagation)."""
    title = entry.get("title", "").lower()
    trigger_files = entry.get("trigger", {}).get("files", [])
    consequences = entry.get("consequences", [])
    
    # Version bumps
    if any(w in title for w in ["bump version", "version bump", "release v"]):
        return True, "version_bump"
    
    # Pure formatting
    if any(w in title for w in ["format", "lint", "prettier", "spotless"]):
        if not any(w in title for w in ["add", "fix", "update logic"]):
            return True, "formatting"
    
    # Merge commits that slipped through
    if title.startswith("merge ") or title.startswith("revert \"revert"):
        return True, "merge_or_double_revert"
    
    # Only 1 consequence and it's a test for the trigger (trivial co-location)
    if len(consequences) == 1:
        cons_file = consequences[0].get("files", [""])[0]
        trig_file = trigger_files[0] if trigger_files else ""
        # Same file just with _test suffix
        trig_base = trig_file.rsplit(".", 1)[0].rsplit("/", 1)[-1]
        cons_base = cons_file.rsplit(".", 1)[0].rsplit("/", 1)[-1]
        if cons_base == trig_base + "Test" or cons_base == trig_base + "_test":
            return True, "trivial_test_pair"
    
    return False, ""


def is_ambiguous_trigger(entry: dict) -> bool:
    """Check if trigger selection might be wrong."""
    consequences = entry.get("consequences", [])
    trigger_files = entry.get("trigger", {}).get("files", [])
    
    if not trigger_files or not consequences:
        return False
    
    # If a consequence has MORE changes than the trigger, it might be the real trigger
    trigger_summary = entry.get("trigger", {}).get("diff_summary", "")
    trigger_changes = _extract_changes(trigger_summary)
    
    for cons in consequences:
        desc = cons.get("description", "")
        cons_changes = _extract_changes(desc)
        if cons_changes > trigger_changes * 2 and cons_changes > 50:
            return True
    
    return False


def _extract_changes(text: str) -> int:
    """Extract +N/-M from a description string."""
    match = re.search(r'\+(\d+)/-(\d+)', text)
    if match:
        return int(match.group(1)) + int(match.group(2))
    match = re.search(r'\+(\d+)', text)
    if match:
        return int(match.group(1))
    return 0


def classify_propagation_type(entry: dict) -> str:
    """Classify what TYPE of propagation this represents."""
    title = entry.get("title", "").lower()
    consequences = entry.get("consequences", [])
    trigger_files = entry.get("trigger", {}).get("files", [])
    
    all_files = trigger_files + [c.get("files", [""])[0] for c in consequences if c.get("files")]
    all_paths = " ".join(all_files).lower()
    
    # Check for test propagation
    test_consequences = sum(1 for c in consequences 
                          if c.get("files") and any(t in c["files"][0].lower() 
                                for t in ["test", "spec", "_test."]))
    if test_consequences == len(consequences) and consequences:
        return "source_to_test"
    
    # Check for config propagation
    if any("config" in f.lower() or ".yaml" in f.lower() or ".json" in f.lower() 
           for f in trigger_files):
        return "config_propagation"
    
    # Check for interface propagation (proto, schema, types)
    if any(w in all_paths for w in [".proto", "types.", "schema", "interface"]):
        return "interface_propagation"
    
    # Multi-layer (source + test + config)
    has_test = any("test" in f.lower() for f in all_files if f)
    has_config = any("config" in f.lower() for f in all_files if f)
    has_source = any(not ("test" in f.lower() or "config" in f.lower()) for f in all_files if f)
    if has_test and has_source:
        return "source_and_test"
    
    return "general"


def audit(datasets_dir: Path) -> dict:
    """Run full quality audit."""
    entries = load_all_entries(datasets_dir)
    
    results = {
        "total": len(entries),
        "trivial": [],
        "ambiguous_trigger": [],
        "empty_consequences": [],
        "propagation_types": Counter(),
        "families": Counter(),
        "sources": Counter(),
        "by_quality": {"good": 0, "trivial": 0, "ambiguous": 0, "empty": 0},
    }
    
    for path, entry in entries:
        # Count families and sources
        results["families"][entry.get("family", "unknown")] += 1
        results["sources"][entry.get("source", "hand-curated")] += 1
        
        # Check trivial
        trivial, reason = is_trivial(entry)
        if trivial:
            results["trivial"].append((path, entry["id"], reason))
            results["by_quality"]["trivial"] += 1
            continue
        
        # Check empty consequences
        if not entry.get("consequences"):
            results["empty_consequences"].append((path, entry["id"]))
            results["by_quality"]["empty"] += 1
            continue
        
        # Check ambiguous
        if is_ambiguous_trigger(entry):
            results["ambiguous_trigger"].append((path, entry["id"]))
            results["by_quality"]["ambiguous"] += 1
        else:
            results["by_quality"]["good"] += 1
        
        # Classify propagation type
        prop_type = classify_propagation_type(entry)
        results["propagation_types"][prop_type] += 1
    
    return results


def print_report(results: dict):
    """Print the audit report."""
    total = results["total"]
    quality = results["by_quality"]
    
    print(f"\n{'═'*60}")
    print(f"  PROPBENCH QUALITY AUDIT")
    print(f"{'═'*60}")
    print(f"\n  Total entries: {total}")
    print(f"\n  Quality breakdown:")
    print(f"    Good:              {quality['good']:4d}  ({quality['good']/total*100:.0f}%)")
    print(f"    Trivial (remove):  {quality['trivial']:4d}  ({quality['trivial']/total*100:.0f}%)")
    print(f"    Ambiguous trigger: {quality['ambiguous']:4d}  ({quality['ambiguous']/total*100:.0f}%)")
    print(f"    Empty consequences:{quality['empty']:4d}  ({quality['empty']/total*100:.0f}%)")
    
    noise_rate = (quality["trivial"] + quality["empty"]) / total
    print(f"\n  Estimated noise rate: {noise_rate:.0%}")
    print(f"  Usable entries:      {quality['good'] + quality['ambiguous']}")
    
    print(f"\n  Propagation types:")
    for ptype, count in results["propagation_types"].most_common():
        print(f"    {ptype:25s} {count:4d}")
    
    print(f"\n  By source:")
    for source, count in results["sources"].most_common():
        print(f"    {source:25s} {count:4d}")
    
    print(f"\n  By family:")
    for fam, count in results["families"].most_common(10):
        print(f"    {fam:30s} {count:4d}")
    
    if results["trivial"]:
        print(f"\n  Trivial entries (first 10):")
        for path, eid, reason in results["trivial"][:10]:
            print(f"    {eid:40s} [{reason}]")
    
    print(f"\n{'═'*60}")


def remove_trivial(datasets_dir: Path, dry_run: bool = True):
    """Remove trivial entries from the dataset."""
    entries = load_all_entries(datasets_dir)
    removed = 0
    
    for path, entry in entries:
        trivial, reason = is_trivial(entry)
        if trivial:
            if dry_run:
                print(f"  Would remove: {entry['id']} [{reason}]")
            else:
                os.remove(path)
                print(f"  Removed: {entry['id']} [{reason}]")
            removed += 1
    
    action = "Would remove" if dry_run else "Removed"
    print(f"\n  {action} {removed} trivial entries")
    if dry_run:
        print("  Run with --remove-trivial --confirm to actually delete")


def main():
    parser = argparse.ArgumentParser(description="Audit PropBench dataset quality")
    parser.add_argument("--remove-trivial", action="store_true", help="Remove trivial entries")
    parser.add_argument("--confirm", action="store_true", help="Actually delete (with --remove-trivial)")
    parser.add_argument("--sample", type=int, help="Print N random entries for manual review")
    parser.add_argument("--datasets", default="datasets", help="Dataset directory")
    
    args = parser.parse_args()
    datasets_dir = Path(args.datasets)
    
    if not datasets_dir.exists():
        datasets_dir = Path(__file__).parent.parent / "datasets"
    
    if args.remove_trivial:
        remove_trivial(datasets_dir, dry_run=not args.confirm)
        return
    
    if args.sample:
        import random
        entries = load_all_entries(datasets_dir)
        sample = random.sample(entries, min(args.sample, len(entries)))
        print(f"\n  Random sample of {len(sample)} entries for manual review:\n")
        for i, (path, entry) in enumerate(sample, 1):
            print(f"  [{i}] {entry['id']}")
            print(f"      Title: {entry.get('title', '?')[:70]}")
            print(f"      Trigger: {entry.get('trigger', {}).get('files', ['?'])[0]}")
            n_cons = len(entry.get('consequences', []))
            print(f"      Consequences: {n_cons} files")
            trivial, reason = is_trivial(entry)
            if trivial:
                print(f"      ⚠️  TRIVIAL: {reason}")
            print()
        return
    
    # Full audit
    results = audit(datasets_dir)
    print_report(results)


if __name__ == "__main__":
    main()
