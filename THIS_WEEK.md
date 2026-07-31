# This Week — Strengthen the Benchmark

## Engine: FROZEN at v0.1

Do NOT add new oracles or optimize existing ones until the dataset reaches 30+ entries.
The bottleneck is now the benchmark, not the model.

---

## Primary Objective

> **Determine whether our benchmark measures Amazon knowledge or software engineering knowledge.**

If Pattern + Structure only works on Brazil/AIX/CDK, this is an internal tool.
If it works on Kubernetes/React/Terraform PRs, it's a research discovery.

### Three hypotheses (from most to least proven):

```
H1: Engineering change propagation is predictable.              ← SUPPORTED (82% recall)
H2: Judgment decomposes into independent information channels.  ← SUPPORTED (67% independence)
H3: Those channels are organization-independent.                ← UNTESTED
```

**H3 is the most important untested hypothesis.** Everything this week should help answer it.

---

## Priority 0: One open-source replay (THE generalization test)

Pick ONE merged PR from a well-known open-source project:
- Kubernetes (CRD field addition → controller + tests + schema + docs)
- Terraform (new resource attribute → provider + tests + docs + examples)
- React (new hook → tests + types + docs)
- FastAPI (new parameter → validation + OpenAPI + tests)

### Steps:
1. Find a PR that changed multiple files across a repo
2. Look ONLY at the first/primary file changed
3. Write down: what else would a senior contributor predict?
4. Compare vs what actually changed in the PR
5. Classify: was it Pattern? Structure? History? Domain?

### What this tells you:
- If you can predict 60%+ on a foreign codebase → H3 likely true
- If you get <30% → the knowledge is org-specific (still a product, but narrower)
- Either way, you learn which channel transfers and which doesn't

---

## Priority 1: Add diverse entries (target: 5-10 this week)

### Types to deliberately seek out:

- [ ] A **bug fix** (does fixing a bug propagate to tests? configs?)
- [ ] A **dependency upgrade** (does bumping a version require downstream changes?)
- [ ] A **refactor** (rename, move, restructure — what propagates?)
- [ ] A **teammate's CR** (Utsav, lhitesh, qbhatia — their patterns, not yours)
- [ ] Something that required **zero propagation** (more negative cases)

### Quick capture template:

```yaml
id: "<family>-<nn>"
title: "<one-line>"
family: "<existing or new family name>"
date: "2026-07-XX"
author: "<who>"

trigger:
  package: "<package>"
  files: ["<file>"]
  intent: "<what were they doing?>"
  diff_summary: |
    <2-3 lines>

consequences:
  - package: "<pkg>"
    files: ["<file>"]
    description: "<what and why>"
    mechanical: true/false
    relationship: "structural" / "co-change" / "pattern"
    confidence_an_expert_would_predict: 0.XX
    reasoning: "<why expert knows>"

expert_reasoning: |
  <free text>

common_mistakes:
  - "<what junior gets wrong>"

tags: ["<tag>"]

effort:
  actual_hours: X
  packages_touched: N
```

---

## Priority 2: Talk to one colleague

### The script:

> "I'm trying to figure out how much of what we do when reviewing CRs
> is pattern recognition vs actually reading the code structure.
> Can I walk you through 3 examples? Takes 5 minutes."

### Show them:
1. The AAS onboarding example (pattern-dominated)
2. The CSG GeoRaven example (structure caught what human missed)
3. Ask them to predict one change cold — measure their accuracy

### Record:
- Did they predict via pattern ("I've seen this before") or structure ("this imports that")?
- Were they right?
- What did they miss?
- Add their prediction + the ground truth as a new entry

---

## Priority 3: Sanity check — test yourself blind

Pick a recent CR from a teammate that you HAVEN'T reviewed yet.

1. Read ONLY the triggering change (the diff in the first package)
2. WITHOUT looking at the rest of the CR, write down your prediction
3. Then look at what they actually changed
4. Record accuracy + what you missed

This tests whether your benchmark entries have "hindsight bias" —
you might be labeling consequences as "obviously predictable" only
because you already know the answer.

---

## What NOT to do this week

- ❌ Don't add new oracles
- ❌ Don't optimize Pattern/Structure rules
- ❌ Don't build Historian
- ❌ Don't build the GitHub App
- ❌ Don't chase precision improvements

The only thing that makes the research stronger right now is a
bigger, more diverse, honestly-labeled benchmark.

---

## Friday check-in

Run:
```bash
cd /home/aakkaash/.meshclaw/workspace/judgment-engine
python3.10 -m src.cli
```

Record in the README tracking table:
```
| Date | n | Pattern R | Structure R | Ensemble R | Notes |
```

Did recall hold as the dataset grew? That's the only question that matters.
