from __future__ import annotations
"""
judgment-engine/src/experts/ensemble.py

The simplest possible ensemble: union of Pattern + Structure.

No ML. No fancy weighting. Just:
1. Collect predictions from both oracles
2. Deduplicate by package
3. Combine confidence (boost when both agree)
4. Preserve which oracle(s) contributed

This answers: "Is Pattern + Structure actually 82% combined,
or was our independence analysis misleading?"
"""

from ..models import Change, Prediction
from .pattern_expert import PatternExpert
from .structure_expert import StructureExpert


class EnsembleOracle:
    """
    Union of PatternOracle + StructureOracle.
    
    When both predict the same package: confidence boosted.
    When only one predicts: use that oracle's confidence.
    """
    
    def __init__(self):
        self.pattern = PatternExpert()
        self.structure = StructureExpert()
    
    @property
    def name(self) -> str:
        return "Ensemble(P+S)"
    
    def predict(self, change: Change) -> list[Prediction]:
        pattern_preds = self.pattern.predict(change)
        structure_preds = self.structure.predict(change)
        
        # Simple union — collect all predictions from both oracles
        by_package: dict[str, list[Prediction]] = {}
        
        for p in pattern_preds:
            by_package.setdefault(p.package, []).append(p)
        for s in structure_preds:
            by_package.setdefault(s.package, []).append(s)
        
        # Merge
        merged = []
        for package, preds in by_package.items():
            sources = set(p.expert_name for p in preds)
            confidences = [p.confidence for p in preds]
            
            # Both agree → boost confidence (cap at 0.99)
            if len(preds) > 1:
                combined_conf = min(0.99, max(confidences) + 0.1)
                agreement = "BOTH"
            else:
                combined_conf = max(confidences)
                agreement = "SINGLE"
            
            # Collect all evidence and reasoning
            all_evidence = []
            all_reasoning = []
            for p in preds:
                all_evidence.extend(p.evidence)
                all_reasoning.append(f"[{p.expert_name}] {p.reasoning}")
            
            merged.append(Prediction(
                package=package,
                confidence=combined_conf,
                reasoning=" | ".join(all_reasoning),
                evidence=all_evidence + [f"Agreement: {agreement} ({', '.join(sources)})"],
                expert_name=f"Ensemble({', '.join(sorted(sources))})",
            ))
        
        # Sort by confidence descending
        merged.sort(key=lambda p: p.confidence, reverse=True)
        return merged
