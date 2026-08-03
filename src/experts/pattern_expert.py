from __future__ import annotations
"""
judgment-engine/src/experts/pattern_expert.py

The PatternExpert works like a senior engineer's brain:
1. Classify: "What kind of change is this?"
2. Retrieve: "What's the playbook for that kind of change?"
3. Predict: "Based on the playbook, here's what else needs changing."

This measures: how much of expert judgment is pattern recognition?
"""

from dataclasses import dataclass
from typing import Optional

from ..models import Change, Prediction


# ─── Playbook Definition ──────────────────────────────────────────

@dataclass
class PlaybookPrediction:
    """A single predicted consequence from a playbook."""
    package: str
    confidence: float
    reason: str
    condition: Optional[str] = None  # When this prediction applies


@dataclass
class Playbook:
    """
    A named playbook that fires for a specific type of change.
    
    Each playbook encodes: "When you see THIS kind of change,
    THESE packages need updating."
    """
    id: str
    name: str
    description: str
    
    def triggers(self, change: Change) -> bool:
        """Does this playbook apply to this change?"""
        raise NotImplementedError
    
    def predictions(self, change: Change) -> list[PlaybookPrediction]:
        """What does this playbook predict?"""
        raise NotImplementedError


# ─── Playbooks ────────────────────────────────────────────────────

class AASSourceOnboarding(Playbook):
    """
    Trigger: New source added to AIXAttributeConfigData
    Playbook: GAMCoreModel + AteamIntegrationTests always needed
    
    Evidence: WELLSPRING, GLOBAL_STORE, LLM_DERIVED_V2 all followed this exactly.
    """
    
    def __init__(self):
        super().__init__(
            id="aas-source-onboarding",
            name="AAS Source Onboarding",
            description="Adding a new attribute source to AAS",
        )
    
    def triggers(self, change: Change) -> bool:
        return (
            change.package == "AIXAttributeConfigData"
            and any(
                keyword in change.intent.lower()
                for keyword in ["source", "onboard", "add", "new"]
            )
            and any(
                keyword in change.intent.lower()
                for keyword in ["source", "attribute", "propagat"]
            )
        )
    
    def predictions(self, change: Change) -> list[PlaybookPrediction]:
        preds = [
            PlaybookPrediction(
                package="GAMCoreModel",
                confidence=0.98,
                reason="SourceConfiguration.prototxt must register new source. Without it, config is dead code at runtime.",
            ),
            PlaybookPrediction(
                package="AteamIntegrationTests",
                confidence=0.90,
                reason="Every source onboarding historically includes an integration test (different VS: ATEAMIntegTest/release).",
            ),
        ]
        return preds


class AASAttributeOnboarding(Playbook):
    """
    Trigger: New attribute files added to AIXAttributeConfigData
    Playbook: GAMCoreModel + CAIMS Model + DataOpUtils
    
    Evidence: NO_PHOTO, DRIVEWAY_ACCESS, CUSTOMER_MOBILITY_ISSUES all followed this.
    """
    
    def __init__(self):
        super().__init__(
            id="aas-attribute-onboarding",
            name="AAS New Attribute Onboarding",
            description="Adding entirely new attributes (not new sources for existing attributes)",
        )
    
    def triggers(self, change: Change) -> bool:
        return (
            change.package == "AIXAttributeConfigData"
            and any(
                keyword in change.intent.lower()
                for keyword in ["new attribute", "new boolean", "add attribute",
                                "add three", "add two", "add new"]
            )
        )
    
    def predictions(self, change: Change) -> list[PlaybookPrediction]:
        return [
            PlaybookPrediction(
                package="GAMCoreModel",
                confidence=0.98,
                reason="Proto enum must include new attribute type.",
            ),
            PlaybookPrediction(
                package="CustomerAddressIssueManagementServiceModel",
                confidence=0.75,
                reason="CAIMS service model needs entry for customer-facing API exposure.",
            ),
            PlaybookPrediction(
                package="AddressAttributesDataOpUtils",
                confidence=0.70,
                reason="Validation rules needed for new attribute type.",
            ),
        ]


class CountryExpansion(Playbook):
    """
    Trigger: New country added to CdpModelGenerator
    Playbook: PlainCdpModel root router + ExceptionDatesProvider + sub-configs
    
    Evidence: PR/PT/ZA expansion followed this. ZA bug proved PlainCdpModel is critical.
    """
    
    def __init__(self):
        super().__init__(
            id="country-expansion",
            name="Country Expansion",
            description="Adding a new country to CdpModelGenerator",
        )
    
    def triggers(self, change: Change) -> bool:
        return (
            change.package == "CdpModelGenerator"
            and any(
                keyword in change.intent.lower()
                for keyword in ["country", "countries", "market", "expansion"]
            )
            # Exclude pure holiday additions (those are simpler, separate playbook)
            and not change.intent.lower().startswith("add all missing holidays")
            and not change.intent.lower().startswith("add holidays")
        )
    
    def predictions(self, change: Change) -> list[PlaybookPrediction]:
        return [
            PlaybookPrediction(
                package="CdpModelGenerator",  # same package, different files
                confidence=0.95,
                reason="PlainCdpModel.yaml root router MUST have country entry. Without it, all plain sub-configs are dead.",
            ),
            PlaybookPrediction(
                package="CdpModelGenerator",
                confidence=0.90,
                reason="ExceptionDatesProvider.yaml needs national holidays for new country.",
            ),
        ]


class CrossAccountAccess(Playbook):
    """
    Trigger: CDK change granting cross-account access (SNS policy, IAM trust)
    Playbook: Consumer-side subscription/handler IF we own both sides.
    
    Evidence: Building Summary SNS cross-account needed both producer + consumer.
    Counter-evidence: Necto gamma account addition needed NOTHING (other team handles their side).
    """
    
    def __init__(self):
        super().__init__(
            id="cross-account-access",
            name="Cross-Account Access Grant",
            description="CDK change granting another account access to a resource",
        )
    
    def triggers(self, change: Change) -> bool:
        return (
            "CDK" in change.package
            and any(
                keyword in change.intent.lower()
                for keyword in ["cross-account", "account", "subscribe", "access"]
            )
        )
    
    def predictions(self, change: Change) -> list[PlaybookPrediction]:
        # This is the tricky one: sometimes there IS propagation (we own both sides)
        # and sometimes there ISN'T (other team handles their side).
        # Lower confidence because intent matters more than structure here.
        return [
            PlaybookPrediction(
                package="WellspringOrchestratorCDK",
                confidence=0.45,
                reason="IF we own the consumer side, it needs SQS queue + subscription. But if another team handles theirs, nothing propagates.",
                condition="Only if we're building both sides of the cross-account flow",
            ),
        ]


class NewDependencyInTest(Playbook):
    """
    Trigger: Test file that imports a new SDK not currently in Config
    Playbook: Config file needs the dependency added
    
    Evidence: DefectEventProcessorLambdaTest needed AwsJavaSdk-Sqs in Config.
    Counter-evidence: DefectLifecycleTest needed nothing (Coral client already present).
    """
    
    def __init__(self):
        super().__init__(
            id="new-dependency-in-test",
            name="New SDK Dependency in Test",
            description="Test code that imports a package not currently in Config",
        )
    
    def triggers(self, change: Change) -> bool:
        return (
            "Test" in change.package
            and any(
                keyword in change.intent.lower()
                for keyword in ["sqs", "lambda", "new sdk", "send message"]
            )
        )
    
    def predictions(self, change: Change) -> list[PlaybookPrediction]:
        return [
            PlaybookPrediction(
                package=change.package,  # Config is in the same package
                confidence=0.80,
                reason="New SDK import requires Brazil Config dependency addition. Build will fail without it.",
            ),
        ]


# ─── The Expert (Classifier + Library) ───────────────────────────

class PatternExpert:
    """
    Classifies changes into known archetypes, then applies playbooks.
    
    This measures: "How much of expert judgment is pattern recognition?"
    """
    
    def __init__(self):
        self.playbooks: list[Playbook] = [
            AASAttributeOnboarding(),   # More specific — check first
            AASSourceOnboarding(),      # More general — check second
            CountryExpansion(),
            CrossAccountAccess(),
            NewDependencyInTest(),
        ]
    
    @property
    def name(self) -> str:
        return "PatternExpert"
    
    def classify(self, change: Change) -> Optional[Playbook]:
        """Which playbook fires for this change? First match wins."""
        for playbook in self.playbooks:
            if playbook.triggers(change):
                return playbook
        return None
    
    def predict(self, change: Change) -> list[Prediction]:
        playbook = self.classify(change)
        
        if playbook is None:
            return []  # No known pattern — honest "I don't know"
        
        pb_predictions = playbook.predictions(change)
        
        return [
            Prediction(
                package=p.package,
                confidence=p.confidence,
                reasoning=p.reason,
                evidence=[
                    f"Matched playbook: {playbook.name}",
                    f"Condition: {p.condition}" if p.condition else "",
                ],
                expert_name=f"PatternExpert/{playbook.id}",
            )
            for p in pb_predictions
        ]
