"""
judgment-engine/src/models.py

Core data structures for the judgment engine research instrument.

Design principle: Each "expert" votes independently. The benchmark
scores them separately. The ensemble comes last.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol


class Relationship(Enum):
    STRUCTURAL = "structural"
    CO_CHANGE = "co-change"
    PATTERN = "pattern"
    CAUSAL = "causal"


class Difficulty(Enum):
    TRIVIAL = "trivial"      # Direct dependency, any tool could catch
    EASY = "easy"            # Straightforward, clear pattern
    MEDIUM = "medium"        # Requires pattern recognition or history
    HARD = "hard"            # Requires architectural or runtime knowledge
    EXPERT = "expert"        # Requires tribal knowledge or runtime understanding
    DECEPTIVE = "deceptive"  # Looks easy but has hidden gotchas


# ─── Dataset Models ───────────────────────────────────────────────

@dataclass
class Change:
    """A code change that triggered propagation (input to predictor)."""
    id: str
    title: str
    family: str
    date: datetime
    author: str
    package: str
    files_changed: list[str]
    intent: str
    diff_summary: str
    difficulty: Difficulty = Difficulty.MEDIUM
    required_knowledge: list[str] = field(default_factory=list)
    version_set: Optional[str] = None
    cr_ids: list[str] = field(default_factory=list)


@dataclass
class Consequence:
    """A downstream change that was actually required (ground truth)."""
    package: str
    files: list[str]
    description: str
    mechanical: bool
    relationship: Relationship
    confidence_expert_would_predict: float
    reasoning: str
    optional: bool = False
    surprise: bool = False
    lag: Optional[str] = None


# ─── Prediction Models ────────────────────────────────────────────

@dataclass
class Prediction:
    """A single prediction from one expert."""
    package: str
    confidence: float           # 0.0 - 1.0
    reasoning: str
    evidence: list[str]
    expert_name: str            # which expert produced this
    files: list[str] = field(default_factory=list)  # predicted files (for file-level scoring)


# ─── Expert Interface ─────────────────────────────────────────────

class Expert(Protocol):
    """Every expert implements this interface."""
    
    @property
    def name(self) -> str: ...
    
    def predict(self, change: Change) -> list[Prediction]: ...


# ─── Scoring ──────────────────────────────────────────────────────

@dataclass
class ReplayResult:
    """Comparison of prediction vs reality for one change."""
    change: Change
    predicted: list[Prediction]
    actual: list[Consequence]
    expert_name: str  # which expert (or "ensemble")
    
    precision: float = 0.0
    recall: float = 0.0
    top1_correct: bool = False
    top3_correct: bool = False
    
    surprises: list[Consequence] = field(default_factory=list)
    false_positives: list[Prediction] = field(default_factory=list)
    missed: list[Consequence] = field(default_factory=list)
    
    def compute_metrics(self):
        predicted_packages = {p.package for p in self.predicted}
        actual_packages = {c.package for c in self.actual if not c.optional}
        
        # ─── Package-level scoring ────────────────────────────────
        if predicted_packages and actual_packages:
            correct = predicted_packages & actual_packages
            self.precision = len(correct) / len(predicted_packages)
            self.recall = len(correct) / len(actual_packages)
        elif not predicted_packages and not actual_packages:
            self.precision = 1.0
            self.recall = 1.0
        elif not predicted_packages:
            self.precision = 1.0
            self.recall = 0.0
        else:
            self.precision = 0.0
            self.recall = 1.0
        
        # ─── File-level scoring (for same-package consequences) ───
        # When consequence is in the SAME package as trigger,
        # check if predicted FILES match actual FILES
        self.file_precision = None
        self.file_recall = None
        
        same_pkg_actual_files = set()
        same_pkg_predicted_files = set()
        
        for c in self.actual:
            if c.package == self.change.package and not c.optional:
                for f in c.files:
                    if f:  # skip empty
                        same_pkg_actual_files.add(f.split("/")[-1])  # basename
        
        for p in self.predicted:
            if p.package == self.change.package:
                for f in p.files:
                    if f:
                        same_pkg_predicted_files.add(f.split("/")[-1])
        
        if same_pkg_actual_files or same_pkg_predicted_files:
            if same_pkg_predicted_files and same_pkg_actual_files:
                correct_files = same_pkg_predicted_files & same_pkg_actual_files
                self.file_precision = len(correct_files) / len(same_pkg_predicted_files) if same_pkg_predicted_files else 1.0
                self.file_recall = len(correct_files) / len(same_pkg_actual_files) if same_pkg_actual_files else 1.0
            elif not same_pkg_predicted_files and same_pkg_actual_files:
                self.file_precision = 1.0
                self.file_recall = 0.0
            elif same_pkg_predicted_files and not same_pkg_actual_files:
                self.file_precision = 0.0
                self.file_recall = 1.0
        
        # ─── Top-K ────────────────────────────────────────────────
        if self.predicted and actual_packages:
            self.top1_correct = self.predicted[0].package in actual_packages
            top3 = {p.package for p in self.predicted[:3]}
            self.top3_correct = actual_packages.issubset(top3)
        elif not self.predicted and not actual_packages:
            self.top1_correct = True
            self.top3_correct = True
        
        # ─── Analysis ─────────────────────────────────────────────
        self.surprises = [c for c in self.actual if c.surprise]
        self.false_positives = [
            p for p in self.predicted
            if p.package not in actual_packages
        ]
        self.missed = [
            c for c in self.actual
            if c.package not in predicted_packages and not c.optional
        ]


@dataclass
class BenchmarkReport:
    """Aggregate results for one expert across all replays."""
    expert_name: str
    results: list[ReplayResult]
    
    @property
    def n(self) -> int:
        return len(self.results)
    
    @property
    def avg_precision(self) -> float:
        return sum(r.precision for r in self.results) / self.n if self.n else 0
    
    @property
    def avg_recall(self) -> float:
        return sum(r.recall for r in self.results) / self.n if self.n else 0
    
    @property
    def avg_file_recall(self) -> float:
        """Average file-level recall (only for entries with file-level data)."""
        file_results = [r for r in self.results if r.file_recall is not None]
        if not file_results:
            return 0.0
        return sum(r.file_recall for r in file_results) / len(file_results)
    
    @property
    def avg_file_precision(self) -> float:
        """Average file-level precision."""
        file_results = [r for r in self.results if r.file_precision is not None]
        if not file_results:
            return 0.0
        return sum(r.file_precision for r in file_results) / len(file_results)
    
    @property
    def top1_rate(self) -> float:
        return sum(r.top1_correct for r in self.results) / self.n if self.n else 0
    
    @property
    def top3_rate(self) -> float:
        return sum(r.top3_correct for r in self.results) / self.n if self.n else 0
    
    @property
    def total_surprises(self) -> int:
        return sum(len(r.surprises) for r in self.results)
    
    @property
    def total_false_positives(self) -> int:
        return sum(len(r.false_positives) for r in self.results)
    
    def by_family(self) -> dict[str, "BenchmarkReport"]:
        families: dict[str, list[ReplayResult]] = {}
        for r in self.results:
            families.setdefault(r.change.family, []).append(r)
        return {k: BenchmarkReport(self.expert_name, v) for k, v in families.items()}
    
    def by_difficulty(self) -> dict[str, "BenchmarkReport"]:
        groups: dict[str, list[ReplayResult]] = {}
        for r in self.results:
            groups.setdefault(r.change.difficulty.value, []).append(r)
        return {k: BenchmarkReport(self.expert_name, v) for k, v in groups.items()}
    
    def format_compact(self) -> str:
        return (
            f"  {self.expert_name:20s} "
            f"P={self.avg_precision:.0%} "
            f"R={self.avg_recall:.0%} "
            f"Top1={self.top1_rate:.0%} "
            f"FP={self.total_false_positives}"
        )
    
    def format_full(self) -> str:
        lines = [
            f"\n{'═'*55}",
            f"  {self.expert_name}",
            f"{'═'*55}",
            f"  Dataset:        {self.n} changes",
            f"  Precision:      {self.avg_precision:.1%}",
            f"  Recall:         {self.avg_recall:.1%}",
            f"  Top-1:          {self.top1_rate:.1%}",
            f"  Top-3:          {self.top3_rate:.1%}",
            f"  False Pos:      {self.total_false_positives}",
            f"  Surprises:      {self.total_surprises}",
        ]
        
        # By family
        lines.append(f"\n{'─'*55}")
        lines.append("  BY FAMILY:")
        for fam, report in sorted(self.by_family().items()):
            lines.append(
                f"    {fam:28s} P={report.avg_precision:.0%} "
                f"R={report.avg_recall:.0%} ({report.n})"
            )
        
        # By difficulty
        lines.append(f"\n{'─'*55}")
        lines.append("  BY DIFFICULTY:")
        for diff, report in sorted(self.by_difficulty().items()):
            lines.append(
                f"    {diff:28s} P={report.avg_precision:.0%} "
                f"R={report.avg_recall:.0%} ({report.n})"
            )
        
        # Worst misses
        lines.append(f"\n{'─'*55}")
        lines.append("  WORST:")
        worst = sorted(self.results, key=lambda r: r.recall)[:3]
        for r in worst:
            missed_str = ", ".join(c.package for c in r.missed) or "—"
            lines.append(f"    {r.change.id}: R={r.recall:.0%} missed=[{missed_str}]")
        
        lines.append(f"{'═'*55}")
        return "\n".join(lines)
