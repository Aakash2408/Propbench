"""
judgment-engine/src/experts/historian.py

Historian Oracle: Learned Co-Change Knowledge Graph

The FIRST oracle that learns automatically from data (rather than hand-written rules).

Architecture:
1. Build a weighted graph from git history (training data)
   - Nodes = files
   - Edges = co-change relationships
   - Edge weight = confidence (co-changes / total changes)
2. For a new change, predict the top-N neighbors in the graph
3. Score against held-out test data

Key design decisions:
- Time decay: recent co-changes weighted higher than old ones
- Multi-level: file→file, directory→directory, extension→extension
- Train/test split: NEVER evaluate on training data
- Threshold: only predict edges with confidence > min_confidence
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from ..models import Change, Prediction


@dataclass
class CoChangeEdge:
    """A weighted edge in the co-change graph."""
    source: str           # file path
    target: str           # file path
    count: int = 0        # number of times they co-changed
    total_source_changes: int = 0  # total times source changed
    authors: set = field(default_factory=set)  # who made these changes
    last_seen: Optional[datetime] = None
    
    @property
    def confidence(self) -> float:
        """P(target changes | source changes)"""
        if self.total_source_changes == 0:
            return 0.0
        return self.count / self.total_source_changes
    
    def time_decayed_confidence(self, reference_date: datetime, half_life_days: int = 180) -> float:
        """Confidence with exponential time decay."""
        if not self.last_seen:
            return self.confidence
        days_ago = (reference_date - self.last_seen).days
        if days_ago < 0:
            days_ago = 0
        decay = math.exp(-0.693 * days_ago / half_life_days)  # 0.693 = ln(2)
        return self.confidence * decay


class CoChangeGraph:
    """
    A knowledge graph of file co-change relationships.
    
    Built from git history. Used for prediction.
    """
    
    def __init__(self, min_confidence: float = 0.15, min_count: int = 2):
        self.edges: dict[str, list[CoChangeEdge]] = defaultdict(list)
        self.file_change_counts: dict[str, int] = defaultdict(int)
        self.min_confidence = min_confidence
        self.min_count = min_count
    
    def add_commit(self, files: list[str], author: str = "", date: Optional[datetime] = None):
        """
        Add a commit to the graph. Every pair of files in the commit
        gets a co-change edge (bidirectional).
        """
        # Update change counts
        for f in files:
            self.file_change_counts[f] += 1
        
        # Add edges for all pairs
        for i, source in enumerate(files):
            for j, target in enumerate(files):
                if i == j:
                    continue
                
                # Find or create edge
                edge = self._get_or_create_edge(source, target)
                edge.count += 1
                edge.total_source_changes = self.file_change_counts[source]
                if author:
                    edge.authors.add(author)
                if date:
                    edge.last_seen = max(edge.last_seen, date) if edge.last_seen else date
    
    def _get_or_create_edge(self, source: str, target: str) -> CoChangeEdge:
        """Get existing edge or create new one."""
        for edge in self.edges[source]:
            if edge.target == target:
                return edge
        edge = CoChangeEdge(source=source, target=target)
        self.edges[source].append(edge)
        return edge
    
    def predict(self, trigger_files: list[str], reference_date: Optional[datetime] = None,
                top_n: int = 5) -> list[tuple[str, float, str]]:
        """
        Given trigger files, return predicted consequence files.
        
        Returns: [(file_path, confidence, reasoning), ...]
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        # Collect all candidate targets
        candidates: dict[str, float] = {}
        candidate_reasons: dict[str, str] = {}
        
        for trigger in trigger_files:
            # Exact file match
            for edge in self.edges.get(trigger, []):
                if edge.count >= self.min_count:
                    conf = edge.time_decayed_confidence(reference_date)
                    if conf >= self.min_confidence:
                        if trigger not in edge.target:  # don't predict trigger itself
                            key = edge.target
                            if key not in candidates or candidates[key] < conf:
                                candidates[key] = conf
                                candidate_reasons[key] = (
                                    f"Co-changed {edge.count}x "
                                    f"(conf={edge.confidence:.0%}, "
                                    f"authors={len(edge.authors)})"
                                )
            
            # Directory-level: if no exact match, try directory neighbors
            trigger_dir = "/".join(trigger.split("/")[:-1])
            if trigger_dir and trigger not in self.edges:
                for source, edges in self.edges.items():
                    source_dir = "/".join(source.split("/")[:-1])
                    if source_dir == trigger_dir:
                        for edge in edges:
                            if edge.count >= self.min_count:
                                conf = edge.time_decayed_confidence(reference_date) * 0.6  # discount
                                if conf >= self.min_confidence:
                                    key = edge.target
                                    if key not in candidates or candidates[key] < conf:
                                        candidates[key] = conf
                                        candidate_reasons[key] = (
                                            f"Directory neighbor co-change "
                                            f"(via {source.split('/')[-1]})"
                                        )
        
        # Sort by confidence, return top N
        sorted_candidates = sorted(candidates.items(), key=lambda x: -x[1])[:top_n]
        
        return [
            (path, conf, candidate_reasons.get(path, ""))
            for path, conf in sorted_candidates
        ]
    
    @property
    def num_nodes(self) -> int:
        return len(self.file_change_counts)
    
    @property
    def num_edges(self) -> int:
        return sum(len(edges) for edges in self.edges.values())
    
    def stats(self) -> str:
        return f"CoChangeGraph: {self.num_nodes} files, {self.num_edges} edges"


class Historian:
    """
    Historian Oracle: predicts file-level consequences from co-change history.
    
    Must be trained on a subset of the dataset BEFORE being evaluated.
    Uses train/test split to avoid memorizing the benchmark.
    """
    
    def __init__(self, graph: Optional[CoChangeGraph] = None):
        self.graph = graph or CoChangeGraph()
        self._trained = False
    
    @property
    def name(self) -> str:
        return "Historian"
    
    def train(self, entries: list[dict], verbose: bool = False):
        """
        Build the co-change graph from training entries.
        
        Each entry has trigger files + consequence files = one "commit" of co-changes.
        """
        for entry in entries:
            trigger_files = entry.get("trigger", {}).get("files", [])
            consequence_files = []
            for c in entry.get("consequences", []):
                consequence_files.extend(c.get("files", []))
            
            # All files in this entry co-changed
            all_files = [f for f in trigger_files + consequence_files if f]
            if len(all_files) >= 2:
                author = entry.get("author", "")
                date_str = str(entry.get("date", ""))
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                except (ValueError, TypeError):
                    date = None
                
                self.graph.add_commit(all_files, author=author, date=date)
        
        self._trained = True
        if verbose:
            print(f"  Historian trained: {self.graph.stats()}")
    
    def predict(self, change: Change) -> list[Prediction]:
        """Predict consequence files based on co-change history."""
        if not self._trained:
            return []
        
        results = self.graph.predict(
            trigger_files=change.files_changed,
            reference_date=change.date if change.date else datetime.now(),
            top_n=5,
        )
        
        predictions = []
        for file_path, confidence, reasoning in results:
            predictions.append(Prediction(
                package=change.package,
                files=[file_path],
                confidence=confidence,
                reasoning=f"Historical co-change: {reasoning}",
                evidence=[
                    f"Trigger: {change.files_changed[0] if change.files_changed else '?'}",
                    f"Graph: {self.graph.stats()}",
                ],
                expert_name=self.name,
            ))
        
        return predictions


def train_test_split(entries: list, test_ratio: float = 0.2, seed: int = 42):
    """
    Split entries into train and test sets.
    
    Uses chronological split if dates are available (more realistic),
    otherwise random split.
    """
    import random
    
    # Try chronological split (most realistic)
    dated = [(e, e.get("date", "")) for e in entries]
    dated.sort(key=lambda x: str(x[1]))
    
    split_idx = int(len(dated) * (1 - test_ratio))
    train = [e for e, _ in dated[:split_idx]]
    test = [e for e, _ in dated[split_idx:]]
    
    return train, test
