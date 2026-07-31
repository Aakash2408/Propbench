"""
judgment-engine/src/benchmark.py

THE SACRED COMMAND.

Run all experts against the dataset. Score independently. Print results.
Everything reduces to this one invocation.
"""

import yaml
from pathlib import Path
from datetime import datetime
from typing import Protocol

from .models import (
    Change, Consequence, Prediction, Relationship, Difficulty,
    ReplayResult, BenchmarkReport
)


# ─── Dataset Loading ──────────────────────────────────────────────

def load_dataset(datasets_dir: Path) -> list[tuple[Change, list[Consequence]]]:
    """Load all YAML dataset files into Change + Consequence pairs."""
    dataset = []
    families_dir = datasets_dir / "families"
    
    if not families_dir.exists():
        return []
    
    for family_dir in sorted(families_dir.iterdir()):
        if not family_dir.is_dir():
            continue
        for yaml_file in sorted(family_dir.glob("*.yaml")):
            try:
                change, consequences = parse_entry(yaml_file)
                dataset.append((change, consequences))
            except Exception as e:
                print(f"  ⚠️  Failed to parse {yaml_file.name}: {e}")
    
    return dataset


def parse_entry(path: Path) -> tuple[Change, list[Consequence]]:
    """Parse a single YAML dataset entry."""
    with open(path) as f:
        data = yaml.safe_load(f)
    
    # Parse difficulty
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
        if not c:  # skip empty/null entries
            continue
        consequences.append(Consequence(
            package=c["package"],
            files=c.get("files", []),
            description=c["description"],
            mechanical=c.get("mechanical", False),
            relationship=Relationship(c.get("relationship", "co-change")),
            confidence_expert_would_predict=c.get("confidence_an_expert_would_predict", 0.5),
            reasoning=c.get("reasoning", ""),
            optional=c.get("optional", False),
            surprise=c.get("surprise", False),
            lag=c.get("lag"),
        ))
    
    return change, consequences


# ─── Benchmark Runner ─────────────────────────────────────────────

def run_expert(
    expert,
    dataset: list[tuple[Change, list[Consequence]]],
    verbose: bool = False,
) -> BenchmarkReport:
    """Run one expert against the full dataset. Return scored report."""
    results = []
    
    for change, actual in dataset:
        predicted = expert.predict(change)
        
        result = ReplayResult(
            change=change,
            predicted=predicted,
            actual=actual,
            expert_name=expert.name,
        )
        result.compute_metrics()
        results.append(result)
        
        if verbose:
            status = "✓" if result.recall == 1.0 else "✗" if result.recall == 0.0 else "~"
            pred_str = [p.package for p in predicted] or ["(nothing)"]
            actual_str = [c.package for c in actual if not c.optional] or ["(nothing)"]
            print(f"  {status} {change.id}")
            print(f"    Predicted: {pred_str}")
            print(f"    Actual:    {actual_str}")
            print(f"    P={result.precision:.0%} R={result.recall:.0%}")
    
    return BenchmarkReport(expert_name=expert.name, results=results)


def run_all_experts(
    experts: list,
    dataset: list[tuple[Change, list[Consequence]]],
    verbose: bool = False,
) -> list[BenchmarkReport]:
    """Run all experts independently. Return list of reports."""
    reports = []
    for expert in experts:
        if verbose:
            print(f"\n{'─'*55}")
            print(f"  Running: {expert.name}")
            print(f"{'─'*55}")
        report = run_expert(expert, dataset, verbose=verbose)
        reports.append(report)
    return reports


def format_leaderboard(reports: list[BenchmarkReport]) -> str:
    """Format the comparison leaderboard."""
    # Sort by recall (most important: did we find everything?)
    sorted_reports = sorted(reports, key=lambda r: r.avg_recall, reverse=True)
    
    lines = [
        "",
        "╔═══════════════════════════════════════════════════════╗",
        "║          JUDGMENT ENGINE BENCHMARK                    ║",
        "╠═══════════════════════════════════════════════════════╣",
        f"║  Dataset: {sorted_reports[0].n if sorted_reports else 0} changes"
        f"{'':40s}║",
        "╠═══════════════════════════════════════════════════════╣",
        "║  Expert               P      R    Top1   FP          ║",
        "╠═══════════════════════════════════════════════════════╣",
    ]
    
    for r in sorted_reports:
        name = r.expert_name[:20]
        lines.append(
            f"║  {name:20s} {r.avg_precision:5.0%}  "
            f"{r.avg_recall:5.0%}  {r.top1_rate:4.0%}   "
            f"{r.total_false_positives:2d}          ║"
        )
    
    lines.extend([
        "╠═══════════════════════════════════════════════════════╣",
        "║  P=Precision  R=Recall  FP=False Positives           ║",
        "╚═══════════════════════════════════════════════════════╝",
    ])
    
    return "\n".join(lines)
