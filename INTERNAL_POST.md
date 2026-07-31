# What Is Engineering Judgment Actually Made Of?
## An Empirical Decomposition of Change Propagation Prediction

**Author:** Aakash Sangwan (aakkaash@) | ate-aixp  
**Date:** July 2026  
**Tags:** engineering-productivity, ML, developer-tools, knowledge-graphs

---

## The Question

Every senior engineer has experienced it: you see a code change and instantly know what else needs updating. A proto field gets added — you immediately think "SourceConfiguration, integration tests, and the Coral model." A config gets removed — you think "wait, does something else read that?"

But what IS that knowledge? Is it pattern memory? Structural reasoning? Historical experience? And can we measure it?

## What We Did

We built **PropBench**, a replay benchmark for engineering change propagation. The setup:

1. Take a real code change (the "trigger")
2. Hide what else actually changed downstream
3. Predict what else needs updating
4. Score against ground truth

We collected **257 real engineering changes** from 18 production repositories and 15+ engineers. Then we evaluated multiple independent "knowledge channels" — each one only allowed to use ONE source of information.

## The Knowledge Channels

| Channel | What it knows | How it predicts |
|---------|--------------|-----------------|
| **Pattern** | "I've seen this kind of change before" | Organizational playbooks (e.g., AAS onboarding always requires GAMCoreModel) |
| **Structure** | "The code tells me" | File naming, imports, config relationships |
| **History** | "These files change together" | Co-change frequency from git history |

## Results

### Package-level prediction (which packages need updating):

```
Pattern + Structure combined:   81% recall, 76% precision
(on 14 hand-curated cross-package entries)
```

### File-level prediction (which specific files):

```
Naming conventions alone:       8% recall
Co-change history:             25% recall
Combined:                      33% recall
```

### The Knowledge Hierarchy

```
Level       What it captures              Transferability
─────────── ───────────────────────────── ─────────────────
Semantic    Organizational playbooks       Potentially high
Structural  Code conventions              Moderate
Statistical File co-occurrence            Repository-specific
```

## The Surprising Finding: Knowledge is Repo-Specific

We tested whether learned patterns transfer across codebases:

```
Within same repo, across engineers:     14% file recall (partial transfer)
Across different repositories:           1% file recall (almost nothing transfers)
```

**Co-change knowledge is overwhelmingly repository-specific.** The graph learns "in THIS repo, constants.ts always changes with lambda.ts" — but that tells you nothing about a different repo.

However, STRUCTURAL patterns (naming conventions like `Foo.java → FooTest.java`) DO transfer — because they're language-level conventions, not project-specific.

## Why This Matters for Our Team

### For Wellspring / Building Summary

The same question applies to geospatial attribute propagation:
- When a delivery signal arrives, which places need re-evaluation?
- When a hierarchy changes, which attributes become stale?
- Can we learn propagation patterns from historical Wellspring executions?

The PropBench methodology (decompose into channels, measure independently, test transfer) applies directly to optimizing our trigger pipeline.

### For Developer Productivity

Imagine a tool that comments on your CR:

> "Based on 17 historical commits, you probably also need to update SourceConfiguration.prototxt and AteamIntegrationTests."

Our data shows this is achievable with ~80% accuracy at package level using only organizational patterns + code structure — no LLM required.

### For Onboarding

New team members lack the "pattern" channel entirely. A tool that surfaces co-change history ("engineers who changed this file also changed these 3 files") gives them day-1 access to institutional knowledge that normally takes months to acquire.

## Technical Details

- **Benchmark:** 257 entries, 18 repos, auto-mined via git history
- **Evaluation:** Proper train/test split (chronological), leave-one-engineer-out, leave-one-repo-out
- **Learning curve:** Needs 100+ commits before co-change history becomes useful
- **Temporal control:** Order doesn't matter — co-occurrence IS the signal

## Open Questions

1. Can we apply this to Wellspring execution optimization? (Reduce unnecessary re-evaluations)
2. Does domain-level transfer work? (CDK repo → another CDK repo)
3. What's the human baseline? (How do senior vs junior engineers score?)
4. Can LLMs improve on the statistical approaches? (Intent understanding)

## Get Involved

If you're interested in:
- Contributing benchmark entries from YOUR packages
- Testing the prediction on your CRs
- Applying the methodology to other propagation problems (attribute freshness, cache invalidation, deployment impact)

Reach out: aakkaash@ | #ate-aixp

---

## References

- PropBench codebase: [internal path — available on request]
- Related: Wellspring 2026 attribute learning pipeline
- Methodology parallels: SWE-bench (code generation), ImageNet (vision)

---

*This work was done as an engineering research project exploring the intersection of developer productivity and ML methodology. The benchmark and tools are available for internal use.*
