from __future__ import annotations
"""
judgment-engine/src/experts/file_predictor.py

File-level prediction oracle.

Unlike package-level oracles that just say "Package X needs updating",
this oracle predicts WHICH FILES within a package will need to change.

Strategies:
1. Test file convention: X.java → XTest.java, X.go → X_test.go
2. Config file convention: source code change → Config/build file
3. Same-directory siblings: files in the same dir often co-change
4. Generated file convention: types.go → generated.proto, zz_generated.*
5. Doc file convention: source → website/docs/ or *.md with matching name
"""

import re
from pathlib import PurePosixPath
from ..models import Change, Prediction


class FilePredictor:
    """
    Predicts which specific FILES will need changing based on
    the trigger file(s) and naming/structural conventions.
    """
    
    @property
    def name(self) -> str:
        return "FilePredictor"
    
    def predict(self, change: Change) -> list[Prediction]:
        predictions = []
        
        for trigger_file in change.files_changed:
            predictions += self._predict_for_file(trigger_file, change)
        
        # Deduplicate
        seen = set()
        deduped = []
        for p in predictions:
            key = tuple(p.files)
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        
        return deduped
    
    def _predict_for_file(self, trigger_file: str, change: Change) -> list[Prediction]:
        preds = []
        
        preds += self._rule_test_file(trigger_file, change)
        preds += self._rule_config_file(trigger_file, change)
        preds += self._rule_generated_files(trigger_file, change)
        preds += self._rule_doc_files(trigger_file, change)
        preds += self._rule_same_dir_siblings(trigger_file, change)
        
        return preds
    
    def _rule_test_file(self, trigger_file: str, change: Change) -> list[Prediction]:
        """
        Convention: source file X → test file XTest or X_test exists.
        
        Patterns:
          Java:    Foo.java          → FooTest.java (in tst/ or src/test/)
          Go:      foo.go            → foo_test.go (same dir)
          Python:  foo.py            → test_foo.py (in tests/)
          TS/JS:   foo.ts            → foo.test.ts or foo.spec.ts
        """
        preds = []
        path = PurePosixPath(trigger_file)
        stem = path.stem
        ext = path.suffix
        parent = str(path.parent)
        
        # Skip if trigger IS already a test file
        if self._is_test_file(trigger_file):
            return []
        
        if ext == ".java":
            # Java: src/main/... → src/test/... or tst/...
            test_path = trigger_file.replace("/main/", "/test/").replace(
                f"{stem}.java", f"{stem}Test.java"
            )
            if test_path == trigger_file:
                # Try tst/ convention (Brazil)
                test_path = trigger_file.replace("src/", "tst/").replace(
                    f"{stem}.java", f"{stem}Test.java"
                )
            preds.append(Prediction(
                package=change.package,
                files=[test_path],
                confidence=0.80,
                reasoning=f"Java test convention: {stem}.java → {stem}Test.java",
                evidence=[f"Trigger: {trigger_file}"],
                expert_name=self.name,
            ))
        
        elif ext == ".go":
            # Go: foo.go → foo_test.go (same directory)
            test_path = trigger_file.replace(f"{stem}.go", f"{stem}_test.go")
            preds.append(Prediction(
                package=change.package,
                files=[test_path],
                confidence=0.75,
                reasoning=f"Go test convention: {stem}.go → {stem}_test.go",
                evidence=[f"Trigger: {trigger_file}"],
                expert_name=self.name,
            ))
        
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            # TypeScript/JS: foo.ts → foo.test.ts or foo.spec.ts
            test_path = trigger_file.replace(ext, f".test{ext}")
            spec_path = trigger_file.replace(ext, f".spec{ext}")
            preds.append(Prediction(
                package=change.package,
                files=[test_path],
                confidence=0.65,
                reasoning=f"TS/JS test convention: {stem}{ext} → {stem}.test{ext}",
                evidence=[f"Trigger: {trigger_file}"],
                expert_name=self.name,
            ))
        
        elif ext == ".py":
            # Python: foo.py → test_foo.py or foo_test.py
            test_path_1 = f"{parent}/test_{stem}.py" if parent != "." else f"test_{stem}.py"
            test_path_2 = trigger_file.replace(f"{stem}.py", f"tests/test_{stem}.py")
            preds.append(Prediction(
                package=change.package,
                files=[test_path_1],
                confidence=0.60,
                reasoning=f"Python test convention: {stem}.py → test_{stem}.py",
                evidence=[f"Trigger: {trigger_file}"],
                expert_name=self.name,
            ))
        
        return preds
    
    def _rule_config_file(self, trigger_file: str, change: Change) -> list[Prediction]:
        """
        Convention: adding new imports/dependencies → build config needs updating.
        
        Patterns:
          Brazil: new import → Config file
          npm:    new import → package.json
          Go:     new import → go.mod
          Rust:   new use → Cargo.toml
        """
        preds = []
        ext = PurePosixPath(trigger_file).suffix
        
        # Only predict config change if intent suggests new dependency
        intent_lower = change.intent.lower() if change.intent else ""
        dep_signals = ["new", "add", "import", "depend", "sdk", "client", "library"]
        
        if any(s in intent_lower for s in dep_signals):
            if ext == ".java":
                preds.append(Prediction(
                    package=change.package,
                    files=["Config"],
                    confidence=0.55,
                    reasoning="Java + new dependency signal → Brazil Config may need updating",
                    evidence=[f"Intent mentions: {intent_lower[:50]}"],
                    expert_name=self.name,
                ))
            elif ext in (".ts", ".tsx", ".js"):
                preds.append(Prediction(
                    package=change.package,
                    files=["package.json"],
                    confidence=0.50,
                    reasoning="TS/JS + new dependency signal → package.json may need updating",
                    evidence=[f"Intent: {intent_lower[:50]}"],
                    expert_name=self.name,
                ))
        
        return preds
    
    def _rule_generated_files(self, trigger_file: str, change: Change) -> list[Prediction]:
        """
        Convention: changing a source-of-truth file → generated files need regenerating.
        
        Patterns:
          types.go → generated.proto, zz_generated.deepcopy.go
          *.proto  → generated Go/Java files
          schema   → generated types
        """
        preds = []
        path = PurePosixPath(trigger_file)
        
        if path.name == "types.go" or "types" in path.stem.lower():
            parent = str(path.parent)
            preds.append(Prediction(
                package=change.package,
                files=[f"{parent}/zz_generated.deepcopy.go"],
                confidence=0.80,
                reasoning="types.go change → deepcopy needs regenerating",
                evidence=[f"Trigger: {trigger_file}"],
                expert_name=self.name,
            ))
        
        if path.suffix == ".proto":
            # Proto → generated code in same or adjacent directory
            preds.append(Prediction(
                package=change.package,
                files=[trigger_file.replace(".proto", ".pb.go")],
                confidence=0.70,
                reasoning="Proto change → generated code needs regenerating",
                evidence=[f"Trigger: {trigger_file}"],
                expert_name=self.name,
            ))
        
        return preds
    
    def _rule_doc_files(self, trigger_file: str, change: Change) -> list[Prediction]:
        """
        Convention: resource/endpoint changes → docs need updating.
        
        Patterns:
          Terraform: internal/service/X/resource.go → website/docs/r/X.html.markdown
          General:   feature change → docs/X.md
        """
        preds = []
        path = PurePosixPath(trigger_file)
        
        # Terraform provider pattern
        if "internal/service/" in trigger_file and trigger_file.endswith(".go"):
            # Extract service and resource name
            parts = trigger_file.split("/")
            if len(parts) >= 4:
                service = parts[2] if "internal" in parts[0] else parts[3]
                resource = path.stem
                doc_path = f"website/docs/r/{resource}.html.markdown"
                preds.append(Prediction(
                    package=change.package,
                    files=[doc_path],
                    confidence=0.60,
                    reasoning=f"Terraform resource change → docs need updating",
                    evidence=[f"Resource file: {trigger_file}"],
                    expert_name=self.name,
                ))
        
        return preds
    
    def _rule_same_dir_siblings(self, trigger_file: str, change: Change) -> list[Prediction]:
        """
        Convention: files in the same directory with related names often co-change.
        
        Patterns:
          FooConfig.java + FooManager.java + FooUtils.java (service trio)
          resource.go + resource_test.go + datasource.go (Terraform)
        """
        # This is weaker — only fires if we can identify a naming pattern
        # For now, skip (avoid too many false positives)
        return []
    
    def _is_test_file(self, filepath: str) -> bool:
        """Check if a file is already a test file."""
        lower = filepath.lower()
        return any(p in lower for p in [
            "test", "spec", "_test.", "tst/", "/test/", "/tests/"
        ])
