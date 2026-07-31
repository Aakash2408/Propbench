# Dataset Format

## Philosophy

The benchmark IS the foundation. Without clean, reproducible data, every
experiment is unreliable. With it, every experiment becomes cumulative.

Start with 10 pristine examples. Expand to 50 once the pipeline works.

## Directory Structure

```
datasets/
├── README.md (this file)
├── families/
│   ├── aas-onboarding/
│   │   ├── 01-wellspring.yaml
│   │   ├── 02-global-store.yaml
│   │   ├── 03-llm-derived-v2.yaml
│   │   └── 04-no-photo-driveway-mobility.yaml
│   ├── country-expansion/
│   │   ├── 01-pr-pt-za-cdp.yaml
│   │   └── 02-holiday-additions.yaml
│   ├── cdk-infrastructure/
│   │   ├── 01-sns-cross-account.yaml
│   │   ├── 02-necto-gamma-account.yaml
│   │   └── 03-building-summary-gating.yaml
│   ├── integration-tests/
│   │   ├── 01-defect-lifecycle.yaml
│   │   └── 02-defect-event-processor-lambda.yaml
│   └── config-changes/
│       ├── 01-csg-georaven-us-removal.yaml
│       └── 02-dhs-handshake-fix.yaml
└── schema.yaml
```

## Change Record Schema (YAML)

```yaml
# Unique identifier
id: "aas-onboarding-03"

# Human-readable description
title: "Add LLM_DERIVED_V2 source for DELIVERY_HINT at BUILDING and UNIT level"

# Classification
family: "aas-onboarding"
date: "2026-07-24"
author: "aakkaash"

# The triggering change
trigger:
  package: "AIXAttributeConfigData"
  files:
    - "configuration/attributes/DELIVERY_HINT.json"
  intent: "Add LLM_DERIVED_V2 as a source at BUILDING and UNIT level with propagation from BUILDING down to UPIDs"
  diff_summary: |
    Added LLM_DERIVED_V2 to:
    - propagationConfig (US BUILDING + CAMPUS)
    - selectionConfig sourceWhitelist (US BUILDING + US UNIT)
    - strategyConfigEntry (US BUILDING + US UNIT)

# Ground truth: what actually needed to change downstream
consequences:
  - package: "GAMCoreModel"
    files:
      - "configuration/SourceConfiguration.prototxt"
    description: "Add PROPAGATED.BUILDING.LLM_DERIVED_V2 and PROPAGATED.CAMPUS.LLM_DERIVED_V2 to source registry"
    mechanical: true
    relationship: "structural"  # proto dependency

  - package: "AteamIntegrationTests"
    files:
      - "tst/com/amazon/aas/integration/DeliveryHintLlmDerivedV2Test.java"
    description: "Add integration test for new source combination"
    mechanical: false  # test logic requires domain understanding
    relationship: "co-change"  # not structurally required, but always done

  - package: "AASTypesCoral"
    files: []
    description: "Coral model sync — historically lags 3-6 months"
    mechanical: true
    relationship: "co-change"
    optional: true  # not required for the change to work
    lag: "3-6 months"

# Evidence that an expert would use
expert_reasoning: |
  - Every previous source onboarding (WELLSPRING, GLOBAL_STORE) touched
    exactly these 3 packages in the same order.
  - GAMCoreModel must have PROPAGATED.X.SOURCE entries for any propagation
    to work at runtime.
  - AteamIntegrationTests is the CI gate — without it, the pipeline
    won't validate the change works end-to-end.
  - AASTypesCoral is the Coral sync that always comes later.

# What a junior engineer would miss
common_mistakes:
  - "Forgetting GAMCoreModel — change deploys but propagation silently fails at runtime"
  - "Not realizing AteamIntegrationTests is on a different version set (ATEAMIntegTest/release)"
  - "Trying to include AASTypesCoral in the same CR — different VS, different timeline"

# Tags for analysis
tags:
  - "multi-package"
  - "config-driven"
  - "pattern-repeating"
  - "cross-version-set"

# How long this took manually
effort:
  actual_hours: 16  # across 2 days including CR iterations
  mechanical_hours: 4  # the mechanical parts alone
  review_hours: 8  # waiting for CR review + AutoSDE
```

## Key Design Decisions

### 1. `mechanical: true/false`

Tracks whether a consequence is purely syntactic (copy a pattern, add a field)
or requires semantic understanding (design a test, choose correct values).

This directly answers: "What % is automatable?"

### 2. `relationship` field

Values:
- `structural`: actual code/config dependency (import, reference)
- `co-change`: historically always changes together (no hard dependency)
- `pattern`: matches a known playbook
- `causal`: the trigger caused a runtime failure requiring this fix

### 3. `expert_reasoning`

Free text explaining WHY an expert would predict this. This is the gold.
When the engine gets a prediction wrong, compare its reasoning to this field.

### 4. `common_mistakes`

What junior engineers actually get wrong. This defines where the product
creates value — the gap between junior and senior.

### 5. `surprise` (added during benchmarking)

After running predictions, any consequence that NO strategy predicted gets
tagged as a "surprise." These reveal hidden dependencies and tribal knowledge
that need to be captured.

## How to add a new entry

1. Pick a real change you made (or reviewed)
2. Write the `trigger` section from memory or git log
3. Write `consequences` by looking at what actually changed (all CRs in the same effort)
4. Write `expert_reasoning` — why would YOU have known this?
5. Write `common_mistakes` — what has a junior actually gotten wrong?
6. Tag it with a family

The dataset should grow by 2-3 entries per week from your normal work.
Don't force it. Just capture what happens naturally.
