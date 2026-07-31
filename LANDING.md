# Landing Page Copy — propagate.dev

## Hero

**Know what else needs to change — before you merge.**

Every PR has hidden dependencies. PropagateBot finds them before your users do.

[Install on GitHub — Free for open source]

---

## The Problem

You change one file. Three services break.

Not because you made a mistake. Because nobody can keep the entire dependency graph in their head.

Senior engineers catch these. Juniors don't. And seniors are busy.

---

## The Solution

PropagateBot analyzes every PR and tells you what else likely needs updating.

```
⚠️ This PR changes the Orders API schema.

These files likely need updating:

• billing-service/OrdersClient.ts (94% — API contract)
• tests/integration/orders.test.ts (87% — co-change history)
• docs/api/orders.md (62% — references this endpoint)
```

No configuration. No rules to write. It learns from your git history.

---

## How it works

1. **Install** — One click. Works immediately.
2. **Scan** — Analyzes your git history to learn propagation patterns.
3. **Predict** — Comments on PRs with likely missing changes.
4. **Learn** — Gets better with every PR merged.

---

## Why it's different

Other tools check **what you changed**.
We predict **what you forgot to change**.

- No rules to configure (learns from your history)
- No CI pipeline changes required
- Works across repos in an org
- Gets smarter over time

---

## Pricing

**Open Source** — Free forever. Unlimited public repos.

**Starter** — $49/month. Private repos, 1 org.

**Team** — $199/month. 5 repos, custom patterns.

**Enterprise** — Custom. SSO, audit, self-hosted.

---

## Early access

We're onboarding 20 teams for the beta.

[Get early access →]

---

## FAQ

**How does it know what to predict?**
Three knowledge sources: your git history (what changed together before), your code structure (imports, dependencies), and common patterns (API changes → SDK updates). No LLM guessing.

**Does it slow down my CI?**
No. It runs asynchronously and posts a comment. It never blocks merge.

**What if it's wrong?**
React with 👎. It learns. Predictions improve with every PR.

**Do you store my code?**
We read diffs and file paths to make predictions. We don't store source code. Analysis results are cached per-repo and deletable.

**Does it work with monorepos?**
Yes. Monorepos with cross-directory dependencies are where it shines most.
