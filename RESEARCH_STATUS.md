# PropBench: A Benchmark for Engineering Change Propagation

## Research Status — July 28, 2026

---

### Position Statement

> We introduce PropBench, a benchmark for measuring engineering judgment
> in change propagation. The prediction engine is one baseline evaluated
> on the benchmark — not the primary contribution.

---

### Dataset (v0.2)

```
Total entries:       272
Hand-curated:         16
Amazon (git-mined):  241  (18 repositories, 15+ engineers)
OSS (GitHub API):     15  (terraform-provider-aws)

Time span:           Jan 2025 — Jul 2026
Unique authors:      15+
Repositories:        19

Label quality:       UNKNOWN (needs manual sample validation)
Noise estimate:      UNKNOWN (needs audit of 30 random entries)
```

### Scoring

```
Package-level:   Implemented (trivially high on single-repo data — 95%)
File-level:      Designed, NOT YET IMPLEMENTED (the real benchmark)
```

### Current Baselines (on 16 hand-curated entries only)

```
Ensemble (Pattern + Structure):  P=76%  R=81%
PatternOracle:                   P=90%  R=44%
StructureOracle:                 P=62%  R=62%
SamePackage (trivial baseline):  P=62%  R=69%
```

Note: Baselines are only meaningful on hand-curated entries with cross-package
consequences. The 241 mined entries require file-level scoring to produce
non-trivial results.

---

### What's Established

1. Engineering propagation judgment decomposes into separable channels
2. Pattern + Structure are 67% independent and together reach 81% recall
3. Difficult cases cluster around architectural/intent knowledge
4. Software can catch hidden dependencies experts miss (1 confirmed case)
5. Dataset scales automatically via git mining

### What's NOT Established

1. File-level prediction accuracy (scoring not implemented)
2. Label quality of mined entries (needs manual audit)
3. Cross-ecosystem generalization (only 15 OSS entries, rate-limited)
4. Human baselines (no recorded predictions from colleagues)
5. Whether the 81% holds at scale on mined data

---

### Next Steps (in priority order)

| # | Action | Why |
|---|--------|-----|
| 1 | Implement file-level scoring | Without it, 241 mined entries are unusable |
| 2 | Sample 30 mined entries, manually validate | Measure noise rate |
| 3 | Mine more OSS (with GITHUB_TOKEN) | K8s, FastAPI, Next.js |
| 4 | Human baseline: record 2-3 colleagues' blind predictions | Context for numbers |
| 5 | Freeze PropBench v1.0 | Stable benchmark others could run |

---

### Tools Built

```
tools/git_miner.py        Mine local git repos (any language/framework)
tools/github_miner.py     Mine GitHub PRs via API (rate-limited without token)
src/experts/              4 baselines + 2 oracles + 1 ensemble
src/benchmark.py          Loader, runner, leaderboard formatter
src/cli.py               Sacred benchmark command
```

---

### Paper Framing (aspirational)

> "We introduce PropBench, a benchmark of 272 engineering change propagations
> automatically mined from 19 production repositories spanning 15+ engineers.
> We evaluate pattern-based and structure-based predictors, finding that their
> combination achieves 81% recall on curated entries, with difficult cases
> concentrating in architectural and intent-based reasoning. We release the
> mining tools and benchmark for community evaluation."

---

### Project Structure (Three Artifacts)

```
1. PropBench (benchmark)       <- PRIMARY CONTRIBUTION
   The dataset + scoring + mining tools

2. Judgment Engine (system)    <- ONE BASELINE
   Pattern + Structure + Ensemble predictors

3. PropagateBot (product)      <- FUTURE APPLICATION
   GitHub App powered by the engine
```
