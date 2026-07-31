# Verification Criteria

## Three hypotheses to prove or kill

---

## Hypothesis 1: Accuracy holds at scale

**Claim:** 82% combined recall (Pattern + Structure) holds as dataset grows from 11 to 50+ entries.

**How to verify:**
- Add 3-5 entries per week from normal work
- Run benchmark after every 10 new entries
- Track recall over time

**Pass condition:**
```
At n=50:  Combined recall >= 75%
At n=50:  PatternOracle precision >= 80%
```

**Fail condition:**
```
At n=30:  Combined recall drops below 60%
At n=30:  PatternOracle precision drops below 65%
```

**What failure means:**
- If recall drops → the 11-entry dataset was biased toward your familiar patterns
- If precision drops → false positives increase with diversity (rules are too broad)
- Action: analyze WHICH families degrade. Maybe new families need new oracles.

**Tracking:**
| Date | n | Pattern R | Structure R | Combined R | Notes |
|------|---|-----------|-------------|------------|-------|
| 2026-07-28 | 11 | 53% | 55% | 82% | Initial benchmark |
| | | | | | |
| | | | | | |

---

## Hypothesis 2: Generalizes to other codebases

**Claim:** The prediction approach works on codebases you've never seen — not just your AAS/CDK/CdpModelGenerator ecosystem.

**How to verify:**
- Test on at least 3 different contexts:
  1. A colleague's recent CR (same team, different packages)
  2. A CR from a different team entirely (different patterns)
  3. An open-source repo (completely unknown codebase)

**Pass condition:**
```
At least 2 of 3 contexts: recall >= 50% on first attempt
(Before tuning any patterns for that codebase)
```

**Fail condition:**
```
All 3 contexts: recall < 30%
```

**What failure means:**
- If same-team CRs work but other-team don't → patterns are team-specific (not generalizable as a product — but still valuable as an internal tool)
- If nothing generalizes → the approach only works with hand-tuned playbooks per codebase (still a product, but requires onboarding work per customer)

**Key test:** Can StructureOracle (which uses NO org-specific knowledge) achieve >40% recall on a foreign codebase? If yes, structural analysis generalizes. If no, even code structure isn't enough without context.

---

## Hypothesis 3: People actually want this

**Claim:** Engineers find propagation predictions useful enough to keep using the tool.

**How to verify:**
- Install on 5 repos (yours + colleagues')
- Track: do they look at the predictions? Do they act on them?
- After 2 weeks, ask: "Would you notice if I turned this off?"

**Pass condition:**
```
3 of 5 users say "don't turn it off"
OR
At least 1 user installs it on a SECOND repo unprompted
```

**Fail condition:**
```
After 2 weeks: 4 of 5 users ignore predictions completely
OR
Most common feedback: "it tells me things I already knew"
```

**What failure means:**
- "I already knew" → tool is too obvious, not adding value (need harder predictions)
- "It's always wrong" → accuracy doesn't generalize (go back to H2)
- "It's annoying" → wrong delivery mechanism (maybe not PR comments — maybe IDE?)
- "I don't care" → the problem isn't painful enough (pivot or kill)

---

## Decision framework

```
         H1: Accuracy holds?
              │
      ┌───────┴───────┐
     YES              NO
      │                │
      ▼                ▼
 H2: Generalizes?    Fix dataset/oracles
      │               or accept niche
      ├── YES
      │    │
      │    ▼
      │  H3: People want it?
      │    │
      │    ├── YES → BUILD THE COMPANY
      │    │
      │    └── NO → Wrong delivery mechanism
      │              (try IDE plugin? Slack bot? CLI?)
      │
      └── NO → Hand-tuned per customer
               (consulting model, not PLG)
```

---

## Timeline

```
Week 1-2:   Add entries, talk to colleagues (THIS_WEEK.md)
Week 3-4:   Hit n=20, run benchmark, check H1 trend
Week 5-6:   Test on colleague's CR, check H2
Week 7-8:   If H1+H2 pass: build minimal GitHub App
Week 9-12:  Install on 5 repos, measure H3
Week 12:    DECISION POINT — continue, pivot, or kill
```

---

## The kill criteria (be honest about these)

**Kill the startup if:**
- Accuracy consistently below 60% on diverse codebases
- Nobody uses it after initial novelty wears off
- The prediction is only useful when hand-tuned per codebase (doesn't scale)
- A major platform (GitHub, GitLab) ships this as a feature

**Keep building if:**
- Accuracy stays >75% as dataset grows
- At least one person says "this caught something I would have missed"
- The tool gets better with usage (data flywheel working)
- Clear willingness to pay from at least 1 team

**Pivot direction if accuracy fails but interest exists:**
- From "predict propagation" → "visualize dependencies" (lower bar, still useful)
- From "automated prediction" → "playbook library" (manual but curated)
- From "PR bot" → "onboarding tool" (help new team members learn propagation patterns)

---

## The one number to watch

If you only track ONE thing:

> **How often does the tool predict something the engineer hadn't already thought of?**

That's the "novel win" rate. If it's >10%, the tool is genuinely augmenting expertise.
If it's 0%, you're just confirming what people already know — which is still useful
(prevents forgetting) but much harder to sell.

Target: >15% novel win rate by week 12.
