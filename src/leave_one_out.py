from __future__ import annotations
"""
judgment-engine/src/leave_one_out.py

Leave-One-Out Cross-Validation for PropBench.

The proper evaluation protocol:
- For each entry i in the dataset:
  1. Train the Historian on ALL entries EXCEPT i
  2. Predict consequences for entry i
  3. Score the prediction against ground truth
- Average scores across all entries

This gives an unbiased estimate of how well the Historian would perform
on a genuinely unseen entry — no data leakage.

Also implements k-fold for larger evaluations.
"""

import yaml
from pathlib import Path
from typing import Optional
from datetime import datetime

from .models import Change, Consequence, Prediction, Difficulty, Relationship
from .benchmark import load_dataset, parse_entry
from .file_scoring import score_file_level, FileLevelScore, FileLevelReport
from .experts.historian import Historian


def leave_one_out_historian(
    dataset: list[tuple[Change, list[Consequence]]],
    raw_entries: list[dict],
    verbose: bool = False,
) -> FileLevelReport:
    """
    Run leave-one-out evaluation for the Historian.
    
    For each entry:
    1. Train on all OTHER entries
    2. Predict for this entry
    3. Score
    
    Returns FileLevelReport with per-entry scores.
    """
    assert len(dataset) == len(raw_entries), "Dataset and raw_entries must be same length"
    
    scores = []
    n = len(dataset)
    
    for i in range(n):
        # Train on everything except entry i
        train_entries = raw_entries[:i] + raw_entries[i+1:]
        
        historian = Historian()
        historian.train(train_entries, verbose=False)
        
        # Predict for entry i
        change, actual = dataset[i]
        predictions = historian.predict(change)
        
        # Score
        score = score_file_level(change, predictions, actual, "Historian-LOO")
        scores.append(score)
        
        if verbose and i % 25 == 0:
            print(f"  LOO progress: {i+1}/{n} ({score.basename_recall:.0%} recall for {change.id})")
    
    return FileLevelReport(expert_name="Historian (leave-one-out)", scores=scores)


def k_fold_historian(
    dataset: list[tuple[Change, list[Consequence]]],
    raw_entries: list[dict],
    k: int = 5,
    verbose: bool = False,
) -> FileLevelReport:
    """
    k-fold cross-validation. Faster than LOO but slightly less precise.
    
    Splits dataset into k folds, trains on k-1, tests on 1.
    """
    import random
    
    n = len(dataset)
    indices = list(range(n))
    random.seed(42)  # reproducible
    random.shuffle(indices)
    
    fold_size = n // k
    all_scores = []
    
    for fold in range(k):
        # Define test set
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < k - 1 else n
        test_indices = set(indices[test_start:test_end])
        train_indices = [j for j in range(n) if j not in test_indices]
        
        # Train
        train_entries = [raw_entries[j] for j in train_indices]
        historian = Historian()
        historian.train(train_entries, verbose=False)
        
        # Test
        for idx in test_indices:
            change, actual = dataset[idx]
            predictions = historian.predict(change)
            score = score_file_level(change, predictions, actual, f"Historian-{k}fold")
            all_scores.append(score)
        
        if verbose:
            fold_scores = all_scores[-(test_end - test_start):]
            valid = [s for s in fold_scores if s.actual_files]
            avg_r = sum(s.basename_recall for s in valid) / len(valid) if valid else 0
            print(f"  Fold {fold+1}/{k}: {len(valid)} entries, avg recall {avg_r:.0%}")
    
    return FileLevelReport(expert_name=f"Historian ({k}-fold CV)", scores=all_scores)


def run_full_evaluation(datasets_dir: Path, verbose: bool = True) -> dict:
    """
    Run the complete evaluation suite and return results.
    
    Returns dict with all metrics for the paper.
    """
    # Load data
    dataset = load_dataset(datasets_dir)
    
    # Load raw entries for training
    raw_entries = []
    families_dir = datasets_dir / "families"
    for family_dir in sorted(families_dir.iterdir()):
        if not family_dir.is_dir():
            continue
        for yaml_file in sorted(family_dir.glob("*.yaml")):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                if data and "consequences" in data:
                    raw_entries.append(data)
            except:
                pass
    
    if verbose:
        print(f"Dataset: {len(dataset)} entries, {len(raw_entries)} raw entries")
        print()
    
    results = {}
    
    # 1. FilePredictor (context-free baseline)
    if verbose:
        print("Running FilePredictor...")
    from .experts.file_predictor import FilePredictor
    from .file_scoring import score_expert_file_level
    
    fp = FilePredictor()
    fp_report = score_expert_file_level(fp, dataset)
    results["FilePredictor"] = {
        "basename_recall": fp_report.avg_basename_recall,
        "basename_precision": fp_report.avg_basename_precision,
        "files_found": fp_report.total_basename_hits,
        "total_files": fp_report.total_actual_files,
        "method": "context-free (naming conventions)",
    }
    if verbose:
        print(f"  {fp_report.summary()}")
        print()
    
    # 2. Historian (trained on full dataset — upper bound)
    if verbose:
        print("Running Historian (full training — upper bound)...")
    historian_full = Historian()
    historian_full.train(raw_entries, verbose=False)
    hist_full_report = score_expert_file_level(historian_full, dataset)
    results["Historian_full"] = {
        "basename_recall": hist_full_report.avg_basename_recall,
        "basename_precision": hist_full_report.avg_basename_precision,
        "files_found": hist_full_report.total_basename_hits,
        "total_files": hist_full_report.total_actual_files,
        "method": "trained on ALL data (upper bound, overfitted)",
    }
    if verbose:
        print(f"  {hist_full_report.summary()}")
        print()
    
    # 3. Historian (5-fold CV — fair estimate)
    if verbose:
        print("Running Historian (5-fold CV — fair estimate)...")
    hist_cv_report = k_fold_historian(dataset, raw_entries, k=5, verbose=verbose)
    results["Historian_5fold"] = {
        "basename_recall": hist_cv_report.avg_basename_recall,
        "basename_precision": hist_cv_report.avg_basename_precision,
        "files_found": hist_cv_report.total_basename_hits,
        "total_files": hist_cv_report.total_actual_files,
        "method": "5-fold cross-validation (fair estimate)",
    }
    if verbose:
        print(f"  {hist_cv_report.summary()}")
        print()
    
    # 4. Summary
    if verbose:
        print("=" * 60)
        print("  PROPBENCH FILE-LEVEL EVALUATION RESULTS")
        print("=" * 60)
        print(f"  {'Expert':<30} {'Recall':<10} {'Precision':<10} {'Method'}")
        print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*30}")
        for name, r in results.items():
            print(f"  {name:<30} {r['basename_recall']:<10.0%} {r['basename_precision']:<10.0%} {r['method']}")
        print("=" * 60)
    
    return results


if __name__ == "__main__":
    results = run_full_evaluation(Path("datasets"))
