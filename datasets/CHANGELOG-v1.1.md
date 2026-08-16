# PropBench v1.1 — changelog

Status: **in progress.** The tooling below is complete and the offline audit has
run across all 881 entries. Online resolution of 616 entries is outstanding and
needs a GitHub token; until it completes, v1.0 remains the published dataset and
v1.1 is not releasable.

## Why v1.1 exists

v1.0 shipped with entries whose cited sources do not exist. Spot-checking five
hand-curated entries:

| Entry | Cited source | Reality |
|---|---|---|
| `oss-react-01` | facebook/react#28270 | does not exist |
| `oss-fastapi-01` | tiangolo/fastapi#11117 | does not exist |
| `oss-fastapi-03` | tiangolo/fastapi#9816 | does not exist |
| `oss-django-01` | django/django#16553 | exists, titled *"Increase coverage"* — unrelated to the entry |
| `oss-k8s-01` | kubernetes/kubernetes#109798 | **real and matching** |

`tools/validate_dataset.py` did not catch this because it validates *structure* —
required fields, path shapes, duplicates — and never checked whether an entry
corresponds to anything real. Once consequence files are **authored** rather than
read off a diff, nothing constrains them to be true.

This is stated plainly because the alternative is a reviewer finding it. The
paper's contribution is label integrity; that makes provenance the whole claim.

## What is and is not affected

The damage is confined to the hand-written entries. The mined corpus is sound:

| Source | n | Provenance |
|---|---|---|
| `github-api-mined` | 629 | `source_repo` + `source_pr` — resolvable |
| `git-mined` | 226 | internal Amazon packages — **not publicly verifiable** |
| `curated-url` | 11 | 5 resolvable, 6 cite docs pages with no commit |
| `?` / repo-only | 15 | no identifier at all |

Of 18 mined entries resolved so far, **18 verified** — the PR exists and the
entry's files overlap the real diff. At n=18 with zero failures the failure rate
is under roughly 17% with 95% confidence. So roughly 3.6% of the dataset has
broken provenance, not the bulk of it.

## Findings that change how the dataset should be used

**Labels are ~80% complete, not wrong.** Measured against the real diffs of the
18 verified entries: 97 claimed files, 121 actually changed, overlap 97. Precision
is 100%, completeness 80.2%. No entry captures its full changed set;
`kubernetes#109798` claims 3 files where the PR touched 78. Scoring a tool against
an 80%-complete label penalises it for finding files that genuinely needed
changing but were never written down.

**The corpus is co-change, not breaking change.** Only **61 of 629** mined entries
(9.7%) are removal-shaped by title/intent. `grpc-go#9221` is typical of the rest:
+714/−2, a pure feature addition. Both are legitimate research targets, but only
the removal-shaped subset exercises a tool whose job is fixing consumers after a
contract breaks.

**Propagation has two vectors, and the dataset conflates them.**

- `symbol` — a declared identifier was removed; consumers name it.
- `package` — a directory was deleted; consumers are files inside it plus
  importers of its path, most naming no single identifier.

`kubernetes#109798` is a package deletion: 63 of 78 files are `status=removed`,
42 under `pkg/security/podsecuritypolicy/`, and the type `PodSecurityPolicy` is
not in the diff at all. Querying the wrong vector under-reports badly — 38.5%
versus 90.9% on that PR, with no change to the tool.

**Difficulty was asserted, not measured.** Entries carry miner-assigned
`difficulty` and `confidence_an_expert_would_predict: 0.5`.
`tools/classify_misses.py` derives it from vector kind, unsupported-language
share and hard-miss count instead.

**Miss categories, grounded in observed misses** rather than proposed a priori:
`co_change_addition` (file gained lines, lost none — never a propagation target),
`unsupported_language` (24 of 36 files in the k8s label are YAML or shell),
`abbreviation_alias` (`SkipPrivileged**PSP**Binding` — an acronym no variant
generator can derive), `low_confidence`, `symbol_absent_other`.

## What changed in the repo

| Added | Purpose |
|---|---|
| `tools/validate_provenance.py` | resolves every entry's reference; classifies verified / mismatched / unreachable / internal-unverifiable / no-reference. `--manifest` emits the split. |
| `tools/extract_seed.py` | derives seed file, symbol, and vector kind mechanically from a real diff; replaces authored labels with observed ones |
| `tools/classify_misses.py` | grounded miss taxonomy + derived difficulty |
| `tools/replay.py` | runs a consumer-finder against verified entries; reports recall over known positives |
| `datasets/PROVENANCE.md`, `datasets/provenance.json` | generated manifest |
| `.github/workflows/dataset.yml` | first CI for this repo |

**No entries were moved or deleted.** The verified/unverified split is a generated
manifest, not a directory restructure, because 616 entries are still
`unresolved` — a state deliberately kept distinct from `verified`. Filing them
under `verified/` now would assert a check that has not been made.

## Exit criteria for release

1. Resolve the remaining 616 references (needs a token; the cache makes the run
   resumable).
2. Regenerate labels from observed diffs for every verified entry.
3. Decide the disposition of the 226 internal entries — validate from local
   clones or reclassify as a separate internal split.
4. Remove or quarantine the entries with no resolvable source.
5. Flip the provenance gate in `dataset.yml` from `continue-on-error` to
   blocking.
6. Publish the validator alongside the dataset so any reader can re-run it.

Point 6 is the actual upgrade. "882 entries" is a weaker claim than "every entry
is machine-verifiable against its source commit, and here is the script."
