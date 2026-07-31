# Product Blueprint: PropagateBot

## One-liner

> "Know what else needs to change — before you merge."

## How it works

```
Developer opens PR
         │
         ▼
GitHub sends webhook to your server
         │
         ▼
Server analyzes the diff:
  1. What changed? (diff parser)
  2. What type of change is this? (classifier)
  3. What else likely needs updating? (oracles)
         │
         ▼
Bot comments on the PR with predictions
         │
         ▼
Developer clicks [Helpful] or [Dismiss]
         │
         ▼
Feedback improves future predictions
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     PropagateBot                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  WEBHOOK RECEIVER (POST /webhook)                            │
│  ├── Event: pull_request.opened                              │
│  ├── Event: pull_request.synchronize (new commits)           │
│  └── Validates GitHub signature                              │
│                                                              │
│  ANALYZER                                                    │
│  ├── Fetch PR diff via GitHub API                            │
│  ├── Parse changed files                                     │
│  ├── Classify change type                                    │
│  ├── Run oracles (Pattern + Structure + Historian)           │
│  └── Rank predictions by confidence                          │
│                                                              │
│  COMMENTER                                                   │
│  ├── Format prediction as markdown comment                   │
│  ├── Post via GitHub API (Issues/Comments)                   │
│  ├── Include [Helpful] [Dismiss] reaction prompts            │
│  └── Track reactions for feedback loop                       │
│                                                              │
│  LEARNING (async)                                            │
│  ├── After PR merges: check what ACTUALLY changed            │
│  ├── Compare predictions vs reality                          │
│  ├── Update co-change frequency model                        │
│  └── Log accuracy metrics                                    │
│                                                              │
│  STORAGE                                                     │
│  ├── Per-repo: dependency graph (cached)                     │
│  ├── Per-repo: co-change matrix (from git history)           │
│  ├── Per-org: pattern library (learned playbooks)            │
│  └── Global: prediction accuracy metrics                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

```
Runtime:        Python 3.11 + FastAPI (or Node.js + Express)
Hosting:        Railway / Fly.io / Render (start cheap, ~$7/month)
Database:       SQLite per repo (or Postgres for multi-tenant)
GitHub API:     PyGithub or octokit
Background:     Celery/Redis or simple async tasks
Domain:         propagate.dev (or similar)
```

## GitHub App Setup

1. Register at https://github.com/settings/apps/new
2. Permissions needed:
   - Pull requests: Read & Write (to comment)
   - Contents: Read (to fetch files/diffs)
   - Metadata: Read
3. Subscribe to events:
   - Pull request (opened, synchronize, closed)
4. Webhook URL: https://your-server.com/webhook
5. Generate private key for authentication

## PR Comment Template

```markdown
### 🔍 Propagation Check

This PR changes `orders-service/src/api/orders.ts`

**Likely also needs updating:**

| File | Confidence | Reason |
|------|-----------|--------|
| ⚠️ `billing-service/src/clients/OrdersClient.ts` | 94% | API contract change (field renamed) |
| ⚠️ `tests/integration/orders.test.ts` | 87% | Co-changed in 8/10 similar PRs |
| ℹ️ `docs/api/orders.md` | 62% | References the modified endpoint |

<details>
<summary>How was this predicted?</summary>

- **PatternOracle**: Matched "API field rename" playbook
- **StructureOracle**: `OrdersClient.ts` imports from `orders.ts`
- **Historian**: These files changed together in 8 of the last 10 PRs touching this endpoint

</details>

---
Was this helpful? React with 👍 or 👎
*PropagateBot learns from your feedback*
```

## Onboarding Flow (first install)

```
1. User installs GitHub App on their repo/org
2. Bot scans git history (last 6 months of commits)
   - Builds co-change matrix
   - Identifies file dependency graph
   - Discovers patterns (files that always change together)
3. Bot posts welcome comment on next PR:
   "PropagateBot is now watching this repo. 
    I've analyzed 847 commits and found 23 common
    propagation patterns. I'll comment on PRs when
    I detect potential missing changes."
4. First real prediction on next qualifying PR
```

## Pricing

```
Free:         Public repos, up to 50 PRs/month
Starter:      $49/month — private repos, 1 org, unlimited PRs
Team:         $199/month — 5 repos, custom patterns, priority
Enterprise:   Custom — SSO, audit log, self-hosted, SLA
```

## Metrics to Track

```
- PRs analyzed per day
- Predictions made per PR
- Helpful rate (👍 / total predictions)
- Dismiss rate (👎 / total predictions)  
- Accuracy (post-merge: did they actually change what we predicted?)
- Time-to-install (onboarding friction)
- Retention (% of repos still active after 30 days)
```

## Growth Loop

```
Bot predicts correctly
         │
         ▼
Developer trusts it
         │
         ▼
Developer installs on another repo
         │
         ▼
More data → better predictions
         │
         ▼
More trust → org-wide installation
         │
         ▼
Enterprise upgrade
```

## MVP Scope (ship in 2 weekends)

Weekend 1:
- GitHub App registration
- Webhook receiver (FastAPI)
- Diff parser
- PatternOracle + StructureOracle (port from PropBench)
- PR comment posting

Weekend 2:
- Git history scan on install (build co-change matrix)
- Historian oracle
- Feedback collection (reaction tracking)
- Deploy to Railway/Fly.io
- Install on 3 personal repos

## What's NOT in MVP

- Custom pattern configuration
- Dashboard/web UI
- Multi-org management
- Billing/payments
- SSO
- Self-hosted option

These come after you have 10+ active repos proving the predictions work.
