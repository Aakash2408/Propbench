from __future__ import annotations
"""
judgment-engine/src/file_scoring.py

File-Level Scoring for PropBench.

The package-level scoring (already implemented) asks:
  "Did you predict the right PACKAGE?"

File-level scoring (THIS module) asks:
  "Did you predict the right FILE within the right package?"

This is much harder because:
- 1223 consequence files across 256 entries
- FilePredictor gets 8% recall at file level
- Historian gets 25%
- Pattern+Structure gets 82% at package level but file-level unknown

Scoring modes:
1. EXACT: predicted file path must exactly match actual file path
2. BASENAME: just the filename must match (ignores directory)
3. FUZZY: predicted file path must be "close" to actual (edit distance)
4. SEMANTIC: predicted file pattern (glob) matches actual file

Default is BASENAME (most practical — directory structures vary).
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import Change, Consequence, Prediction, ReplayResult


@dataclass
class FileLevelScore:
    """File-level scoring for a single replay."""
    change_id: str
    expert_name: str
    
    # All actual files across all consequence packages
    actual_files: list[str] = field(default_factory=list)
    # All predicted files across all predictions
    predicted_files: list[str] = field(default_factory=list)
    
    # Matches
    exact_matches: list[str] = field(default_factory=list)
    basename_matches: list[str] = field(default_factory=list)
    
    # Metrics
    exact_precision: float = 0.0
    exact_recall: float = 0.0
    basename_precision: float = 0.0
    basename_recall: float = 0.0
    
    def compute(self):
        """Compute file-level metrics."""
        if not self.actual_files and not self.predicted_files:
            self.exact_precision = 1.0
            self.exact_recall = 1.0
            self.basename_precision = 1.0
            self.basename_recall = 1.0
            return
        
        # Normalize paths
        actual_set = set(self.actual_files)
        predicted_set = set(self.predicted_files)
        actual_basenames = set(_basename(f) for f in self.actual_files)
        predicted_basenames = set(_basename(f) for f in self.predicted_files)
        
        # Exact matching
        self.exact_matches = list(actual_set & predicted_set)
        if predicted_set:
            self.exact_precision = len(self.exact_matches) / len(predicted_set)
        if actual_set:
            self.exact_recall = len(self.exact_matches) / len(actual_set)
        
        # Basename matching (more lenient)
        basename_hits = actual_basenames & predicted_basenames
        self.basename_matches = list(basename_hits)
        if predicted_basenames:
            self.basename_precision = len(basename_hits) / len(predicted_basenames)
        if actual_basenames:
            self.basename_recall = len(basename_hits) / len(actual_basenames)


@dataclass
class FileLevelReport:
    """Aggregate file-level scores for one expert."""
    expert_name: str
    scores: list[FileLevelScore] = field(default_factory=list)
    
    @property
    def n(self) -> int:
        """Number of entries scored."""
        return len(self.scores)
    
    @property
    def n_with_files(self) -> int:
        """Entries that have file-level data."""
        return len([s for s in self.scores if s.actual_files])
    
    @property
    def avg_exact_recall(self) -> float:
        valid = [s for s in self.scores if s.actual_files]
        return sum(s.exact_recall for s in valid) / len(valid) if valid else 0.0
    
    @property
    def avg_exact_precision(self) -> float:
        valid = [s for s in self.scores if s.actual_files]
        return sum(s.exact_precision for s in valid) / len(valid) if valid else 0.0
    
    @property
    def avg_basename_recall(self) -> float:
        valid = [s for s in self.scores if s.actual_files]
        return sum(s.basename_recall for s in valid) / len(valid) if valid else 0.0
    
    @property
    def avg_basename_precision(self) -> float:
        valid = [s for s in self.scores if s.actual_files]
        return sum(s.basename_precision for s in valid) / len(valid) if valid else 0.0
    
    @property
    def total_actual_files(self) -> int:
        return sum(len(s.actual_files) for s in self.scores)
    
    @property
    def total_predicted_files(self) -> int:
        return sum(len(s.predicted_files) for s in self.scores)
    
    @property
    def total_basename_hits(self) -> int:
        return sum(len(s.basename_matches) for s in self.scores)
    
    def summary(self) -> str:
        return (
            f"{self.expert_name}: "
            f"Basename R={self.avg_basename_recall:.0%} P={self.avg_basename_precision:.0%} "
            f"| Exact R={self.avg_exact_recall:.0%} P={self.avg_exact_precision:.0%} "
            f"| {self.total_basename_hits}/{self.total_actual_files} files found "
            f"({self.n_with_files} entries with file data)"
        )


def score_file_level(
    change: Change,
    predictions: list[Prediction],
    actual: list[Consequence],
    expert_name: str,
) -> FileLevelScore:
    """
    Compute file-level score for a single prediction.
    
    Compares ALL predicted files (across all predicted packages)
    against ALL actual consequence files (across all packages).
    """
    # Collect all actual files
    actual_files = []
    for c in actual:
        if not c.optional:
            for f in c.files:
                if f:
                    actual_files.append(f)
    
    # Collect all predicted files
    predicted_files = []
    for p in predictions:
        for f in p.files:
            if f:
                predicted_files.append(f)
    
    score = FileLevelScore(
        change_id=change.id,
        expert_name=expert_name,
        actual_files=actual_files,
        predicted_files=predicted_files,
    )
    score.compute()
    return score


def score_expert_file_level(
    expert,
    dataset: list[tuple[Change, list[Consequence]]],
) -> FileLevelReport:
    """
    Run file-level scoring for one expert across the full dataset.
    """
    scores = []
    
    for change, actual in dataset:
        predictions = expert.predict(change)
        score = score_file_level(change, predictions, actual, expert.name)
        scores.append(score)
    
    return FileLevelReport(expert_name=expert.name, scores=scores)


def format_file_leaderboard(reports: list[FileLevelReport]) -> str:
    """Format file-level comparison table."""
    sorted_reports = sorted(reports, key=lambda r: r.avg_basename_recall, reverse=True)
    
    lines = [
        "",
        "╔═══════════════════════════════════════════════════════════════╗",
        "║          FILE-LEVEL SCORING                                  ║",
        "╠═══════════════════════════════════════════════════════════════╣",
        "║  Expert               Basename R  Basename P  Exact R  Files ║",
        "╠═══════════════════════════════════════════════════════════════╣",
    ]
    
    for r in sorted_reports:
        name = r.expert_name[:20]
        lines.append(
            f"║  {name:20s} {r.avg_basename_recall:8.0%}    "
            f"{r.avg_basename_precision:8.0%}    {r.avg_exact_recall:5.0%}  "
            f"{r.total_basename_hits:4d}/{r.total_actual_files:<4d} ║"
        )
    
    lines.extend([
        "╠═══════════════════════════════════════════════════════════════╣",
        "║  Basename = filename match (ignores directory)               ║",
        "║  Exact = full path match                                     ║",
        "╚═══════════════════════════════════════════════════════════════╝",
    ])
    
    return "\n".join(lines)


# === Helpers ===

def _basename(filepath: str) -> str:
    """Extract filename from a path."""
    return filepath.rstrip("/").split("/")[-1] if filepath else ""
