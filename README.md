# judgment-engine

## PropBench v0.1 — A Benchmark for Engineering Judgment

### Claim (precise, reproducible)

> On a benchmark of 11 real engineering changes across 5 families,
> an ensemble using organizational patterns + static code structure
> achieved **82% recall** and **74% precision**.

### What this does NOT yet prove

- That 82% generalizes to other codebases
- That 82% holds at n=50
- That this is better or worse than a mid-level engineer
- That the knowledge decomposition (Pattern vs Structure) is universal

### What it DOES prove

- Engineering judgment decomposes into at least two measurably independent channels
- Those channels (organizational memory + structural analysis) are 67% independent
- Their union significantly outperforms either alone
- Software can catch dependencies that human experts miss (1 confirmed case)

---

### Current Results (v0.1, frozen)

```
Dataset:          11 entries, 5 families
Engine version:   v0.1 (frozen — do not optimize further until n≥30)

╔═══════════════════════════════════════════════════════╗
║  Oracle               P      R    Top1   Cov         ║
╠═══════════════════════════════════════════════════════╣
║  Ensemble(P+S)        74%    82%   73%   91%          ║
║  PatternExpert        85%    55%   55%   64%          ║
║  StructureOracle      55%    55%   45%   91%          ║
║  SamePackage (base)   55%    64%   55%  100%          ║
║  DirectDeps (base)   100%    21%   36%   27%          ║
╚═══════════════════════════════════════════════════════╝
```

### Knowledge Channel Decomposition

```
                 ENGINEERING JUDGMENT
                        100%
                          │
             ┌────────────┴────────────┐
         Explained                 Unexplained
             82%                       18%
       ┌──────┴──────┐                  │
    Pattern      Structure          Needs:
      55%           55%             • History?
           Overlap: 27%             • Runtime?
                                    • Intent?
```

### Next Steps (benchmark quality, not engine quality)

1. ⬜ Grow dataset to 30-50 entries (diverse: bug fixes, refactors, deps, IAM, proto, CI/CD)
2. ⬜ Add entries from teammates (not just my own changes)
3. ⬜ Add human baselines (junior / mid / senior predictions)
4. ⬜ Confidence calibration (does 90% confidence mean 90% correct?)
5. ⬜ Per-family stability analysis (does each family hold with more examples?)
6. ⬜ Only then: test Historian (does git history add signal beyond 82%?)

### Running

```bash
cd judgment-engine
python3.10 -m src.cli        # leaderboard
python3.10 -m src.cli -v     # per-entry detail
```

### File Structure

```
judgment-engine/
├── README.md              # This file
├── PRODUCT.md             # GitHub App product spec
├── LANDING.md             # Landing page copy
├── PLATFORM.md            # 18-month expansion roadmap
├── VERIFICATION.md        # Pass/fail criteria + kill conditions
├── THIS_WEEK.md           # Immediate action items
├── pyproject.toml
├── src/
│   ├── cli.py             # Sacred benchmark command
│   ├── benchmark.py       # Dataset loader + runner
│   ├── models.py          # Core data structures
│   └── experts/
│       ├── baselines.py   # NullExpert, SamePackage, DirectDeps, AlwaysGAM
│       ├── pattern_expert.py   # 5 playbooks (PatternOracle)
│       ├── structure_expert.py # 5 structural rules (StructureOracle)
│       └── ensemble.py    # Simple union (P+S)
└── datasets/
    ├── README.md          # Schema + philosophy
    └── families/          # 11 entries across 5 families
```

### Design Philosophy

> Build software that captures expert judgment and makes it available on demand.

### Hypothesis (falsifiable)

Software can predict the consequences of code changes with accuracy
comparable to a senior engineer. If this hypothesis is false after
testing on 50 diverse entries, this project should not continue.
