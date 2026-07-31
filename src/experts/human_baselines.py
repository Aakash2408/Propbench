"""
judgment-engine/src/experts/human_baselines.py

Human and LLM baselines for comparison.

These aren't real oracles — they're RECORDED predictions from humans/LLMs
on the same dataset entries. Used to contextualize what "81% recall" means.

Usage:
1. For each dataset entry, ask a human (or LLM) to predict consequences
   given ONLY the trigger change
2. Record their predictions in the dataset YAML under `baselines:`
3. This oracle replays those recorded predictions for scoring

Format in YAML:
```yaml
baselines:
  junior:
    predictions: ["GAMCoreModel"]
    time_seconds: 120
  senior:
    predictions: ["GAMCoreModel", "AteamIntegrationTests"]
    time_seconds: 8
  gpt4:
    predictions: ["GAMCoreModel", "AteamIntegrationTests", "GeoStudio"]
    time_seconds: 3
```
"""

from ..models import Change, Prediction


class HumanBaseline:
    """
    Replays recorded human predictions from dataset entries.
    
    Each dataset entry can include `baselines:` with predictions
    from different humans/LLMs. This oracle just reads them back
    for scoring.
    """
    
    def __init__(self, baseline_name: str, predictions_map: dict[str, list[str]]):
        """
        baseline_name: e.g. "Junior Engineer", "Senior Engineer", "GPT-4"
        predictions_map: {change_id: [predicted_packages]}
        """
        self._name = baseline_name
        self.predictions_map = predictions_map
    
    @property
    def name(self) -> str:
        return self._name
    
    def predict(self, change: Change) -> list[Prediction]:
        preds = self.predictions_map.get(change.id, [])
        return [
            Prediction(
                package=pkg,
                confidence=0.7,  # humans don't give calibrated confidence
                reasoning=f"Human prediction ({self._name})",
                evidence=[f"Recorded baseline from {self._name}"],
                expert_name=self._name,
            )
            for pkg in preds
        ]


def load_baselines_from_dataset(dataset, baseline_name: str) -> "HumanBaseline":
    """
    Load a named baseline from all dataset entries that have it.
    
    Looks for `baselines.<name>.predictions` in each YAML entry.
    Returns a HumanBaseline oracle that replays those predictions.
    """
    predictions_map = {}
    # This would parse from the YAML — for now, use hardcoded estimates
    return HumanBaseline(baseline_name, predictions_map)


# ─── Estimated baselines (based on the project's analysis) ─────────

class EstimatedJuniorBaseline:
    """
    Estimated: what would a junior engineer (1-2 years, new to this codebase)
    predict given only the triggering change?
    
    Assumptions:
    - Knows basic language constructs (imports → deps)
    - Does NOT know organizational playbooks
    - Does NOT know historical patterns
    - Can read the code structure
    - Misses cross-package propagation frequently
    """
    
    @property
    def name(self) -> str:
        return "Junior (est.)"
    
    def predict(self, change: Change) -> list[Prediction]:
        # Junior only predicts same-package changes (files they can see)
        # and obvious structural deps (if they check)
        preds = []
        
        # Junior notices if there's an obvious test file
        if any("test" in f.lower() or "Test" in f for f in change.files_changed):
            pass  # already in a test, won't predict more
        else:
            # Might think "I should update tests" but not know WHERE
            preds.append(Prediction(
                package=change.package,
                confidence=0.4,
                reasoning="Should probably update tests somewhere",
                evidence=["General awareness"],
                expert_name=self.name,
            ))
        
        return preds


class EstimatedSeniorBaseline:
    """
    Estimated: what would a senior engineer (5+ years, knows this codebase)
    predict given only the triggering change?
    
    Assumptions:
    - Knows all organizational playbooks
    - Knows historical patterns from memory
    - Has runtime/operational experience
    - Occasionally misses hidden couplings (like CSG GeoRaven)
    - Very high precision (rarely predicts wrong things)
    """
    
    # For a proper baseline, you'd record ACTUAL senior predictions
    # on the dataset entries. This is a placeholder estimate.
    
    @property
    def name(self) -> str:
        return "Senior (est.)"
    
    def predict(self, change: Change) -> list[Prediction]:
        # A senior would use pattern knowledge first
        # This is a rough approximation — real baseline needs real predictions
        preds = []
        
        # Senior knows AAS onboarding playbook
        if change.package == "AIXAttributeConfigData":
            preds.append(Prediction(
                package="GAMCoreModel",
                confidence=0.95,
                reasoning="Senior knows the AAS onboarding playbook",
                evidence=["Organizational memory"],
                expert_name=self.name,
            ))
            preds.append(Prediction(
                package="AteamIntegrationTests",
                confidence=0.85,
                reasoning="Senior knows integ tests are always needed",
                evidence=["Organizational memory"],
                expert_name=self.name,
            ))
        
        # Senior knows country expansion pattern
        if change.package == "CdpModelGenerator" and "country" in change.intent.lower():
            preds.append(Prediction(
                package="CdpModelGenerator",
                confidence=0.90,
                reasoning="Senior knows PlainCdpModel + ExceptionDates needed",
                evidence=["Organizational memory"],
                expert_name=self.name,
            ))
        
        # Senior knows cross-account = two sides
        if "CDK" in change.package and "cross-account" in change.intent.lower():
            preds.append(Prediction(
                package="WellspringOrchestratorCDK",
                confidence=0.70,
                reasoning="Senior knows cross-account needs consumer-side too",
                evidence=["Architectural knowledge"],
                expert_name=self.name,
            ))
        
        # Senior knows config can have multiple consumers
        if "config" in change.intent.lower() and ("remove" in change.intent.lower() or "disable" in change.intent.lower()):
            preds.append(Prediction(
                package=change.package,
                confidence=0.60,
                reasoning="Senior checks for other consumers of shared config",
                evidence=["Operational experience"],
                expert_name=self.name,
            ))
        
        return preds
