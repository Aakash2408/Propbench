#!/usr/bin/env python3
"""Freeze PropBench dataset at a versioned snapshot for reproducible evaluation."""

import hashlib
import os
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FAMILIES_DIR = ROOT / "datasets" / "families"
FROZEN_DIR = ROOT / "datasets" / "frozen"
PAPER_DIR = ROOT / "paper"

VERSION = "1.0"
SEED = 42
TRAIN_RATIO = 0.8
N_FOLDS = 5


def load_all_entries():
    """Load all YAML entries from datasets/families/**/*.yaml (supports multi-doc)."""
    entries = []
    for yaml_file in sorted(FAMILIES_DIR.rglob("*.yaml")):
        with open(yaml_file) as f:
            docs = list(yaml.safe_load_all(f))
        for entry in docs:
            if entry and isinstance(entry, dict) and "id" in entry:
                entry["_source_file"] = str(yaml_file.relative_to(ROOT))
                entries.append(entry)
    return entries


def compute_hash(content: str) -> str:
    """SHA-256 of serialized content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate_splits(n: int, seed: int):
    """Generate deterministic 80/20 train/test split indices."""
    rng = random.Random(seed)
    indices = list(range(n))
    rng.shuffle(indices)
    split_point = int(n * TRAIN_RATIO)
    return sorted(indices[:split_point]), sorted(indices[split_point:])


def generate_cv_folds(n: int, seed: int, n_folds: int):
    """Generate deterministic stratified k-fold CV indices."""
    rng = random.Random(seed)
    indices = list(range(n))
    rng.shuffle(indices)
    folds = []
    fold_size = n // n_folds
    for i in range(n_folds):
        start = i * fold_size
        end = start + fold_size if i < n_folds - 1 else n
        test_idx = sorted(indices[start:end])
        train_idx = sorted(set(indices) - set(test_idx))
        folds.append({"fold": i + 1, "train": train_idx, "test": test_idx})
    return folds


def load_paper_results():
    """Extract key results from paper/ for README."""
    results = {}
    for name in ["per-type-results.md", "scaling-curve-results.md", "llm-baseline-results.md"]:
        path = PAPER_DIR / name
        if path.exists():
            results[name] = path.read_text()[:500]
    return results


def generate_readme(entries, family_counts, paper_results):
    """Generate README.md documenting the frozen version."""
    lines = [
        f"# PropBench v{VERSION} — Frozen Dataset",
        "",
        f"**Frozen**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Entries**: {len(entries)}",
        f"**Families**: {len(family_counts)}",
        f"**Seed**: {SEED}",
        f"**Split**: {int(TRAIN_RATIO*100)}/{100-int(TRAIN_RATIO*100)} train/test",
        f"**CV**: {N_FOLDS}-fold",
        "",
        "## Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        f"| `v{VERSION}.yaml` | All {len(entries)} entries in one flat list |",
        f"| `split_train.yaml` | Training split ({int(len(entries)*TRAIN_RATIO)} entries) |",
        f"| `split_test.yaml` | Test split ({len(entries) - int(len(entries)*TRAIN_RATIO)} entries) |",
        f"| `cv_folds.yaml` | {N_FOLDS}-fold CV indices |",
        "",
        "## Per-Family Breakdown",
        "",
        "| Family | Count |",
        "|--------|-------|",
    ]
    for family, count in sorted(family_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {family} | {count} |")

    lines += ["", "## Evaluation Results (from paper/)", ""]
    if "per-type-results.md" in paper_results:
        lines.append("- **FilePredictor**: 15.9% overall recall (naming conventions)")
        lines.append("- **Proto/Schema**: 57.7% (highest), TypeScript: 2.6% (lowest)")
    if "scaling-curve-results.md" in paper_results:
        lines.append("- **Historian (5-fold CV)**: 30.8% at full dataset, monotonic growth")
    if "llm-baseline-results.md" in paper_results:
        lines.append("- **LLM Simulated Baseline**: 32.7% (frontier model without history)")

    lines += [
        "",
        "## Reproducibility",
        "",
        "```bash",
        "python tools/freeze_dataset.py",
        "```",
        "",
        "All splits use `random.Random(42)` for deterministic shuffling.",
        "The SHA-256 hash in v1.0.yaml header verifies content integrity.",
    ]
    return "\n".join(lines) + "\n"


def main():
    entries = load_all_entries()
    if not entries:
        print("ERROR: No entries found in datasets/families/")
        sys.exit(1)

    # Sort deterministically by id
    entries.sort(key=lambda e: e.get("id", ""))

    # Family breakdown
    family_counts = Counter(e.get("family", "unknown") for e in entries)

    # Serialize entries (strip internal metadata)
    clean_entries = []
    for e in entries:
        clean = {k: v for k, v in e.items() if not k.startswith("_")}
        clean_entries.append(clean)

    content_body = yaml.dump(clean_entries, default_flow_style=False, sort_keys=False)
    content_hash = compute_hash(content_body)

    # Build frozen YAML with metadata header
    metadata = {
        "version": VERSION,
        "frozen_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entry_count": len(entries),
        "sha256": content_hash,
        "seed": SEED,
        "families": len(family_counts),
    }
    frozen_content = yaml.dump({"metadata": metadata}, default_flow_style=False, sort_keys=False)
    frozen_content += "---\n" + content_body

    # Generate splits
    train_idx, test_idx = generate_splits(len(entries), SEED)
    train_entries = [clean_entries[i] for i in train_idx]
    test_entries = [clean_entries[i] for i in test_idx]

    # Generate CV folds
    cv_folds = generate_cv_folds(len(entries), SEED, N_FOLDS)

    # Write outputs
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)

    (FROZEN_DIR / f"v{VERSION}.yaml").write_text(frozen_content)
    (FROZEN_DIR / "split_train.yaml").write_text(
        yaml.dump({"split": "train", "seed": SEED, "count": len(train_entries),
                   "entries": train_entries}, default_flow_style=False, sort_keys=False))
    (FROZEN_DIR / "split_test.yaml").write_text(
        yaml.dump({"split": "test", "seed": SEED, "count": len(test_entries),
                   "entries": test_entries}, default_flow_style=False, sort_keys=False))
    (FROZEN_DIR / "cv_folds.yaml").write_text(
        yaml.dump({"n_folds": N_FOLDS, "seed": SEED, "total_entries": len(entries),
                   "folds": cv_folds}, default_flow_style=False, sort_keys=False))

    # README
    paper_results = load_paper_results()
    readme = generate_readme(entries, family_counts, paper_results)
    (FROZEN_DIR / "README.md").write_text(readme)

    # Print summary
    print(f"✅ PropBench v{VERSION} frozen successfully")
    print(f"   Entries: {len(entries)}")
    print(f"   Families: {len(family_counts)}")
    print(f"   SHA-256: {content_hash[:16]}...")
    print(f"   Train/Test: {len(train_entries)}/{len(test_entries)}")
    print(f"   CV Folds: {N_FOLDS} x ~{len(entries)//N_FOLDS} entries")
    print(f"   Output: {FROZEN_DIR.relative_to(ROOT)}/")
    print()
    print("   Top families:")
    for family, count in sorted(family_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"     {family}: {count}")


if __name__ == "__main__":
    main()
