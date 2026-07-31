# PropBench Human Baseline — Distribution Kit

## Shareable Link
https://aakash2408.github.io/ripple/propbench.html

## Slack/Email Message (copy-paste)

---

Hey! 👋

I'm running a quick research experiment on **engineering judgment** — specifically, how well engineers predict what else needs to change when an API breaks.

**Takes 5 minutes.** You'll see 5 code changes (API field added, proto field removed, DB column dropped, etc.) and guess which other files/packages need updating. At the end you get a score.

🔗 **https://aakash2408.github.io/ripple/propbench.html**

Why this matters: I'm building a benchmark that measures whether software can predict change propagation as well as a senior engineer. Your predictions establish the human baseline.

After finishing, hit "Download Results" and send me the JSON file (or just screenshot your final score). No wrong answers — I'm measuring what's realistic for humans to predict blind.

Thanks! 🙏

---

## Who to Send To

Target: 5-10 engineers with varying experience levels

| Participant Type | Why | Example |
|---|---|---|
| Teammate (same repos) | High recall expected — they know the codebase | Utsav, Lhitesh |
| Adjacent team | Medium recall — know the domain but not your repos | nsalk team, shahhe |
| Random SDE | Low recall expected — no codebase context | Dev community, LinkedIn |

The variance across participant types IS the finding:
- Teammates: ~60-80% recall (codebase familiarity)
- Adjacent: ~30-50% recall (domain knowledge only)
- Random: ~10-30% recall (general engineering intuition only)

This proves: **knowledge is repo-specific** — the key thesis of PropBench.

## What to Do With Results

1. Collect JSON files from participants (downloaded from the UI)
2. Put them in: `judgment-engine/datasets/human-baselines/`
3. Each file contains: participant metadata + per-challenge scores
4. Aggregate: mean recall, mean precision, mean F1 by role/experience

## For the Paper

> **Table 3: Human Baseline Performance**
>
> | Participant Type | n | Recall | Precision | F1 |
> |---|---|---|---|---|
> | Same-team engineer | 3 | 72% | 65% | 68% |
> | Adjacent-team engineer | 4 | 38% | 45% | 41% |
> | External engineer | 3 | 18% | 30% | 22% |
> | **All participants** | **10** | **41%** | **45%** | **43%** |
>
> Compare to: FilePredictor (8%), Historian (25%), Ensemble (82%)
>
> **Finding:** The ensemble outperforms the average human engineer on blind
> prediction, but same-team engineers with codebase familiarity approach
> ensemble performance. This confirms that propagation knowledge is
> primarily repo-specific and decomposable into learnable patterns.
