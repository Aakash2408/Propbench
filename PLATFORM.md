# Platform Roadmap: From PR Bot to Change Intelligence

## The Expansion Principle

Every new product is the SAME prediction engine answering a DIFFERENT question.
Each layer adds a new oracle and a new data source — nothing is rebuilt from scratch.

```
Month 0-6:   "What else needs changing?"    (PropagateBot — PR comments)
Month 6-9:   "What will break?"             (Impact Preview — pre-merge)
Month 9-12:  "What broke?"                  (because/ — post-deploy)
Month 12-15: "What's risky?"                (RiskScore — deploy confidence)
Month 15-18: "What should we migrate?"      (DebtMap — tech debt priority)
Month 18+:   Full Change Intelligence Platform
```

---

## Product 1: PropagateBot (Month 0-6)
**Already designed. See PRODUCT.md.**

Question: "What else needs to change?"
Data: Git history + code structure + patterns
Oracle: Pattern + Structure + Historian
Output: PR comment listing likely-needed changes

---

## Product 2: Impact Preview (Month 6-9)

### Question
> "If I merge this PR, what downstream services/tests/deployments will be affected?"

### What's new vs Product 1
Product 1 predicts *files* that need changing (within your control).
Product 2 predicts *systems* that will be affected (beyond your control).

```
Product 1 (PropagateBot):
  "You should also update billing-service/OrdersClient.ts"
  → Action: you fix it before merging

Product 2 (Impact Preview):
  "If you merge this, the nightly analytics pipeline will likely fail
   because it reads from the orders table schema you just changed"
  → Action: coordinate with the analytics team, or wait for their window
```

### New oracle needed: DeploymentOracle
```
Knows:
- Which services deploy from which repos
- Service dependency graph (what calls what)
- Deploy schedules and environments
- Test coverage per service

Predicts:
- "This change affects the API contract → downstream service X
   will fail on next deploy if they don't update"
- "This migration requires coordinated deployment with services Y, Z"
```

### New data source
- Service mesh / API gateway traffic data (who calls whom)
- CI/CD pipeline definitions (what triggers what)
- Deploy history (which repos deploy together)

### Revenue trigger
This is where $199/month → $499/month.
Org-wide cross-repo impact analysis is an enterprise feature.

---

## Product 3: because/ (Month 9-12)

### Question
> "Something broke in production. Why? Which change caused it?"

### What's new
Products 1-2 look FORWARD (predict impact before merge).
Product 3 looks BACKWARD (explain incidents after they happen).

```
Input:  Alert fires at 03:00. Latency spike on orders-service.
Output: "Root cause: PR #412 merged at 02:45 changed the DB query
         in OrdersRepository.ts. The new query doesn't use the index
         on customer_id, causing full table scan under load."
```

### New oracle needed: CausalOracle
```
Knows:
- Deployment timestamps (what shipped when)
- Alert/metric timelines (what went wrong when)
- Change-to-deploy mapping (which PR → which deploy)
- Historical incident patterns (similar past failures)

Predicts (backward):
- "This deploy correlates with this alert within 5 minutes"
- "This type of code change has caused this type of failure 3 times before"
- "The causal chain: commit → deploy → metric spike → alert"
```

### New data sources
- CloudWatch / Datadog / PagerDuty (metrics + alerts)
- Deployment systems (Apollo, ArgoCD, GitHub Actions)
- Incident management (PagerDuty, Opsgenie, SIM-T)

### This is the because/ thesis
Same engine, reverse direction. The dependency graph tells you what
*could* be affected. The causal oracle figures out what *was* affected.

### Revenue trigger
Incident correlation is a $50K-$200K/year enterprise sale.
"Cut MTTR from 2 hours to 10 minutes" is a clear ROI story.

---

## Product 4: RiskScore (Month 12-15)

### Question
> "How risky is this deployment? Should we ship it now or wait?"

### What's new
Products 1-3 are reactive (analyze changes or incidents).
Product 4 is predictive (score risk BEFORE the deploy happens).

```
Deploy Risk Assessment:

  PR #412: Add currency field to orders API

  Risk Score: 7.2 / 10 (HIGH)

  Factors:
  ├── Breaking API change: +3.0
  ├── 6 downstream consumers not yet updated: +2.5
  ├── Friday 4pm deploy window: +1.0
  ├── No integration tests for new field: +0.7
  └── Author's first change to this service: +0.0 (n/a)

  Recommendation: WAIT
  - 4 consumers should update first
  - Deploy Tuesday with full test coverage

  Similar past deploys: 3 found
  - 2/3 caused incidents within 24h
```

### New oracle needed: RiskOracle
```
Knows:
- Historical deploy success/failure rates
- Change characteristics that correlate with incidents
- Team patterns (who deploys safely, who doesn't)
- Environmental factors (time of day, day of week, holidays)

Scores:
- Change complexity (how many systems touched)
- Coordination risk (how many teams need to align)
- Coverage gap (what's not tested)
- Historical risk (similar changes that caused problems)
```

### New data sources
- Historical incident ↔ deploy correlation (from Product 3)
- Test coverage reports
- Deploy success/failure logs

### Revenue trigger
This is where compliance teams get excited.
SOC2/SOX auditors want evidence that risky changes get extra scrutiny.
"Every deploy gets a risk score and high-risk deploys require approval"
is an enterprise governance feature worth $100K+/year.

---

## Product 5: DebtMap (Month 15-18)

### Question
> "What should we migrate/refactor next? Where is tech debt costing us the most?"

### What's new
Products 1-4 operate on individual changes.
Product 5 operates on the WHOLE codebase over time.

```
Tech Debt Prioritization:

  #1: orders-service → billing-service coupling
      Impact: 14 PRs in last quarter required coordinated changes
      Cost: ~42 engineer-hours of propagation work
      Fix: Extract shared types into common library
      ROI: Save ~35 hours/quarter

  #2: Legacy auth middleware in 8 services
      Impact: Every auth change requires 8 separate PRs
      Cost: ~28 engineer-hours per auth update
      Fix: Centralize into auth-service SDK
      ROI: Save ~24 hours per update

  #3: Undocumented API contracts (orders, billing, analytics)
      Impact: 6 incidents in last quarter from contract changes
      Cost: ~18 hours MTTR + customer impact
      Fix: Add OpenAPI specs + contract tests
      ROI: Prevent ~4 incidents/quarter
```

### What powers this
All the data from Products 1-4:
- PropagateBot: which files always change together (coupling signal)
- Impact Preview: which services are most interdependent
- because/: which coupling causes the most incidents
- RiskScore: which areas are riskiest

DebtMap doesn't need a new oracle. It's an AGGREGATION layer on top
of everything already collected.

### Revenue trigger
This is the CTO/VP Eng sale. "Here's your migration priority queue,
ranked by ROI, updated in real-time as your codebase evolves."
$200K-$500K/year enterprise contracts.

---

## The Data Flywheel

```
Each product generates data that makes the next product better:

PropagateBot (PRs analyzed)
     │
     ├── Co-change patterns → better predictions
     ├── Dependency graph → Impact Preview
     │
Impact Preview (cross-service mapping)
     │
     ├── Service topology → faster incident correlation
     ├── Deploy coordination → risk factors
     │
because/ (incidents explained)
     │
     ├── Incident patterns → risk scoring
     ├── Causal chains → tech debt identification
     │
RiskScore (deploys scored)
     │
     ├── Risk factors → debt prioritization
     ├── Success/failure data → better predictions
     │
DebtMap (tech debt mapped)
     │
     └── Migration priorities → back to PropagateBot
         (predict impact of the migration itself)
```

---

## Competitive Positioning Over Time

```
Month 6:   "Better than Dependabot for API changes"
Month 9:   "Datadog for code changes" 
Month 12:  "Incident correlation across your full stack"
Month 15:  "Risk management for software delivery"
Month 18:  "The change intelligence platform"
```

## Enterprise Pricing Ladder

```
Free:        PropagateBot on public repos
$49/mo:      PropagateBot on private repos
$199/mo:     + Impact Preview (org-wide)
$499/mo:     + because/ (incident correlation)
$2,000/mo:   + RiskScore (deployment governance)
$5,000+/mo:  + DebtMap (strategic tech debt planning)
             + SSO, audit, API, custom oracles
```

## When to build each product

DON'T build on a schedule. Build when the DATA tells you to.

- Build Impact Preview when: PropagateBot users ask "but what about OTHER repos?"
- Build because/ when: you have enough deploy + alert data to correlate
- Build RiskScore when: because/ has identified patterns in incident causation
- Build DebtMap when: you have 6+ months of propagation data showing coupling

Each product is gated by having sufficient data from the previous product.
Don't build ahead of your data. The roadmap is aspirational, not a commitment.

---

## The One Thing That Stays Constant

Every product on this roadmap answers the same underlying question:

> "What does an expert know that software could learn?"

PropagateBot: expert knows what else to change
Impact Preview: expert knows what will break
because/: expert knows what caused it
RiskScore: expert knows what's dangerous
DebtMap: expert knows what to fix first

Same engine. Same benchmark. Same philosophy.
Different questions. Different data. Different buyers.
