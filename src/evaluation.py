from __future__ import annotations
"""
judgment-engine/src/evaluation.py

Comprehensive evaluation module for PropBench.

Computes precision, recall, F1 with bootstrap confidence intervals,
stratified analysis by difficulty and cross-repo status, per-family
metrics, and statistical significance tests between baselines.

Usage:
    python3 src/evaluation.py --baseline file_predictor|historian|llm \
        --dataset datasets/frozen/v1.0.yaml
"""

import argparse
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

# Local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.models import Change, Consequence, Prediction
from src.benchmark import parse_entry
from src.experts.file_predictor import FilePredictor
from src.experts.historian import Historian

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

SEED = 42
BOOTSTRAP_ITERATIONS = 1000


# ─── Data Structures ──────────────────────────────────────────────

@dataclass
class MetricSet:
    """Precision, recall, F1 for a single evaluation."""
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class MetricWithCI:
    """Metric with 95% confidence interval."""
    value: float = 0.0
    ci_low: float = 0.0
    ci_high: float = 0.0

    def __str__(self) -> str:
        return f"{self.value:.3f} [{self.ci_low:.3f}, {self.ci_high:.3f}]"


@dataclass
class EvalResult:
    """Full evaluation result for one baseline."""
    baseline_name: str
    n_entries: int = 0
    precision: MetricWithCI = field(default_factory=MetricWithCI)
    recall: MetricWithCI = field(default_factory=MetricWithCI)
    f1: MetricWithCI = field(default_factory=MetricWithCI)
    per_stratum: dict = field(default_factory=dict)   # difficulty -> MetricSet
    per_family: dict = field(default_factory=dict)    # family -> MetricSet
    same_pkg: MetricSet = field(default_factory=MetricSet)
    cross_pkg: MetricSet = field(default_factory=MetricSet)


# ─── Dataset Loading ──────────────────────────────────────────────

def load_frozen_dataset(path: Path) -> List[Tuple[Change, List[Consequence]]]:
    """Load the frozen v1.0 dataset (multi-document YAML)."""
    entries = []
    with open(path) as f:
        docs = list(yaml.safe_load_all(f))

    # First doc is metadata, rest is the entry list
    if len(docs) < 2:
        return []

    entry_list = docs[1] if isinstance(docs[1], list) else []
    for data in entry_list:
        if not data or not isinstance(data, dict):
            continue
        try:
            # Reuse parse logic inline (frozen format matches raw)
            from datetime import datetime
            from src.models import Difficulty, Relationship

            diff_str = data.get("difficulty", "medium")
            difficulty = Difficulty(diff_str) if isinstance(diff_str, str) else Difficulty.MEDIUM

            change = Change(
                id=data["id"],
                title=data["title"],
                family=data["family"],
                date=datetime.strptime(str(data["date"]), "%Y-%m-%d"),
                author=data["author"],
                package=data["trigger"]["package"],
                files_changed=data["trigger"].get("files", []),
                intent=data["trigger"]["intent"],
                diff_summary=data["trigger"].get("diff_summary", ""),
                difficulty=difficulty,
                required_knowledge=data.get("required_knowledge", []),
                version_set=data["trigger"].get("version_set"),
                cr_ids=data.get("cr_ids", []),
            )

            consequences = []
            for c in data.get("consequences", []):
                if not c:
                    continue
                consequences.append(Consequence(
                    package=c["package"],
                    files=c.get("files", []),
                    description=c["description"],
                    mechanical=c.get("mechanical", False),
                    relationship=Relationship(c.get("relationship", "co-change")),
                    confidence_expert_would_predict=c.get(
                        "confidence_an_expert_would_predict", 0.5),
                    reasoning=c.get("reasoning", ""),
                    optional=c.get("optional", False),
                    surprise=c.get("surprise", False),
                    lag=c.get("lag"),
                ))
            entries.append((change, consequences))
        except Exception:
            continue
    return entries


# ─── Core Metrics ─────────────────────────────────────────────────

def compute_file_metrics(
    predictions: List[Prediction],
    consequences: List[Consequence],
) -> MetricSet:
    """Compute precision/recall/F1 at file level for one entry."""
    predicted_files = set()
    for p in predictions:
        for f in p.files:
            predicted_files.add(f)

    ground_truth_files = set()
    for c in consequences:
        for f in c.files:
            ground_truth_files.add(f)

    if not predicted_files and not ground_truth_files:
        return MetricSet(1.0, 1.0, 1.0)
    if not predicted_files:
        return MetricSet(0.0, 0.0, 0.0)
    if not ground_truth_files:
        return MetricSet(0.0, 0.0, 0.0)

    true_positives = len(predicted_files & ground_truth_files)
    precision = true_positives / len(predicted_files) if predicted_files else 0.0
    recall = true_positives / len(ground_truth_files) if ground_truth_files else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return MetricSet(precision=precision, recall=recall, f1=f1)


def aggregate_metrics(metric_list: List[MetricSet]) -> MetricSet:
    """Macro-average a list of per-entry metrics."""
    if not metric_list:
        return MetricSet()
    n = len(metric_list)
    return MetricSet(
        precision=sum(m.precision for m in metric_list) / n,
        recall=sum(m.recall for m in metric_list) / n,
        f1=sum(m.f1 for m in metric_list) / n,
    )


# ─── Bootstrap Confidence Intervals ──────────────────────────────

def bootstrap_ci(
    metric_list: List[MetricSet],
    field_name: str,
    n_iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = SEED,
) -> MetricWithCI:
    """Compute 95% CI for a metric field via bootstrap resampling."""
    rng = random.Random(seed)
    values = [getattr(m, field_name) for m in metric_list]
    n = len(values)

    if n == 0:
        return MetricWithCI()

    point_estimate = sum(values) / n
    bootstrap_means = []

    for _ in range(n_iterations):
        sample = [rng.choice(values) for _ in range(n)]
        bootstrap_means.append(sum(sample) / n)

    bootstrap_means.sort()
    ci_low = bootstrap_means[int(0.025 * n_iterations)]
    ci_high = bootstrap_means[int(0.975 * n_iterations)]

    return MetricWithCI(value=point_estimate, ci_low=ci_low, ci_high=ci_high)


# ─── Stratified Analysis ─────────────────────────────────────────

def classify_difficulty(consequences: List[Consequence]) -> str:
    """Classify entry difficulty by consequence file count."""
    total_files = sum(len(c.files) for c in consequences)
    if total_files <= 3:
        return "EASY"
    elif total_files <= 8:
        return "MEDIUM"
    else:
        return "HARD"


def classify_cross_repo(
    change: Change, consequences: List[Consequence]
) -> str:
    """Classify whether consequences are same-package or cross-package."""
    trigger_pkg = change.package
    for c in consequences:
        if c.package != trigger_pkg:
            return "CROSS"
    return "SAME"


# ─── Statistical Significance ────────────────────────────────────

def significance_test(
    metrics_a: List[MetricSet],
    metrics_b: List[MetricSet],
    field_name: str = "f1",
) -> Optional[Tuple[str, float]]:
    """Paired Wilcoxon signed-rank test between two baselines.

    Returns (test_name, p_value) or None if scipy unavailable.
    """
    if not HAS_SCIPY:
        return None
    if len(metrics_a) != len(metrics_b):
        return None

    values_a = [getattr(m, field_name) for m in metrics_a]
    values_b = [getattr(m, field_name) for m in metrics_b]
    diffs = [a - b for a, b in zip(values_a, values_b)]

    # Skip if all diffs are zero
    if all(d == 0.0 for d in diffs):
        return ("wilcoxon", 1.0)

    try:
        stat, p_value = scipy_stats.wilcoxon(diffs)
        return ("wilcoxon", p_value)
    except Exception:
        return None


# ─── Run Baseline ─────────────────────────────────────────────────

def get_baseline(name: str):
    """Instantiate a baseline by name."""
    if name == "file_predictor":
        return FilePredictor()
    elif name == "historian":
        return Historian()
    elif name == "llm":
        # LLM baseline stub -- returns empty predictions
        class LLMBaseline:
            @property
            def name(self) -> str:
                return "LLM_Simulated"
            def predict(self, change: Change) -> List[Prediction]:
                return []
        return LLMBaseline()
    else:
        raise ValueError(f"Unknown baseline: {name}")


def evaluate_baseline(
    baseline_name: str,
    dataset: List[Tuple[Change, List[Consequence]]],
) -> Tuple[EvalResult, List[MetricSet]]:
    """Run a baseline against the full dataset, return structured results."""
    baseline = get_baseline(baseline_name)
    all_metrics = []  # type: List[MetricSet]
    stratum_metrics = defaultdict(list)  # type: dict[str, List[MetricSet]]
    family_metrics = defaultdict(list)   # type: dict[str, List[MetricSet]]
    same_metrics = []  # type: List[MetricSet]
    cross_metrics = []  # type: List[MetricSet]

    for change, consequences in dataset:
        predictions = baseline.predict(change)
        m = compute_file_metrics(predictions, consequences)
        all_metrics.append(m)

        # Stratified
        difficulty = classify_difficulty(consequences)
        stratum_metrics[difficulty].append(m)

        # Cross-repo
        cross_class = classify_cross_repo(change, consequences)
        if cross_class == "SAME":
            same_metrics.append(m)
        else:
            cross_metrics.append(m)

        # Per-family
        family_metrics[change.family].append(m)

    result = EvalResult(
        baseline_name=baseline_name,
        n_entries=len(dataset),
        precision=bootstrap_ci(all_metrics, "precision"),
        recall=bootstrap_ci(all_metrics, "recall"),
        f1=bootstrap_ci(all_metrics, "f1"),
        per_stratum={k: aggregate_metrics(v) for k, v in stratum_metrics.items()},
        per_family={k: aggregate_metrics(v) for k, v in sorted(family_metrics.items())},
        same_pkg=aggregate_metrics(same_metrics),
        cross_pkg=aggregate_metrics(cross_metrics),
    )
    return result, all_metrics


# ─── Markdown Report ──────────────────────────────────────────────

def format_report(result: EvalResult, sig_result: Optional[Tuple[str, float]] = None) -> str:
    """Generate a formatted markdown results table."""
    lines = []
    lines.append(f"# PropBench Evaluation: {result.baseline_name}")
    lines.append(f"")
    lines.append(f"**Dataset**: {result.n_entries} entries")
    lines.append(f"**Bootstrap**: {BOOTSTRAP_ITERATIONS} iterations, seed={SEED}")
    lines.append(f"")

    # Overall metrics
    lines.append("## Overall Metrics (with 95% CI)")
    lines.append("")
    lines.append("| Metric    | Value | 95% CI |")
    lines.append("|-----------|-------|--------|")
    lines.append(f"| Precision | {result.precision.value:.3f} "
                 f"| [{result.precision.ci_low:.3f}, {result.precision.ci_high:.3f}] |")
    lines.append(f"| Recall    | {result.recall.value:.3f} "
                 f"| [{result.recall.ci_low:.3f}, {result.recall.ci_high:.3f}] |")
    lines.append(f"| F1        | {result.f1.value:.3f} "
                 f"| [{result.f1.ci_low:.3f}, {result.f1.ci_high:.3f}] |")
    lines.append("")

    # Stratified by difficulty
    lines.append("## Stratified by Difficulty")
    lines.append("")
    lines.append("| Stratum | N | Precision | Recall | F1 |")
    lines.append("|---------|---|-----------|--------|-----|")
    for stratum in ["EASY", "MEDIUM", "HARD"]:
        if stratum in result.per_stratum:
            m = result.per_stratum[stratum]
            lines.append(f"| {stratum} | - | {m.precision:.3f} "
                         f"| {m.recall:.3f} | {m.f1:.3f} |")
    lines.append("")

    # Cross-repo analysis
    lines.append("## Cross-Package Analysis")
    lines.append("")
    lines.append("| Scope | Precision | Recall | F1 |")
    lines.append("|-------|-----------|--------|-----|")
    lines.append(f"| Same package   | {result.same_pkg.precision:.3f} "
                 f"| {result.same_pkg.recall:.3f} | {result.same_pkg.f1:.3f} |")
    lines.append(f"| Cross package  | {result.cross_pkg.precision:.3f} "
                 f"| {result.cross_pkg.recall:.3f} | {result.cross_pkg.f1:.3f} |")
    lines.append("")

    # Per-family (top 10 by entry count)
    lines.append("## Per-Family Metrics")
    lines.append("")
    lines.append("| Family | Precision | Recall | F1 |")
    lines.append("|--------|-----------|--------|-----|")
    for family, m in result.per_family.items():
        lines.append(f"| {family} | {m.precision:.3f} "
                     f"| {m.recall:.3f} | {m.f1:.3f} |")
    lines.append("")

    # Significance test
    if sig_result:
        test_name, p_value = sig_result
        sig_str = "✓ significant" if p_value < 0.05 else "✗ not significant"
        lines.append("## Statistical Significance")
        lines.append("")
        lines.append(f"- Test: {test_name}")
        lines.append(f"- p-value: {p_value:.4f} ({sig_str} at α=0.05)")
        lines.append("")

    return "\n".join(lines)


# ─── CLI Entry Point ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PropBench comprehensive evaluation")
    parser.add_argument(
        "--baseline", required=True,
        choices=["file_predictor", "historian", "llm"],
        help="Baseline to evaluate")
    parser.add_argument(
        "--dataset", required=True,
        help="Path to frozen dataset YAML")
    parser.add_argument(
        "--compare", default=None,
        choices=["file_predictor", "historian", "llm"],
        help="Optional second baseline for significance test")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: dataset not found at {dataset_path}")
        sys.exit(1)

    print(f"Loading dataset from {dataset_path}...")
    dataset = load_frozen_dataset(dataset_path)
    if not dataset:
        print("Error: no entries loaded from dataset")
        sys.exit(1)
    print(f"Loaded {len(dataset)} entries")

    print(f"\nEvaluating baseline: {args.baseline}")
    result, metrics_a = evaluate_baseline(args.baseline, dataset)

    sig_result = None
    if args.compare:
        print(f"Evaluating comparison baseline: {args.compare}")
        _, metrics_b = evaluate_baseline(args.compare, dataset)
        sig_result = significance_test(metrics_a, metrics_b, "f1")
        if sig_result is None:
            print("  (scipy not available, skipping significance test)")

    report = format_report(result, sig_result)
    print("\n" + report)


if __name__ == "__main__":
    main()
