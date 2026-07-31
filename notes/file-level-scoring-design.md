# File-Level Scoring Design

## The Problem

Package-level scoring works for Amazon (multi-package ecosystem) but fails
for monorepos (K8s, Terraform) where all consequences are in the same package.

## Solution: Two scoring modes

Each dataset entry declares its `propagation_unit`:

```yaml
propagation_unit: "package"   # Amazon-style: predict WHICH PACKAGE
propagation_unit: "file"      # Monorepo-style: predict WHICH FILE
```

The benchmark scores each entry using its declared unit.

## Scoring Rules

### Package-level (default, backward compatible)

```
Predicted: ["GAMCoreModel", "AteamIntegrationTests"]
Actual:    ["GAMCoreModel", "AteamIntegrationTests"]

Match on: package name
Precision: 2/2 = 100%
Recall:    2/2 = 100%
```

### File-level

```
Predicted: ["validation.go", "validation_test.go", "generated.proto"]
Actual:    ["validation.go", "validation_test.go", "generated.proto", 
            "zz_generated.deepcopy.go", "controller.go", "e2e_test.go", "swagger.json"]

Match on: file path (or file basename if paths differ)
Precision: 3/3 = 100%
Recall:    3/7 = 43%
```

### Mixed (package+file)

For entries where some consequences are cross-package and some are intra-package:

```yaml
consequences:
  - package: "GAMCoreModel"           # scored at package level
    files: ["SourceConfiguration.prototxt"]  # file info for analysis only
  - package: "SamePackage"            # if same as trigger, score at FILE level
    files: ["Config"]
```

Rule: If consequence.package == trigger.package, score at file level.
Otherwise score at package level.

## Implementation Changes

### models.py

```python
@dataclass
class Prediction:
    package: str
    files: list[str]        # NEW: predicted files (optional for package-level)
    confidence: float
    reasoning: str
    evidence: list[str]
    expert_name: str

@dataclass
class ReplayResult:
    # ... existing fields ...
    
    def compute_metrics(self):
        # Determine scoring mode per consequence
        for consequence in self.actual:
            if consequence.package == self.change.package:
                # Same package → file-level scoring
                self._score_file_level(consequence)
            else:
                # Cross-package → package-level scoring (existing)
                self._score_package_level(consequence)
```

### What oracles need to change

Currently oracles return:
```python
Prediction(package="GAMCoreModel", files=[], ...)
```

For file-level scoring, they need to also predict files:
```python
Prediction(package="kubernetes/kubernetes", 
           files=["pkg/apis/apps/validation/validation.go"], ...)
```

This means:
- PatternOracle playbooks should include predicted FILE PATHS (not just packages)
- StructureOracle rules should predict specific files based on naming conventions

### Phased rollout

Phase 1 (now): Add `propagation_unit` to dataset entries. Score existing entries
at package level (backward compatible). File predictions in oracles are optional.

Phase 2 (when OSS entries have real data): Implement file-level scoring for entries
marked `propagation_unit: file`. Require oracles to return file predictions.

Phase 3 (mature): Report both package-level and file-level metrics separately
in the leaderboard.

## Example: How StructureOracle would predict files

```python
def _rule_naming_convention(self, change: Change) -> list[Prediction]:
    """
    If trigger file is X.go, predict X_test.go exists and needs updating.
    If trigger file is types.go, predict generated.proto, zz_generated.deepcopy.go.
    """
    for f in change.files_changed:
        base = f.rsplit('.', 1)[0]
        ext = f.rsplit('.', 1)[1] if '.' in f else ''
        
        # Go test file convention
        if ext == 'go' and not f.endswith('_test.go'):
            predictions.append(Prediction(
                package=change.package,
                files=[f"{base}_test.go"],
                confidence=0.70,
                ...
            ))
        
        # K8s types.go → generated files
        if f.endswith('types.go'):
            predictions.append(Prediction(
                package=change.package,
                files=["generated.proto", "zz_generated.deepcopy.go"],
                confidence=0.85,
                ...
            ))
```

## Metrics at file level

```
PropBench Leaderboard (mixed scoring)

Oracle          | Pkg-P | Pkg-R | File-P | File-R | Combined
----------------|-------|-------|--------|--------|----------
Ensemble(P+S)   |  74%  |  82%  |   ?    |   ?    |    ?
PatternOracle    |  85%  |  55%  |   ?    |   ?    |    ?
StructureOracle  |  55%  |  55%  |   ?    |   ?    |    ?
```

## Why this matters

File-level scoring is:
- Required to evaluate OSS/monorepo performance honestly
- A harder challenge (more precise predictions needed)
- Closer to what a real product would need ("update THIS file" not just "check this package")
- The difference between a research benchmark and a useful tool

## Timeline

- This week: Add `propagation_unit` field to new entries
- Next sprint: Implement file-level scoring in benchmark.py
- After 10+ OSS replay entries: Report file-level metrics
