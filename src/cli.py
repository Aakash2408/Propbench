"""
judgment-engine/src/cli.py

THE SACRED COMMAND.

    $ python -m src.cli

Runs all oracles against the dataset. Prints the leaderboard.
"""

import sys
from pathlib import Path

from .benchmark import load_dataset, run_all_experts, format_leaderboard
from .experts.baselines import (
    NullExpert, AlwaysGAMExpert, SamePackageExpert, DirectDepsExpert
)
from .experts.pattern_expert import PatternExpert
from .experts.structure_expert import StructureExpert
from .experts.ensemble import EnsembleOracle
from .experts.human_baselines import EstimatedJuniorBaseline, EstimatedSeniorBaseline
from .experts.file_predictor import FilePredictor


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    datasets_dir = Path("datasets")
    
    if not datasets_dir.exists():
        datasets_dir = Path(__file__).parent.parent / "datasets"
    
    print("\n  Loading dataset...")
    dataset = load_dataset(datasets_dir)
    print(f"  Found {len(dataset)} changes across {_count_families(dataset)} families")
    
    if not dataset:
        print("  ⚠️  No dataset found. Check datasets/families/ directory.")
        sys.exit(1)
    
    # Register all oracles
    oracles = [
        # Baselines
        NullExpert(),
        SamePackageExpert(),
        DirectDepsExpert(),
        # Human baselines (estimated)
        EstimatedJuniorBaseline(),
        EstimatedSeniorBaseline(),
        # Real oracles
        PatternExpert(),
        StructureExpert(),    # Code structure (uses "StructureOracle" as name internally)
        # File-level oracle
        FilePredictor(),
        # Ensemble
        EnsembleOracle(),
    ]
    
    print(f"  Running {len(oracles)} oracles...")
    
    reports = run_all_experts(oracles, dataset, verbose=verbose)
    
    # Print leaderboard
    print(format_leaderboard(reports))
    
    # File-level metrics (where available)
    print("  FILE-LEVEL SCORING (same-package predictions):")
    for report in reports:
        file_p_vals = [r.file_precision for r in report.results if r.file_precision is not None]
        file_r_vals = [r.file_recall for r in report.results if r.file_recall is not None]
        if file_p_vals:
            avg_fp = sum(file_p_vals) / len(file_p_vals)
            avg_fr = sum(file_r_vals) / len(file_r_vals)
            print(f"    {report.expert_name:20s} File-P={avg_fp:.0%} File-R={avg_fr:.0%} ({len(file_p_vals)} entries)")
    
    # Coverage
    print("\n  COVERAGE:")
    for report in reports:
        triggered = sum(1 for r in report.results if r.predicted)
        coverage = triggered / report.n if report.n else 0
        print(f"    {report.expert_name:20s} {triggered}/{report.n} = {coverage:.0%}")
    
    # Summary
    best_r = max(reports, key=lambda r: r.avg_recall)
    print(f"\n  Best recall: {best_r.expert_name} @ R={best_r.avg_recall:.0%}")
    print(f"  Target: 80%+ recall with 80%+ precision")
    print(f"  Gap to target recall: {max(0, 0.80 - best_r.avg_recall):.0%}\n")


def _count_families(dataset) -> int:
    return len({change.family for change, _ in dataset})


if __name__ == "__main__":
    main()
