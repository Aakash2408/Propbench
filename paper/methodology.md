# Methodology

## Dataset Construction Protocol

PropBench entries are constructed from merged pull requests in production codebases. The selection criteria ensure that each entry represents a non-trivial change propagation scenario with verifiable ground truth.

**Inclusion Criteria.** A pull request is eligible for inclusion if it: (1) has been merged into the mainline branch, confirming that the change was accepted by reviewers and CI systems; (2) modifies three or more files, ensuring sufficient complexity to distinguish meaningful propagation from trivial co-location; and (3) contains at least one identifiable trigger-consequence relationship where a change to one file necessitates changes to other files to maintain system correctness.

**Exclusion Criteria.** The following changes are excluded from the dataset: auto-generated files (protocol buffer outputs, lockfiles, compiled assets), version bump commits (package.json version fields, changelog-only updates), formatting-only changes (whitespace normalization, import reordering without semantic effect), and bulk refactoring operations where a single find-and-replace constitutes the entire change (as these test grep-like tooling rather than engineering judgment).

**Entry Structure.** Each dataset entry captures: the repository context, a trigger file and description of the change made to it, and a set of consequence files that required modification as a direct result of the trigger change. Entries are organized by repository family (e.g., all entries from a single codebase share a family identifier) to enable stratified evaluation that prevents data leakage.

**Selection Process.** Candidate pull requests are identified through repository mining scripts that filter by file count and merge status. A human annotator then reviews each candidate to identify the primary trigger change and its downstream consequences. Pull requests with ambiguous causality (where multiple independent changes are bundled) are rejected. The annotator decomposes complex PRs into multiple entries only when distinct trigger-consequence chains are clearly separable.

## Ground Truth Labeling

**Annotator Qualification.** All ground truth labels are produced by a single annotator with two or more years of professional experience in each labeled codebase. This ensures deep familiarity with architectural patterns, dependency relationships, and implicit contracts that govern change propagation in that system.

**Labeling Protocol.** The annotator reviews the merged pull request and identifies: (a) the trigger file — the file whose change initiates the propagation chain; (b) the trigger description — a natural-language summary of what changed and why; and (c) the consequence set — files that MUST change to maintain correctness after the trigger change.

**Definition of Consequence.** A file is labeled as a consequence if and only if leaving it unmodified after the trigger change would result in at least one of: a compilation or build failure, a test failure, a runtime error, incorrect behavior observable by users, or a contract violation (type mismatch, schema incompatibility, missing required field). Files that COULD change for improvement, consistency, or style but whose absence would not cause a defect are explicitly excluded. This strict definition ensures that the benchmark measures necessity rather than desirability.

**Quality Classification.** Each entry is assigned a quality label: GOOD (clear trigger-consequence relationship, all consequences verified), SUSPECT (relationship exists but may be partially subjective or incomplete), or BAD (consequence set cannot be verified or is empty). Only GOOD entries are used in primary evaluation; SUSPECT entries are included in sensitivity analyses.

## Evaluation Protocol

**Primary Metrics.** Systems are evaluated on file-level recall (proportion of true consequence files that are predicted), precision (proportion of predicted files that are true consequences), and F1 score (harmonic mean of recall and precision). Recall is prioritized in ranking, as a missed consequence represents a potential defect that escapes to production, while a false positive merely represents unnecessary developer attention.

**Statistical Methodology.** All reported metrics include 95% confidence intervals computed via bootstrap resampling with 1,000 iterations. For each bootstrap sample, entries are drawn with replacement from the evaluation set, metrics are computed over the resampled set, and the 2.5th and 97.5th percentiles define the confidence interval. This non-parametric approach makes no distributional assumptions about metric variability.

**Cross-Validation Protocol.** Evaluation employs 5-fold stratified cross-validation, where stratification is performed by repository family. This ensures that all entries from a single codebase appear in the same fold, preventing information leakage through shared architectural patterns, naming conventions, or co-change histories. The stratification is critical: without it, a model could memorize repository-specific patterns from training entries and exploit them on test entries from the same repository, inflating apparent performance.

**Deterministic Splitting.** Fold assignments are generated with a fixed random seed (seed=42) and frozen at dataset release. All evaluations reported in this work and by future researchers use identical splits, enabling direct comparison without variance from random partitioning.

## Baseline Descriptions

### FilePredictor (Naming Convention Matching)

FilePredictor implements a zero-history baseline that predicts consequence files based solely on naming similarity to the trigger file. It extracts identifiers from the trigger filename and searches the repository for files containing lexical variants of those identifiers across common naming conventions: snake_case, camelCase, PascalCase, UPPER_SNAKE_CASE, and kebab-case. A file is predicted as a consequence if its path contains any variant of the trigger identifier. This baseline tests the hypothesis that change propagation follows naming co-location — that files sharing identifier substrings tend to require co-modification.

### Historian (Co-Change Frequency)

Historian implements a history-based baseline that predicts consequence files based on co-change frequency extracted from git history. For each trigger file, Historian queries the repository's commit log to identify all files that have been modified in the same commit as the trigger file. Files are ranked by co-change frequency (number of shared commits divided by total commits touching the trigger file). A threshold is applied to produce a binary prediction set.

Historian is evaluated under two configurations: (a) full history, where the entire git log (excluding the test commit) is available, representing an upper bound on history-based prediction; and (b) 5-fold cross-validation, where only commits from training folds are available, representing realistic deployment conditions where the system has not observed the test PR.

### LLM Baseline (Prompted Prediction)

The LLM baseline evaluates the ability of large language models to predict change consequences from natural-language understanding of the trigger change. The model receives: the trigger file's content, a description of the change made, and a list of all files in the repository. It is prompted to identify which files would require modification to maintain correctness after the described change.

This baseline tests whether general-purpose reasoning about code semantics, combined with broad pre-training on software repositories, is sufficient to predict change propagation without repository-specific history or training.

## Difficulty Classification

Entries are classified into three difficulty tiers to enable fine-grained analysis of system performance across varying complexity levels:

**Easy** (consequence count ≤ 2, cross-package ratio = 0). Changes where consequences are few and confined to the same package or module as the trigger. These typically involve direct references (imports, type annotations, test files) discoverable through static analysis.

**Medium** (consequence count 3–5, OR cross-package ratio > 0 and ≤ 0.5). Changes requiring moderate propagation, potentially crossing package boundaries. These often involve interface changes affecting a bounded set of consumers.

**Hard** (consequence count > 5, OR cross-package ratio > 0.5). Changes with wide-reaching consequences spanning multiple packages or architectural layers. These require understanding of implicit contracts, runtime dependencies, or distributed system semantics that are not captured in static dependency graphs.

The cross-package ratio is defined as the proportion of consequence files residing in a different top-level package or module than the trigger file. This metric captures architectural distance, which correlates with prediction difficulty independent of consequence count.

## Threats to Validity

### Internal Validity

**Annotator Bias.** All labels are produced by a single annotator, introducing potential systematic bias in what constitutes a "necessary" consequence. The strict operational definition (must cause build failure, test failure, runtime error, or contract violation) mitigates but does not eliminate this threat. Future work should include multi-annotator agreement studies with Cohen's kappa measurement.

**Hindsight Bias.** The annotator observes the complete merged PR when labeling, potentially biasing consequence identification toward files that were actually changed rather than files that should have been changed. This is partially controlled by the quality classification system, which flags entries where the relationship is ambiguous.

### External Validity

**Repository Diversity.** The current dataset draws primarily from Amazon internal codebases, which may exhibit architectural patterns, code review standards, and dependency structures atypical of the broader software ecosystem. The inclusion of open-source repositories (Django, React, Kubernetes, FastAPI, Next.js, gRPC) partially addresses this concern, but the Amazon-to-OSS ratio remains skewed. Generalization claims should be tempered accordingly.

**Technology Ecosystem Bias.** Preliminary analysis reveals substantial performance variation across technology ecosystems (e.g., Protocol Buffer entries vs. TypeScript entries). Results aggregated across the full dataset may mask ecosystem-specific strengths or weaknesses of prediction systems.

### Construct Validity

**File-Level Granularity.** PropBench evaluates at the file level, which may be too coarse for some applications (a predicted file may require only a one-line change) and too fine for others (a predicted file may contain multiple independent changes). Function-level or hunk-level evaluation would provide higher fidelity but introduces significantly more complex labeling requirements and inter-annotator disagreement.

**Binary Consequence Definition.** The current labeling treats consequences as binary (must-change vs. need-not-change), eliding the severity spectrum. A missed configuration file update that causes a production outage is weighted equally to a missed test file update that causes a CI failure. Severity-weighted metrics represent a natural extension.

## Reproducibility

**Frozen Dataset.** PropBench v1.0 is released as a frozen dataset with a SHA-256 content hash computed over the canonical serialization of all entries. Any modification to entry content, ordering, or metadata will produce a different hash, enabling verification of dataset integrity.

**Deterministic Evaluation.** All random operations (fold assignment, bootstrap sampling) use documented seeds. The evaluation harness is released as open-source code alongside the dataset, enabling exact reproduction of all reported results.

**Open Artifacts.** The following artifacts are publicly released: (1) the frozen v1.0 dataset (268 entries, YAML format); (2) fold assignments for 5-fold stratified CV (seed=42); (3) evaluation scripts computing all metrics with bootstrap CIs; (4) baseline implementations (FilePredictor, Historian, LLM); and (5) the dataset validation and quality assurance tooling. All code is released under a permissive open-source license to enable extension, critique, and comparison by the research community.
