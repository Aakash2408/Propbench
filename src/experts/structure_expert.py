from __future__ import annotations
"""
judgment-engine/src/experts/structure_expert.py

ORACLE: Structure

Tests hypothesis H2: "The codebase structure already contains
the missing information."

This expert knows ONLY what's derivable from:
- File co-location (same directory = related)
- Naming conventions (Config, Manager, Utils = trio)
- Import relationships (if parseable)
- File type patterns (*.proto → consumers exist)

It does NOT know:
- Historical patterns
- Organizational playbooks
- Who changed what before
- Runtime behavior

If this expert moves recall significantly, the knowledge lives in the code.
If it doesn't, the knowledge lives in humans.
"""

from ..models import Change, Prediction


# ─── Structural Rules ─────────────────────────────────────────────
# Each rule encodes a structural relationship derivable from
# reading the codebase WITHOUT any historical knowledge.

class StructureExpert:
    """
    Predicts consequences based purely on code structure.
    
    Rules:
    1. Config-Utils-Manager trio (Java service pattern)
    2. Same-package other files in same directory
    3. Proto file changed → consumers in same VS likely affected
    4. Config file (Brazil) → package build may need updating
    5. YAML/JSON config → other files that reference the same keys
    """
    
    @property
    def name(self) -> str:
        return "StructureOracle"
    
    def predict(self, change: Change) -> list[Prediction]:
        predictions = []
        
        # Apply all structural rules
        predictions += self._rule_config_utils_manager(change)
        predictions += self._rule_same_dir_related_files(change)
        predictions += self._rule_multi_invoker_config(change)
        predictions += self._rule_root_config_reference(change)
        predictions += self._rule_new_import_needs_dep(change)
        
        # Deduplicate by package
        seen = set()
        deduped = []
        for p in predictions:
            key = (p.package, p.reasoning[:50])
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        
        return deduped
    
    def _rule_config_utils_manager(self, change: Change) -> list[Prediction]:
        """
        Java service pattern: Config + Utils + Manager are a trio.
        If you change one, the other two likely need updating.
        
        Derivable from: file naming conventions in the same package.
        """
        predictions = []
        
        for f in change.files_changed:
            f_lower = f.lower()
            
            # If changing a Utils file → Config + Manager likely affected
            if "utils" in f_lower or "util" in f_lower:
                predictions.append(Prediction(
                    package=change.package,
                    confidence=0.75,
                    reasoning="Utils file changed → Config class likely needs updating (Config-Utils-Manager pattern)",
                    evidence=[f"Changed: {f}", "Java service trio pattern"],
                    expert_name=self.name,
                ))
                predictions.append(Prediction(
                    package=change.package,
                    confidence=0.70,
                    reasoning="Utils file changed → Manager class likely needs updating (Config-Utils-Manager pattern)",
                    evidence=[f"Changed: {f}", "Java service trio pattern"],
                    expert_name=self.name,
                ))
            
            # If changing a Config file → Manager likely affected
            if "config" in f_lower and "config.cfg" not in f_lower:
                predictions.append(Prediction(
                    package=change.package,
                    confidence=0.65,
                    reasoning="Config class changed → Manager class likely needs updating",
                    evidence=[f"Changed: {f}", "Java service trio pattern"],
                    expert_name=self.name,
                ))
        
        return predictions
    
    def _rule_same_dir_related_files(self, change: Change) -> list[Prediction]:
        """
        Files in the same directory that share a naming root are related.
        
        e.g., configProvider.ts + snsPolicyProvider.ts in same lib/ dir.
        e.g., personalizedCdpConfig/ has per-country files.
        """
        predictions = []
        
        # If changing multiple files in same dir, predict the package itself
        if len(change.files_changed) >= 2:
            dirs = set()
            for f in change.files_changed:
                parts = f.rsplit("/", 1)
                if len(parts) > 1:
                    dirs.add(parts[0])
            
            # Multiple files but same directory = likely more files in that dir
            if len(dirs) == 1:
                predictions.append(Prediction(
                    package=change.package,
                    confidence=0.55,
                    reasoning="Multiple files changed in same directory → other files in that directory may need updating",
                    evidence=[f"Changed files share directory: {list(dirs)[0]}"],
                    expert_name=self.name,
                ))
        
        return predictions
    
    def _rule_multi_invoker_config(self, change: Change) -> list[Prediction]:
        """
        Config files can be shared by multiple consumers.
        
        If a config file is being REMOVED or significantly altered,
        flag that other consumers of the same config may be affected.
        
        Derivable from: static analysis of who imports/reads the config file.
        """
        predictions = []
        
        for f in change.files_changed:
            f_lower = f.lower()
            
            # Config files (JSON, YAML) in a multi-handler package
            if ("config" in f_lower or "configuration" in f_lower) and \
               (".json" in f_lower or ".yaml" in f_lower):
                # If the intent mentions "remove" or "disable"
                if any(word in change.intent.lower() for word in ["remove", "disable", "delete"]):
                    predictions.append(Prediction(
                        package=change.package,
                        confidence=0.60,
                        reasoning="Removing/disabling config entry — other handlers in this package may also read this config file",
                        evidence=[
                            f"Config file modified: {f}",
                            "Intent includes removal/disable language",
                            "Config files are often shared across multiple Lambda handlers",
                        ],
                        expert_name=self.name,
                    ))
        
        return predictions
    
    def _rule_root_config_reference(self, change: Change) -> list[Prediction]:
        """
        When adding entries to sub-configs, a root config/router usually
        needs updating too.
        
        Derivable from: directory structure showing parent-child config relationship.
        e.g., personalizedCdpConfig/PR/ exists → PlainCdpModel.yaml needs routing entry.
        """
        predictions = []
        
        for f in change.files_changed:
            # If files are in subdirectories (sub-configs), parent config may need updating
            parts = f.split("/")
            if len(parts) >= 3:  # e.g., src/personalizedCdpConfig/PR/...
                predictions.append(Prediction(
                    package=change.package,
                    confidence=0.50,
                    reasoning="Sub-config files changed → root config/router may need updating to reference new entries",
                    evidence=[f"File in nested config dir: {f}"],
                    expert_name=self.name,
                ))
                break  # Only predict once
        
        return predictions
    
    def _rule_new_import_needs_dep(self, change: Change) -> list[Prediction]:
        """
        If a change introduces usage of a new SDK/library, the Brazil Config
        file needs the dependency.
        
        Derivable from: diff mentions new import + checking if dep exists in Config.
        """
        predictions = []
        
        # Check if intent mentions new SDK/library usage
        sdk_keywords = ["sqs", "sns", "dynamodb", "s3", "lambda", "bedrock",
                       "http client", "new sdk", "new dependency"]
        
        if any(kw in change.intent.lower() for kw in sdk_keywords):
            predictions.append(Prediction(
                package=change.package,
                confidence=0.75,
                reasoning="New SDK usage mentioned → Brazil Config file likely needs dependency addition",
                evidence=["Intent mentions SDK/service that may not be in current Config"],
                expert_name=self.name,
            ))
        
        return predictions
