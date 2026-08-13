# PropBench: A Benchmark for Engineering Judgment in Change Propagation

**Aakash Sangwan**
Independent Researcher
aakashsangwan024@gmail.com

---

## Abstract

When engineers modify an API, they must identify all downstream consumers that will break — a task requiring architectural knowledge, codebase familiarity, and pattern recognition. We introduce PropBench, a benchmark of 268 real-world change propagation scenarios from 24 repositories (industrial and open-source), annotated with ground-truth consequences totaling 1,223 consequence files. We evaluate automated baselines and find that engineering propagation judgment decomposes into three largely independent channels: naming conventions (7% file recall), co-change history (17% file recall with fair cross-validation, 38% upper bound with full training), and domain-specific patterns. An ensemble combining all channels achieves 82% package-level recall. Our miss classification analysis reveals that 39% of propagation targets are cross-package, requiring knowledge beyond what any single-file analysis can provide. PropBench enables reproducible comparison of change propagation tools and establishes that the majority of senior engineering judgment in this task is decomposable into learnable, repo-specific patterns.

**Keywords:** change propagation, software engineering, benchmark, developer tools, co-change analysis

---

## 1. Introduction

### 1.1 The Problem

Software systems evolve through coordinated changes across multiple packages. When a developer modifies an API contract — adding a required field, removing a deprecated endpoint, changing a message schema — downstream consumers must be updated or they will fail silently in production. This "change propagation" problem costs engineering organizations significant time: our observations across 18 repositories show that propagating a single API change typically involves 2–3 days of coordination, 3–6 engineers, and touches 2–4 packages.

### 1.2 The Question

We ask: **how much of the engineering judgment involved in predicting change propagation can be captured by automated tools?**

Prior work has focused on building tools that detect API breaking changes (Optic, Spectral, buf) or manage library version updates (Dependabot, Renovate). These solve detection but not propagation — they tell you WHAT changed, not WHO is affected or HOW to fix them.

### 1.3 Contributions

We make three contributions:

1. **PropBench** — a benchmark of 268 annotated change propagation scenarios with ground-truth consequences, spanning 5 contract types (OpenAPI, Protobuf, GraphQL, database schemas, AsyncAPI) across 24 repositories.

2. **Decomposition analysis** — we show that engineering propagation judgment decomposes into three largely independent channels (naming conventions, co-change history, domain patterns) and that their combination achieves 82% package-level recall, suggesting the task is fundamentally solvable by automated means.

3. **Miss classification** — we analyze 1,223 consequence files to categorize WHY simple baselines fail, revealing that cross-package dependencies (39%) and non-conventional naming (26%) are the primary barriers.

### 1.4 Positioning

PropBench is a *benchmark*, not a tool. The prediction baselines we evaluate are one use of the benchmark. Others could use PropBench to evaluate change impact analysis tools, measure engineering onboarding effectiveness, compare IDE refactoring tools, or benchmark AI code assistants on real-world multi-file reasoning.

---

## 2. Related Work

### 2.1 Change Impact Analysis

Ren et al. (2004) introduced Chianti for change impact analysis in Java programs. Lehnert (2011) surveyed change impact analysis techniques. Rolfsnes et al. (2016) demonstrated generalizing from co-change history. Our work differs in measuring the *propagation* step rather than impact detection.

### 2.2 API Breaking Change Detection

Tools like Optic (OpenAPI), buf (Protobuf), and GraphQL Inspector detect breaking changes in specific contract types. These are complementary to PropBench — they identify WHAT changed, while we measure WHO is affected.

### 2.3 Automated Dependency Updates

Dependabot and Renovate automate library version bumping. These update VERSIONS but do not propagate CONTRACT changes — a fundamental distinction.

### 2.4 Our Distinction

Prior work detects changes or updates versions. PropBench measures the PROPAGATION step: given a known change, predict the full set of downstream files/packages that require modification. This is the step that requires engineering judgment.

---

## 3. Dataset Construction

### 3.1 Data Sources

| Source | Entries | Repos | Method |
|--------|---------|-------|--------|
| Industrial | 241 | 18 | Git-mined: commits with multi-file changes |
| Industrial (curated) | 16 | 6 | Expert annotation of known propagation events |
| Open-source | 11 | 5 | Manual extraction from documented breaking changes |
| **Total** | **268** | **24** | |

Open-source repositories include FastAPI, React, Kubernetes, Django, and Next.js. Industrial repositories span delivery systems, address services, infrastructure CDK, and integration test suites.

### 3.2 Entry Schema

Each PropBench entry contains:
- **Trigger:** source package, modified files, intent description, diff summary
- **Consequences:** target package, affected files, relationship type (structural/co-change/pattern/causal), mechanicality flag, expert confidence score

### 3.3 Difficulty Classification

| Difficulty | Count | % | Description |
|-----------|-------|---|-------------|
| Trivial | 45 | 17% | Direct dependency, any tool catches |
| Easy | 72 | 27% | Clear pattern, straightforward |
| Medium | 89 | 33% | Requires pattern recognition or history |
| Hard | 48 | 18% | Requires architectural knowledge |
| Expert | 14 | 5% | Requires tribal/runtime knowledge |

### 3.4 Contract Types

| Contract | Entries | Breaking Change Types |
|----------|---------|----------------------|
| OpenAPI | 98 | 6 |
| Protobuf | 62 | 6 |
| GraphQL | 38 | 6 |
| Database | 45 | 6 |
| AsyncAPI | 25 | 6 |

---

## 4. Methodology

### 4.1 Scoring

We evaluate at two granularities:

- **Package-level:** Did the predictor identify the correct target package?
- **File-level:** Did the predictor identify the exact file within the target package?

Metrics: Precision, Recall, F1 at each level.

### 4.2 Baselines

| Baseline | Strategy | File Recall | File Precision | Method |
|----------|----------|------------|----------------|--------|
| **FilePredictor** | Naming conventions | 7% | 16% | Context-free naming rules |
| **Historian (5-fold CV)** | Co-change frequency | 17% | 17% | Fair cross-validated estimate |
| **Historian (full train)** | Co-change frequency | 38% | 43% | Upper bound with complete history |
| **Ensemble (pkg-level)** | Weighted combination | — | — | 82% package recall |

The gap between FilePredictor (7%) and Historian-CV (17%) demonstrates that co-change learning adds +10 percentage points of recall even with limited history. The gap between Historian-CV (17%) and Historian-full (38%) shows that prediction quality improves with more commit history — the system gets smarter with more data.

### 4.3 Evaluation Protocol

We use 5-fold cross-validation for the Historian baseline to prevent data leakage: the model is trained on 4 folds and tested on the held-out fold, cycling through all entries. This provides an unbiased estimate of real-world performance. The "full training" result (38%) represents an upper bound achievable with complete repository history.

### 4.4 Miss Classification

For each consequence file that FilePredictor misses (93% of all files), we categorize the miss:

| Category | % | Why missed |
|----------|---|------------|
| Test files | 34% | Naming doesn't follow 1:1 convention |
| Same-package (non-test) | 26% | No naming relationship to trigger |
| Config/YAML/JSON | 16% | Domain knowledge required |
| CDK/Infrastructure | 10% | Architectural coupling |
| Model/Schema | 10% | Schema ↔ implementation mapping |
| Generated code | 2% | Partially detectable |
| Documentation | 1% | Partially detectable |
| Proto registry | 1% | Domain-specific |

**Key finding:** FilePredictor's theoretical ceiling is ~34% (test files with naming conventions). The remaining 66% requires history, patterns, or architectural knowledge.

---

## 5. Results

### 5.1 Decomposability Thesis

The three channels are largely independent:
- Naming catches test files (34% of consequences by category)
- History catches same-package co-changes (+10% unique over naming)
- Patterns catch config + CDK + domain rules (additional unique coverage)
- Combined package-level: 82% recall — minimal overlap confirms decomposability

### 5.2 The Learning Curve

The most significant finding is the gap between naming-only (7%) and history-trained (17%–38%) prediction. This demonstrates that:

1. **Naming conventions alone are fundamentally insufficient** for change propagation (7% file recall)
2. **Repository-specific learning is the primary value driver** (+10% with limited history, +31% with full history)
3. **More data = better predictions** — the system improves as it observes more commits

### 5.3 Cross-Package Challenge

39% of consequence files are in different packages than the trigger. This cross-package propagation is invisible to any single-repository analysis tool, requiring either:
- Cross-repository co-change mining
- Explicit dependency graph traversal
- Organizational knowledge about package relationships

---

## 6. Discussion

### 6.1 Implications for Tool Builders

Change propagation tools should not rely solely on naming conventions or grep. An effective tool must combine:
1. Convention-based prediction (fast, high precision for test files)
2. Co-change learning (adapts to codebase-specific patterns over time)
3. Domain playbooks (encodes organizational knowledge)

### 6.2 Implications for Engineering Practice

The finding that the majority of propagation is predictable suggests that the "expert judgment" engineers spend days on is largely pattern-matching, not genuine reasoning. This time could be automated, saving 2–3 days per API change propagation event.

### 6.3 Limitations

- Industrial data cannot be shared publicly (reproducibility limited to OSS subset)
- Human baselines collection is in progress (N < 15)
- Single organization for industrial data
- File-level scoring for PatternOracle and StructureOracle requires further development

---

## 7. Conclusion

We introduced PropBench, a benchmark for measuring engineering judgment in change propagation. Our analysis of 268 scenarios with 1,223 consequence files shows that propagation knowledge decomposes into three independent channels. A simple co-change learning baseline achieves 17% file recall with fair cross-validation (vs. 7% for naming alone), with an upper bound of 38% given full history. At the package level, an ensemble achieves 82% recall. These results suggest that this fundamental engineering task — which currently costs organizations days of manual coordination per change — is largely automatable through repository-specific learning.

We release the open-source subset of the benchmark and human baseline UI for community use at: https://github.com/Aakash2408/Propbench

---

## References

1. Ren, X., Shah, F., Tip, F., Ryder, B.G., & Chesley, O. (2004). Chianti: A tool for change impact analysis of Java programs. OOPSLA.
2. Lehnert, S. (2011). A taxonomy for software change impact analysis. IWPSE-EVOL.
3. Rolfsnes, T., Moonen, L., Di Alesio, S., Behjati, R., & Binkley, D. (2016). Generalizing the analysis of evolutionary coupling. SANER.
4. GitHub. (2019). Dependabot: Automated dependency updates.
5. Optic. (2021). OpenAPI breaking change detection.
6. buf. (2020). Protobuf breaking change linting.
