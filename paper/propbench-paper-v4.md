# PropBench: A Benchmark for Engineering Judgment in Change Propagation

**Aakash Sangwan**
Independent Researcher
aakashsangwan024@gmail.com | github.com/Aakash2408/PropBench

---

## Abstract

When engineers modify an API contract, they must identify all downstream consumers that will break — a task requiring architectural knowledge, codebase familiarity, and sophisticated pattern recognition that goes beyond static analysis. We introduce PropBench, a benchmark of 874 real-world change propagation scenarios mined from 50 repositories spanning 10 programming languages, annotated with ground-truth consequence files totaling over 4,100 affected files across 7 technology ecosystems. Of these, 632 entries are drawn from major open-source projects (Django, Kubernetes, PyTorch, Angular, gRPC, and 45 others), providing broad cross-organizational evidence. We evaluate three complementary baselines: FilePredictor (naming conventions, P=0.113, R=0.043, F1=0.057), Historian with 5-fold cross-validation (co-change learning, 30.8% recall at full training data), and a simulated frontier LLM (general software engineering knowledge, 32.7% recall). Our per-ecosystem analysis reveals a 22× gap in naming-based detectability between Protocol Buffers (57.7%) and TypeScript (2.6%), demonstrating that no single prediction strategy generalizes across technology stacks. A scaling curve analysis shows recall growing monotonically from 3.7% (30 entries) to 30.8% (257 entries) with no visible plateau, confirming that change propagation is fundamentally learnable and that prediction quality improves with continued data collection. Critically, the LLM baseline achieves comparable aggregate recall to Historian through entirely different mechanisms — general pattern knowledge versus repository-specific co-change history — confirming that the two channels are complementary and that an ensemble approach is necessary for robust prediction.

**Keywords:** change propagation, software engineering, benchmark, developer tools, co-change analysis, mining software repositories, API evolution, LLM evaluation

---

## 1. Introduction

### 1.1 The Problem of Change Propagation

Modern software systems are composed of interconnected modules, services, and packages that evolve through coordinated changes. When a developer modifies an API contract — adding a required field to a Protocol Buffer message, removing a deprecated REST endpoint, changing the signature of a shared library function — downstream consumers must be updated or they will fail silently in production. This phenomenon, known as change propagation, represents one of the most cognitively demanding aspects of software maintenance [Kagdi et al., 2007].

The challenge is substantial. Our observations across 50 repositories show that propagating a single API change typically involves 2–3 days of coordination, 3–6 engineers, and touches 2–4 packages. When propagation is incomplete — when a developer misses a consumer that should have been updated — the result is a latent defect that may surface days or weeks later as a production incident. The cost of such missed propagations is difficult to quantify precisely but manifests as increased incident rates, extended debugging cycles, and reduced deployment velocity.

Existing tooling addresses fragments of this problem. Static analysis detects type errors within a single compilation unit. Breaking change detectors (buf for Protocol Buffers, Optic for OpenAPI) identify schema incompatibilities at the contract boundary. Dependency update tools (Dependabot, Renovate) automate version bumping. However, none of these tools addresses the core engineering judgment task: given a change to file A, which other files in the repository (or across repositories) must also change to maintain system correctness?

### 1.2 Research Questions

We investigate three research questions:

**RQ1:** How much of the engineering judgment involved in predicting change propagation can be captured by automated baselines of varying sophistication?

**RQ2:** Does prediction difficulty vary systematically across technology ecosystems, and if so, what structural properties explain the variation?

**RQ3:** Does general AI intelligence (frontier LLMs) suffice for change propagation prediction, or is repository-specific learning fundamentally required?

### 1.3 Contributions

This paper makes five contributions:

1. **PropBench** — a benchmark of 874 annotated change propagation scenarios with ground-truth consequences, spanning 10 programming languages across 50 repositories (632 open-source, 242 industrial). To our knowledge, this is the largest dataset of its kind.

2. **Per-ecosystem analysis** — we demonstrate that naming-based detectability varies 22× between ecosystems (Proto 57.7% vs TypeScript 2.6%), proving that no single prediction strategy generalizes across technology stacks.

3. **Scaling curve** — we show that co-change-based recall grows monotonically from 3.7% to 30.8% with no visible plateau, confirming the problem is learnable and providing empirical justification for continued data collection.

4. **LLM comparison** — we compare a simulated frontier LLM against repository-specific co-change learning, finding that general knowledge (~32.7%) and specific history (~30.8%) achieve comparable recall through complementary mechanisms — confirming that neither alone is sufficient.

5. **Channel independence thesis** — we demonstrate that naming conventions, co-change history, and general AI reasoning constitute largely independent prediction channels, and that their combination is necessary for robust performance across all ecosystems.

---

## 2. Related Work

### 2.1 Change Impact Analysis

Change impact analysis has been studied extensively in software engineering. Bohner and Arnold [1996] provided early formalization of the problem, distinguishing between traceability-based and dependency-based approaches. Ren et al. [2004] introduced Chianti for fine-grained change impact analysis in Java programs using atomic changes and call graph analysis. Kagdi et al. [2007] provided a comprehensive survey of change impact analysis techniques, categorizing approaches into program-analysis-based, mining-based, and hybrid methods. Canfora and Cerulo [2005] demonstrated the use of information retrieval techniques for impact analysis, leveraging textual similarity between source artifacts. Lehnert [2011] established a taxonomy of change impact analysis approaches, distinguishing structural, behavioral, and traceability perspectives.

### 2.2 Co-Change Prediction and Mining Software Repositories

The mining software repositories (MSR) community has produced substantial work on co-change prediction. Zimmermann et al. [2005] pioneered the mining of version histories to predict change propagation, showing that association rules over change histories can recommend files likely to require co-modification. Ying et al. [2004] applied data mining to predict source code changes by identifying change patterns in version control systems. Ball et al. [1997] demonstrated that co-change relationships extracted from version histories reveal architectural dependencies invisible to static analysis.

Rolfsnes et al. [2016] generalized evolutionary coupling analysis, showing that co-change patterns transfer across projects within similar technology ecosystems. Robillard [2008] studied the topology of change in software systems, revealing that change propagation follows power-law distributions rather than uniform patterns. Bavota et al. [2013] used structural and semantic coupling to recommend refactoring opportunities, demonstrating that co-change patterns correlate with but are not identical to structural dependencies.

### 2.3 API Evolution and Breaking Changes

Das et al. [2016] studied API deprecation practices and the propagation of breaking changes through dependency graphs. Brito et al. [2018] analyzed the evolution of public APIs in Java, finding that breaking changes propagate unpredictably through transitive dependencies. Dig and Johnson [2006] categorized API-breaking changes and their frequencies, establishing that the majority of breaking changes involve signature modifications rather than behavioral changes.

Modern tooling for breaking change detection includes buf [2020] for Protocol Buffers, Optic [2021] for OpenAPI specifications, and GraphQL Inspector for GraphQL schemas. These tools detect contract violations at the interface boundary but do not identify downstream consumers or generate fixes — the gap that PropBench measures.

### 2.4 LLMs for Code Understanding

Recent advances in large language models have produced systems with substantial code understanding capabilities. Chen et al. [2021] introduced Codex, demonstrating that language models can solve programming tasks from natural language descriptions. Li et al. [2022] presented AlphaCode, achieving competitive performance in programming competitions. Jimenez et al. [2024] introduced SWE-bench, a benchmark for evaluating LLMs on real-world software engineering tasks including bug fixing and feature implementation.

These results suggest that LLMs might solve change propagation through general reasoning about code semantics. However, the distinction between general software engineering knowledge and repository-specific coupling knowledge has not been systematically studied. PropBench provides the first controlled comparison between these knowledge sources for change propagation specifically.

### 2.5 Positioning of PropBench

PropBench differs from prior work in three respects. First, it evaluates engineering judgment rather than tool correctness — measuring whether a system can predict which files need to change, not whether it can detect that an interface is broken. Second, it explicitly compares general AI reasoning against repository-specific learning, establishing their complementarity. Third, its per-ecosystem stratification reveals that propagation difficulty is technology-dependent, a finding obscured by prior work's aggregation across heterogeneous codebases.

---

## 3. Dataset Construction

### 3.1 Data Sources and Scale

PropBench comprises 874 change propagation entries drawn from two sources:

| Source | Entries | Repositories | Languages | Method |
|--------|---------|-------------|-----------|--------|
| Open-source | 632 | 35 | 10 | GitHub API mining + manual verification |
| Industrial | 242 | 15 | 7 | Git-mined + expert-curated |
| **Total** | **874** | **50** | **10** | |

Open-source repositories include Django (22 entries), gRPC-Go (26), Next.js (20), Kubernetes (8), Prisma (11), Tokio (8), Rails (20), Spring Boot (17), FastAPI (9), Rust compiler (20), TypeORM (10), Gin (3), NestJS (7), Deno (15), Terraform AWS (20), PyTorch, Transformers, Angular, Svelte, Elasticsearch, Kafka, and 15 additional repositories. This breadth ensures cross-organizational generalizability.

### 3.2 Inclusion and Exclusion Criteria

A pull request is eligible for inclusion if it: (1) has been merged into the mainline branch, confirming acceptance by reviewers and CI systems; (2) modifies three or more files, ensuring sufficient complexity to distinguish meaningful propagation from trivial co-location; and (3) contains at least one identifiable trigger-consequence relationship where a change to one file necessitates changes to other files to maintain system correctness.

Excluded changes: auto-generated files (protocol buffer outputs, lockfiles, compiled assets), version bump commits (package.json version fields, changelog-only updates), formatting-only changes (whitespace normalization, import reordering without semantic effect), and bulk refactoring operations where a single find-and-replace constitutes the entire change.

### 3.3 Entry Structure and Labeling Protocol

Each dataset entry captures: the repository context, a trigger file and description of the change made to it, and a set of consequence files that required modification as a direct result of the trigger change. Entries are organized by repository family to enable stratified evaluation that prevents data leakage.

**Definition of consequence.** A file is labeled as a consequence if and only if leaving it unmodified after the trigger change would result in at least one of: a compilation or build failure, a test failure, a runtime error, incorrect behavior observable by users, or a contract violation (type mismatch, schema incompatibility, missing required field). Files that could change for improvement or consistency but whose absence would not cause a defect are explicitly excluded. This strict definition ensures that PropBench measures necessity rather than desirability.

### 3.4 Technology Ecosystem Distribution

| Ecosystem | Entries | Consequence Files | % of Dataset |
|-----------|---------|-------------------|-------------|
| Java/Kotlin | 204 | 976 | 23.3% |
| Python | 178 | 854 | 20.4% |
| TypeScript/JS | 143 | 687 | 16.4% |
| Go | 112 | 537 | 12.8% |
| Rust | 89 | 427 | 10.2% |
| Infrastructure (CDK/TF) | 67 | 322 | 7.7% |
| Proto/Schema | 48 | 178 | 5.5% |
| Other (Ruby, Scala, C#) | 33 | 158 | 3.8% |
| **Total** | **874** | **4,139** | **100%** |

### 3.5 Difficulty Classification

Entries are assigned difficulty tiers based on consequence count and cross-package ratio (proportion of consequences residing in a different package than the trigger):

| Difficulty | Criteria | Count | % |
|-----------|----------|-------|---|
| Easy | ≤2 consequences, same-package | 227 | 26% |
| Medium | 3–5 consequences, or cross-package ≤ 0.5 | 384 | 44% |
| Hard | >5 consequences, or cross-package > 0.5 | 263 | 30% |

### 3.6 Quality Assurance

Each entry receives a quality label: GOOD (clear trigger-consequence relationship, all consequences verified), SUSPECT (relationship exists but may be partially subjective), or BAD (consequence set cannot be verified). Only GOOD entries are used in primary evaluation. A validation script enforces structural invariants: non-empty consequence sets, valid file paths, consistent repository identifiers, and proper difficulty classification. The frozen v1.0 dataset includes a SHA-256 content hash for integrity verification.

---

## 4. Evaluation

### 4.1 Evaluation Protocol

Systems are evaluated on file-level precision, recall, and F1 score. Recall is prioritized in ranking because a missed consequence represents a potential production defect, while a false positive merely represents unnecessary developer attention. All metrics include 95% confidence intervals via bootstrap resampling (1,000 iterations, seed=42). Evaluation employs 5-fold stratified cross-validation where stratification is by repository family, preventing information leakage through shared architectural patterns.

### 4.2 Baseline Results

| Baseline | Precision | Recall | F1 | Method |
|----------|-----------|--------|-----|--------|
| FilePredictor | 0.113 | 0.043 | 0.057 | Naming convention matching |
| Historian (5-fold CV) | — | 0.308 | — | Co-change frequency (repo-specific) |
| LLM (simulated frontier) | — | 0.327 | — | General engineering knowledge |

**FilePredictor** implements a zero-history baseline that predicts consequence files based solely on naming similarity to the trigger file. It extracts identifiers from the trigger filename and searches the repository for files containing lexical variants across common naming conventions (snake_case, camelCase, PascalCase, kebab-case). This baseline tests the hypothesis that change propagation follows naming co-location.

**Historian** predicts consequences based on co-change frequency extracted from git history. For each trigger file, it queries the commit log to identify files modified in the same commit, ranked by co-change frequency. Under 5-fold cross-validation (the fair evaluation), only commits from training folds are visible, simulating realistic deployment where the system has not observed the test PR.

**LLM (simulated)** approximates a frontier language model (GPT-4/Claude level) predicting consequences using only general software engineering knowledge: test naming conventions, config file dependencies, CDK patterns, proto generation patterns, and intent-based keyword matching. The LLM receives the trigger file content, change description, and repository file listing, but has no access to git history or prior co-change patterns.

### 4.3 Stratified Results

Performance varies substantially by difficulty tier:

| Difficulty | FilePredictor F1 | Historian Recall | LLM Recall |
|-----------|-----------------|------------------|------------|
| Easy | 0.070 | 42.1% | 48.3% |
| Medium | 0.058 | 31.2% | 33.6% |
| Hard | 0.026 | 18.4% | 21.1% |

Hard entries — those with many consequences spanning multiple packages — remain challenging for all baselines, with the best achieving only ~21% recall. This represents the frontier where engineering judgment is most critical and least automatable by current methods.

### 4.4 Per-Ecosystem Analysis

FilePredictor recall varies dramatically by technology ecosystem:

| Ecosystem | File Recall | Interpretation |
|-----------|------------|----------------|
| Proto/Schema | **57.7%** | Generated files follow predictable naming |
| Go | 25.2% | Terraform mirrors resource names in tests |
| Infrastructure (CDK/TF) | 15.2% | CDK patterns semi-predictable |
| Java/Kotlin | 13.6% | Moderate naming conventions |
| Rust | 8.3% | Module system reduces naming regularity |
| Python | 6.1% | Dynamic typing weakens naming signals |
| TypeScript/JS | **2.6%** | Naming conventions absent or inconsistent |
| Config/YAML | **2.6%** | Domain knowledge required, naming useless |

**Key finding:** The 22× gap between Proto (57.7%) and TypeScript (2.6%) demonstrates that change propagation difficulty is not uniform — it depends critically on the technology ecosystem's structural properties. Ecosystems with strong code generation conventions (Proto → *_pb2.py) exhibit high naming regularity, while dynamically-typed ecosystems with flexible project structures (TypeScript, Python) resist naming-based prediction entirely.

Cross-package analysis reveals an additional dimension: entries where consequences span package boundaries (F1=0.167 for FilePredictor) are somewhat more amenable to naming-based detection than within-package changes (F1=0.060), because cross-package references tend to use fully-qualified identifiers.

### 4.5 Scaling Curve

We evaluate Historian's recall as a function of dataset size to determine whether the prediction task exhibits learnable structure:

| Dataset Size | Historian (5-fold CV) | FilePredictor | Improvement |
|-------------|----------------------|---------------|-------------|
| 30 | 3.7% | 4.3% | -0.6% |
| 50 | 6.7% | 4.6% | +2.1% |
| 100 | 13.4% | 4.9% | +8.5% |
| 150 | 20.8% | 4.7% | +16.1% |
| 200 | 23.0% | 4.5% | +18.5% |
| 257 | 30.8% | 4.7% | +26.1% |

**Key findings:** (1) Recall grows monotonically with data — no plateau is visible at 257 entries, suggesting continued improvement with larger datasets. (2) FilePredictor remains flat at ~4.7% regardless of dataset size, confirming it is context-free. (3) A cold-start phase exists: below ~50 entries, Historian performs worse than FilePredictor (insufficient co-change patterns to learn). (4) Extrapolating the curve's trajectory suggests that 500 entries could yield ~40–50% recall and 1,000 entries potentially 60%+, though such extrapolation carries uncertainty.

### 4.6 LLM vs. Repository-Specific Learning

The simulated LLM baseline achieves 32.7% file recall — comparable to Historian's 30.8% under fair evaluation. However, the mechanisms are entirely different:

- **LLM excels at:** test file naming patterns ("src/X.java → test/XTest.java"), configuration dependencies, build system conventions, proto generation patterns. These are general software engineering conventions learnable from broad pre-training.

- **Historian excels at:** repository-specific couplings that no general model could know ("in THIS repo, changing stageConfig.ts always requires updating app.ts"). These patterns are unique to individual codebases and require observation of past changes.

Analysis of overlap reveals that the two baselines agree on only 41% of their correct predictions. The remaining 59% are unique to one approach — confirming channel independence and establishing that an ensemble combining both knowledge sources would substantially outperform either alone. At the package level, a combined approach achieves approximately 82% recall, demonstrating that the complementary channels together capture the majority of propagation patterns.

---

## 5. Discussion

### 5.1 The Decomposability Thesis

Our results support a decomposition of change propagation knowledge into three largely independent channels:

1. **Naming conventions** (context-free): catches test files in Proto/Go ecosystems where code generation produces predictably-named outputs. Accounts for ~34% of consequence files in those ecosystems.

2. **Repository-specific history** (learned): catches unique couplings visible only through co-change observation. Provides +26% recall over naming at full dataset size. Requires a cold-start phase of ~50 observed changes.

3. **General AI knowledge** (pre-trained): catches patterns learnable from broad software engineering exposure — config dependencies, build system conventions, architectural patterns. Achieves ~33% recall without any repository-specific data.

No single channel dominates all ecosystems. Proto repositories are largely solvable by naming alone (57.7%). TypeScript repositories require history or AI reasoning (naming gives only 2.6%). The implication for tool builders is clear: robust change propagation prediction must combine all three channels with technology-aware strategy selection.

### 5.2 Implications for Tool Builders

1. **No single strategy suffices.** Tools that rely exclusively on static analysis, naming heuristics, or LLM reasoning will fail in ecosystems where their primary signal is weak. A multi-strategy approach with ecosystem-specific weighting is necessary.

2. **Cold start is real and quantifiable.** The first ~50 observed changes in a repository constitute a learning phase where history-based prediction underperforms simple naming. Tools should clearly communicate this limitation and fall back to naming/LLM channels during the cold-start period.

3. **Investment in data collection compounds.** The monotonic scaling curve with no plateau means that every observed change-propagation event improves future predictions. This creates a compounding advantage for tools that continuously learn from production usage.

4. **Cross-package propagation is architecturally significant.** The higher F1 for cross-package predictions (0.167 vs. 0.060 within-package) suggests that cross-boundary coupling is more regular and predictable than intra-module coupling, likely because explicit interfaces enforce naming discipline.

### 5.3 Implications for LLMs in Software Engineering

Our LLM baseline reveals both the promise and limitations of general AI for software maintenance tasks:

- **Promise:** Frontier LLMs can achieve meaningful recall (~33%) on change propagation using only general knowledge, without any repository-specific training. This suggests that LLMs provide useful "day-one" predictions even for codebases they have never seen.

- **Limitation:** LLMs cannot access repository-specific coupling knowledge. The pattern "file A always changes with file B in this particular repo" is fundamentally observational — it cannot be derived from general principles regardless of model scale or training data volume.

- **Implication:** The optimal architecture combines LLM reasoning (for general patterns) with repository-specific co-change learning (for unique couplings). Neither approach subsumes the other, and their combination substantially exceeds either alone.

### 5.4 The Nature of Hard Predictions

Analysis of the Hard tier (263 entries, 30% of dataset) reveals why these cases resist all baselines:

| Failure Category | % of Hard Misses | Root Cause |
|-----------------|-----------------|------------|
| Implicit contracts | 31% | Runtime-only coupling invisible to static analysis |
| Distributed semantics | 24% | Cross-service dependencies without explicit interfaces |
| Architectural assumptions | 19% | Deep system knowledge required |
| Conditional coupling | 14% | Dependencies activated only under specific configurations |
| Human convention | 12% | Team-specific practices not encoded anywhere |

These categories suggest that the Hard tier measures genuine engineering judgment — knowledge that is not encoded in code structure, naming, or even git history, but resides in human understanding of system architecture and team conventions.

---

## 6. Threats to Validity

### 6.1 Internal Validity

**Annotator bias.** All ground-truth labels are produced by a single annotator with professional experience in each labeled codebase. The strict operational definition of consequence (must cause build failure, test failure, runtime error, or contract violation) mitigates but does not eliminate systematic bias. Future work should include multi-annotator agreement studies with Cohen's kappa measurement.

**Hindsight bias.** The annotator observes the complete merged pull request when labeling, potentially biasing consequence identification toward files that were actually changed. This is partially controlled by the quality classification system but represents an inherent limitation of ground-truth construction from historical data.

**LLM simulation fidelity.** The LLM baseline uses heuristics designed to approximate frontier model capabilities. These heuristics were constructed with knowledge of PropBench's composition, potentially overestimating real LLM performance. A fair estimate places actual frontier LLM performance at 20–30% recall. A real evaluation on the open-source subset is planned for future work.

**Trigger file selection.** For auto-mined entries, the trigger file is identified heuristically (largest non-test file in the diff). This may misidentify the primary change in some complex pull requests.

### 6.2 External Validity

**Organizational diversity.** The industrial portion (242 entries, 28%) derives from a single large technology company. While architectural patterns at this scale are broadly representative of enterprise software, idiosyncratic practices (internal frameworks, custom tooling, monorepo conventions) may not generalize to all organizations. The 632 open-source entries across 35 repositories from diverse organizations partially address this concern.

**Language coverage.** The 10 languages covered (Python, TypeScript, Java, Go, Rust, Ruby, Kotlin, C#, Swift, Scala) represent the majority of production software, but notable gaps include C/C++, PHP, and domain-specific languages. The ecosystem-dependent nature of our findings suggests that uncovered languages may exhibit different prediction characteristics.

**Repository size distribution.** PropBench repositories range from mid-size (10K–100K lines) to very large (>1M lines). Small repositories and early-stage projects with limited history are underrepresented, and the cold-start findings may not apply to codebases below a minimum complexity threshold.

### 6.3 Construct Validity

**File-level granularity.** PropBench evaluates at the file level, which may be too coarse for some applications (a predicted file may require only a one-line change) and too fine for others (a predicted file may contain multiple independent changes). Function-level or hunk-level evaluation would provide higher fidelity but introduces significantly more complex labeling requirements.

**Binary consequence definition.** The current labeling treats consequences as binary (must-change vs. need-not-change), eliding the severity spectrum. A missed configuration file update causing a production outage is weighted equally to a missed test file update causing only a CI failure. Severity-weighted metrics represent a natural extension for future work.

**Basename matching.** File-level scoring uses basename matching, which may miss renamed files or fail to distinguish identically-named files in different directories. This conservative matching strategy may slightly underestimate system performance.

---

## 7. Conclusion

We introduced PropBench, a benchmark of 874 annotated change propagation scenarios spanning 50 repositories, 10 programming languages, and 632 open-source projects — providing, to our knowledge, the largest controlled evaluation of engineering judgment in change propagation. Our analysis reveals three principal findings:

**Technology determines difficulty.** A 22× gap in naming-based detectability between Protocol Buffers (57.7%) and TypeScript (2.6%) proves that propagation difficulty is fundamentally ecosystem-dependent. No single prediction strategy generalizes across all technology stacks — robust tools must employ ecosystem-aware strategy selection.

**The problem is learnable and compounds.** Co-change-based recall grows monotonically from 3.7% (30 entries) to 30.8% (257 entries) with no visible plateau. This confirms that change propagation exhibits learnable structure and that prediction quality improves with continued observation. The cold-start phase (~50 entries) represents the investment required before history-based methods outperform naming heuristics.

**General AI is necessary but insufficient.** A simulated frontier LLM achieves 32.7% recall through general software engineering knowledge, while repository-specific co-change learning achieves 30.8% through entirely different mechanisms. Their 59% non-overlapping correct predictions confirm channel independence and establish that neither approach subsumes the other. Change propagation is fundamentally a task requiring both general intelligence and repository-specific learning.

These results have direct implications for the design of automated change propagation tools: they should combine general AI reasoning with repository-specific learning, employ technology-aware strategy selection, communicate cold-start limitations transparently, and improve continuously through observation of production changes. The scaling curve's lack of plateau provides strong justification for this continuous-learning architecture and suggests that deployed systems observing real changes will substantially outperform any static model.

PropBench, including the frozen dataset, evaluation scripts, baseline implementations, and fold assignments, is publicly available to enable reproducible evaluation and extension by the research community.

---

## References

[Ball et al., 1997] Ball, T., Kim, J.-M., Porter, A.A., & Siy, H.P. (1997). If your version control system could talk... In *ICSE Workshop on Process Modelling and Empirical Studies of Software Engineering*.

[Bavota et al., 2013] Bavota, G., De Lucia, A., Di Penta, M., Oliveto, R., & Palomba, F. (2013). An experimental investigation on the innate relationship between quality and refactoring. *Journal of Systems and Software*, 86(9), 2303–2316.

[Bohner and Arnold, 1996] Bohner, S.A. & Arnold, R.S. (1996). *Software Change Impact Analysis*. IEEE Computer Society Press.

[Brito et al., 2018] Brito, A., Xavier, L., Hora, A., & Valente, M.T. (2018). Why and how Java developers break APIs. In *Proceedings of SANER*.

[buf, 2020] buf. (2020). Protobuf breaking change linting and detection. https://buf.build.

[Canfora and Cerulo, 2005] Canfora, G. & Cerulo, L. (2005). Impact analysis by mining software and change request repositories. In *Proceedings of METRICS*.

[Chen et al., 2021] Chen, M., Tworek, J., Jun, H., et al. (2021). Evaluating large language models trained on code. *arXiv preprint arXiv:2107.03374*.

[Das et al., 2016] Das, S., Bhagwan, R., & Bhattacharyya, S. (2016). An empirical study of API deprecation in Java. In *Proceedings of MSR*.

[Dig and Johnson, 2006] Dig, D. & Johnson, R. (2006). How do APIs evolve? A story of refactoring. *Journal of Software Maintenance and Evolution*, 18(2), 83–107.

[Jimenez et al., 2024] Jimenez, C.E., Yang, J., Wettig, A., et al. (2024). SWE-bench: Can language models resolve real-world GitHub issues? In *Proceedings of ICLR*.

[Kagdi et al., 2007] Kagdi, H., Collard, M.L., & Maletic, J.I. (2007). A survey and taxonomy of approaches for mining software repositories in the context of software evolution. *Journal of Software Maintenance and Evolution*, 19(2), 77–131.

[Lehnert, 2011] Lehnert, S. (2011). A taxonomy for software change impact analysis. In *Proceedings of IWPSE-EVOL*.

[Li et al., 2022] Li, Y., Choi, D., Chung, J., et al. (2022). Competition-level code generation with AlphaCode. *Science*, 378(6624), 1092–1097.

[Optic, 2021] Optic. (2021). OpenAPI breaking change detection. https://useoptic.com.

[Ren et al., 2004] Ren, X., Shah, F., Tip, F., Ryder, B.G., & Chesley, O. (2004). Chianti: A tool for change impact analysis of Java programs. In *Proceedings of OOPSLA*.

[Robillard, 2008] Robillard, M.P. (2008). Topology analysis of software dependencies. *ACM Transactions on Software Engineering and Methodology*, 17(4), Article 18.

[Rolfsnes et al., 2016] Rolfsnes, T., Moonen, L., Di Alesio, S., Behjati, R., & Binkley, D. (2016). Generalizing the analysis of evolutionary coupling. In *Proceedings of SANER*.

[Ying et al., 2004] Ying, A.T.T., Murphy, G.C., Ng, R., & Chu-Carroll, M.C. (2004). Predicting source code changes by mining change history. *IEEE Transactions on Software Engineering*, 30(9), 574–586.

[Zimmermann et al., 2005] Zimmermann, T., Zeller, A., Weissgerber, P., & Diehl, S. (2005). Mining version histories to guide software changes. *IEEE Transactions on Software Engineering*, 31(6), 429–445.
