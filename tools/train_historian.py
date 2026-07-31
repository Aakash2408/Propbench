#!/usr/bin/env python3
"""
judgment-engine/tools/train_historian.py

Train the Historian oracle on the mined dataset and evaluate
with proper train/test split.

Usage:
    python3 tools/train_historian.py
    python3 tools/train_historian.py --test-ratio 0.3
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.experts.historian import Historian, CoChangeGraph, train_test_split
from src.experts.file_predictor import FilePredictor
from src.benchmark import load_dataset, run_expert
from src.models import Change, Consequence, Prediction, ReplayResult, BenchmarkReport

import yaml


def load_raw_entries(datasets_dir: Path) -> list[dict]:
    """Load all entries as raw dicts (for training)."""
    entries = []
    families_dir = datasets_dir / "families"
    for yaml_file in sorted(families_dir.rglob("*.yaml")):
        if yaml_file.name == "schema.yaml":
            continue
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and isinstance(data, dict) and "id" in data:
                entries.append(data)
        except Exception:
            pass
    return entries


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--min-confidence", type=float, default=0.15)
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    
    datasets_dir = Path("datasets")
    if not datasets_dir.exists():
        datasets_dir = Path(__file__).parent.parent / "datasets"
    
    # Load raw entries
    print("\n  Loading dataset...")
    raw_entries = load_raw_entries(datasets_dir)
    print(f"  Total entries: {len(raw_entries)}")
    
    # Train/test split
    train_entries, test_entries = train_test_split(raw_entries, test_ratio=args.test_ratio)
    print(f"  Train: {len(train_entries)}")
    print(f"  Test:  {len(test_entries)}")
    
    # Build and train Historian
    graph = CoChangeGraph(min_confidence=args.min_confidence, min_count=args.min_count)
    historian = Historian(graph=graph)
    historian.train(train_entries, verbose=True)
    
    # Evaluate on test set using the benchmark framework
    # Convert test entries to (Change, [Consequence]) format
    from src.benchmark import parse_entry
    
    test_dataset = []
    for entry in test_entries:
        # Write to temp, parse back (reuse existing parser)
        try:
            from datetime import datetime
            from src.models import Change, Consequence, Relationship, Difficulty
            
            trigger = entry.get("trigger", {})
            diff_str = entry.get("difficulty", "medium")
            try:
                difficulty = Difficulty(diff_str)
            except (ValueError, KeyError):
                difficulty = Difficulty.MEDIUM
            
            change = Change(
                id=entry["id"],
                title=entry.get("title", ""),
                family=entry.get("family", "unknown"),
                date=datetime.strptime(str(entry.get("date", "2025-01-01")), "%Y-%m-%d"),
                author=entry.get("author", ""),
                package=trigger.get("package", ""),
                files_changed=trigger.get("files", []),
                intent=trigger.get("intent", ""),
                diff_summary=trigger.get("diff_summary", ""),
                difficulty=difficulty,
            )
            
            consequences = []
            for c in entry.get("consequences", []):
                if not c:
                    continue
                consequences.append(Consequence(
                    package=c.get("package", ""),
                    files=c.get("files", []),
                    description=c.get("description", ""),
                    mechanical=c.get("mechanical", False),
                    relationship=Relationship(c.get("relationship", "co-change")),
                    confidence_expert_would_predict=c.get("confidence_an_expert_would_predict", 0.5),
                    reasoning=c.get("reasoning", ""),
                ))
            
            test_dataset.append((change, consequences))
        except Exception as e:
            if args.verbose:
                print(f"  ⚠️  Skipped {entry.get('id', '?')}: {e}")
    
    print(f"  Parsed test entries: {len(test_dataset)}")
    
    # Run Historian on test set
    print("\n  Running Historian on test set...")
    historian_report = run_expert(historian, test_dataset, verbose=args.verbose)
    
    # Also run FilePredictor for comparison
    file_pred_report = run_expert(FilePredictor(), test_dataset)
    
    # Report
    print(f"\n{'═'*60}")
    print(f"  HISTORIAN EVALUATION (test set, n={len(test_dataset)})")
    print(f"{'═'*60}")
    print(f"\n  Package-level:")
    print(f"    Historian:     P={historian_report.avg_precision:.0%} R={historian_report.avg_recall:.0%}")
    print(f"    FilePredictor: P={file_pred_report.avg_precision:.0%} R={file_pred_report.avg_recall:.0%}")
    
    # File-level
    h_file_hits = len([r for r in historian_report.results if r.file_recall and r.file_recall > 0])
    f_file_hits = len([r for r in file_pred_report.results if r.file_recall and r.file_recall > 0])
    
    h_file_recalls = [r.file_recall for r in historian_report.results if r.file_recall is not None and r.file_recall > 0]
    f_file_recalls = [r.file_recall for r in file_pred_report.results if r.file_recall is not None and r.file_recall > 0]
    
    h_avg_fr = sum(r.file_recall for r in historian_report.results if r.file_recall is not None) / max(1, len([r for r in historian_report.results if r.file_recall is not None]))
    f_avg_fr = sum(r.file_recall for r in file_pred_report.results if r.file_recall is not None) / max(1, len([r for r in file_pred_report.results if r.file_recall is not None]))
    
    print(f"\n  File-level:")
    print(f"    Historian:     File-R={h_avg_fr:.0%}  ({h_file_hits}/{len(test_dataset)} entries hit)")
    print(f"    FilePredictor: File-R={f_avg_fr:.0%}  ({f_file_hits}/{len(test_dataset)} entries hit)")
    
    # Show best Historian predictions
    print(f"\n  Top Historian hits:")
    hits = [(r, r.file_recall) for r in historian_report.results if r.file_recall and r.file_recall > 0]
    hits.sort(key=lambda x: -x[1])
    for r, fr in hits[:10]:
        pred_files = [f.split("/")[-1] for p in r.predicted for f in p.files if f]
        print(f"    {r.change.id[:35]:35s} File-R={fr:.0%}  predicted: {pred_files[:3]}")
    
    print(f"\n  Graph stats: {historian.graph.stats()}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()
