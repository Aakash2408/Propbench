# PropBench: Scaling Curve Results

## Historian Recall vs Dataset Size (5-fold CV, averaged over 3 trials)

| Dataset Size | Historian (5-fold) | FilePredictor | Improvement over naming |
|-------------|-------------------|---------------|------------------------|
| 30 | 3.7% | 4.3% | -0.6% (too few entries to learn) |
| 50 | 6.7% | 4.6% | +2.1% |
| 75 | 7.7% | 4.8% | +2.9% |
| 100 | 13.4% | 4.9% | +8.5% |
| 125 | 15.5% | 4.9% | +10.6% |
| 150 | 20.8% | 4.7% | +16.1% |
| 175 | 21.3% | 4.9% | +16.4% |
| 200 | 23.0% | 4.5% | +18.5% |
| 225 | 26.9% | 5.0% | +21.9% |
| 257 (full) | 30.8% | 4.7% | +26.1% |

## Key Findings

1. **Historian recall grows monotonically with data** — from 3.7% at 30 entries to 30.8% at 257.
   The curve shows NO plateau. More data = better predictions. This is the core insight
   supporting the "compounding intelligence" product moat.

2. **FilePredictor is flat at ~4.7%** — naming conventions don't benefit from more data.
   This is expected: naming rules are context-free (don't learn from history).

3. **Crossover point at ~50 entries** — below 50 entries, Historian performs WORSE than
   FilePredictor (not enough co-change patterns to learn). Above 50, it dominates.

4. **No plateau visible** — the curve is still climbing at 257 entries. Extrapolating:
   at 500 entries, Historian might reach 40-50%. At 1000, potentially 60%+.
   This is the strongest argument for growing the dataset.

5. **The "cold start" problem** — Historian needs ~50 entries before it beats naming.
   This means for a NEW repo, the first 50 observed changes are the learning phase.
   After that, predictions improve continuously.

## Implication for the Paper

This curve is Figure 1 in the paper. It proves:
- The problem is learnable (not random)
- More data = better predictions (no plateau)
- The learning has a cold-start phase (~50 entries)
- The approach justifies building a commercial product (compounding intelligence)

## ASCII Plot (for paper text)

```
Recall
  |
30%|                                                    ●
   |                                              ●
25%|                                         ●
   |                                    ●
20%|                               ● ●
   |
15%|                          ●
   |
10%|
   |                    ●
 5%|         ●    ●                                    ─ ─ ─ ─ (FilePredictor ~4.7%)
   |    ●
 0%+────────────────────────────────────────────────── Dataset size
   30   50   75  100  125  150  175  200  225  257
```
