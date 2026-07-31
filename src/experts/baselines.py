"""
judgment-engine/src/experts/baselines.py

Baseline "experts" that establish the accuracy floor.
If your real expert can't beat these, it's not worth building.

Strategy 0: What does a trivial algorithm already get?
"""

from ..models import Change, Prediction


class NullExpert:
    """Predicts nothing. Establishes the recall floor (0%) and precision ceiling (100%)."""
    
    @property
    def name(self) -> str:
        return "NullExpert"
    
    def predict(self, change: Change) -> list[Prediction]:
        return []


class AlwaysGAMExpert:
    """
    Always predicts GAMCoreModel + AteamIntegrationTests.
    
    This is the "lazy senior engineer" baseline: when in doubt,
    assume the proto and tests need updating. How often is that right?
    """
    
    @property
    def name(self) -> str:
        return "AlwaysGAM+Tests"
    
    def predict(self, change: Change) -> list[Prediction]:
        return [
            Prediction(
                package="GAMCoreModel",
                confidence=0.7,
                reasoning="Most changes need proto update",
                evidence=["baseline assumption"],
                expert_name=self.name,
            ),
            Prediction(
                package="AteamIntegrationTests",
                confidence=0.5,
                reasoning="Most changes need test update",
                evidence=["baseline assumption"],
                expert_name=self.name,
            ),
        ]


class SamePackageExpert:
    """
    Only predicts changes within the same package (other files).
    
    Tests whether intra-package prediction is trivial.
    If this scores high, the "hard" part is only cross-package prediction.
    """
    
    @property
    def name(self) -> str:
        return "SamePackage"
    
    def predict(self, change: Change) -> list[Prediction]:
        # Can't predict specific files without more info,
        # but we predict the trigger package itself will have more changes
        return [
            Prediction(
                package=change.package,
                confidence=0.6,
                reasoning="Other files in same package likely affected",
                evidence=[f"Trigger is in {change.package}"],
                expert_name=self.name,
            ),
        ]


class DirectDepsExpert:
    """
    Predicts all packages that directly depend on the trigger package.
    
    This is "just read the dependency graph" — no intelligence.
    The critical baseline: if this gets 80%, you don't need AI.
    
    Requires a dependency map to be loaded.
    """
    
    def __init__(self, dep_map: dict[str, list[str]] | None = None):
        """
        dep_map: {package: [packages that depend on it]}
        If None, uses a hardcoded map from known Amazon packages.
        """
        self.dep_map = dep_map or self._default_map()
    
    @property
    def name(self) -> str:
        return "DirectDeps"
    
    def predict(self, change: Change) -> list[Prediction]:
        dependents = self.dep_map.get(change.package, [])
        return [
            Prediction(
                package=dep,
                confidence=0.6,
                reasoning=f"Directly depends on {change.package}",
                evidence=[f"Dependency graph: {dep} imports {change.package}"],
                expert_name=self.name,
            )
            for dep in dependents
        ]
    
    @staticmethod
    def _default_map() -> dict[str, list[str]]:
        """
        Hardcoded dependency map from known packages.
        This represents what you'd get from parsing Brazil Config files.
        """
        return {
            # AAS ecosystem
            "AIXAttributeConfigData": ["GAMCoreModel"],
            "GAMCoreModel": ["AteamIntegrationTests", "AddressAttributesDataOpUtils"],
            
            # GeoStudio ecosystem  
            "GeoStudioDeliveryHistoryCDK": [],  # CDK has no downstream code deps
            
            # CdpModelGenerator is self-contained
            "CdpModelGenerator": [],
            
            # RDMS test package
            "RepeatDefectsManagementServiceTests": [],
            
            # SAA
            "SmartAddressAssistantWebApp": [],
            
            # CSG
            "CSGAndGCSIntegrationLambdaGeo": [],
            
            # Necto CDK
            "NectoChangesetProcessorCDK": [],
        }
