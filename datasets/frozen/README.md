# PropBench v1.0 — Frozen Dataset

**Frozen**: 2026-08-13 11:08 UTC
**Entries**: 481
**Families**: 18
**Seed**: 42
**Split**: 80/20 train/test
**CV**: 5-fold

## Files

| File | Description |
|------|-------------|
| `v1.0.yaml` | All 481 entries in one flat list |
| `split_train.yaml` | Training split (384 entries) |
| `split_test.yaml` | Test split (97 entries) |
| `cv_folds.yaml` | 5-fold CV indices |

## Per-Family Breakdown

| Family | Count |
|--------|-------|
| uncategorized | 147 |
| configuration-evolution | 79 |
| interface-evolution | 71 |
| bugfix | 63 |
| test-evolution | 36 |
| refactor | 34 |
| dependency-evolution | 18 |
| infrastructure-evolution | 11 |
| aas-onboarding | 3 |
| oss-fastapi | 3 |
| cdk-infrastructure | 2 |
| config-changes | 2 |
| country-expansion | 2 |
| integration-tests | 2 |
| oss-django | 2 |
| oss-kubernetes | 2 |
| oss-nextjs | 2 |
| oss-react | 2 |

## Evaluation Results (from paper/)

- **FilePredictor**: 15.9% overall recall (naming conventions)
- **Proto/Schema**: 57.7% (highest), TypeScript: 2.6% (lowest)
- **Historian (5-fold CV)**: 30.8% at full dataset, monotonic growth
- **LLM Simulated Baseline**: 32.7% (frontier model without history)

## Reproducibility

```bash
python tools/freeze_dataset.py
```

All splits use `random.Random(42)` for deterministic shuffling.
The SHA-256 hash in v1.0.yaml header verifies content integrity.
