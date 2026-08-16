# PropBench v1.1 — changelog

Status: **provenance fully resolved.** All 634 resolvable references have been
checked against their hosts. 631 verify (99.5%). Three do not.

## Why v1.1 exists

v1.0 shipped without any check that an entry corresponds to a real change.
`tools/validate_dataset.py` validates *structure* — required fields, path shapes,
duplicates — and never resolved a citation. Once consequence files are
**authored** rather than read off a diff, nothing constrains them to be true.

Full resolution, 634 entries:

| Result | n | Meaning |
|---|---|---|
| `verified` | **631** (99.5%) | reference resolves and claimed files overlap the real diff |
| `mismatched` | 2 | reference resolves but claimed files do not intersect it |
| `unreachable` | 1 | HTTP 404 — does not exist |

The three:

| Entry | Cited source | Verdict |
|---|---|---|
| `oss-fastapi-01` | tiangolo/fastapi#11117 | **404 — does not exist** |
| `oss-django-01` | django/django#16553 | exists, titled *"Increase coverage"* — claims 3 files, none in that PR |
| `oss-react-01` | facebook/react#28270 | exists, but claims 4 files where only 2 are real and they do not intersect |

### Correction to an earlier draft of this file

An earlier version stated that **three** cited PRs did not exist —
`react#28270`, `fastapi#11117` and `fastapi#9816`. That was wrong, and wrong for
an instructive reason: those spot-checks ran against an exhausted unauthenticated
rate limit, so GitHub returned **HTTP 403** and the validator recorded it as
`unreachable`. Only `fastapi#11117` is genuinely absent. `react#28270` exists
(its labels are simply wrong) and `fastapi#9816` **verifies cleanly**.

The validator now separates 404 (definitive) from 403/429/5xx (transient, never
cached), because caching a transient failure makes a false "does not exist"
verdict permanent. That defect was found by an adversarial fixture in the
verification stage — after it had already contaminated this changelog.

So the damage in v1.0 is **3 entries of 881 (0.34%)**, not the ~3.6% first
estimated. The corpus is in far better shape than the initial curated-entry
sample suggested.

## What is and is not verifiable

| Source | n | Provenance |
|---|---|---|
| `github-api-mined` | 629 | `source_repo` + `source_pr` — all resolvable, all verified |
| `git-mined` | 226 | internal Amazon packages — **not publicly verifiable** |
| `curated-url` | 11 | 5 resolvable (2 of the 3 problems are here), 6 cite docs pages with no commit |
| `?` / repo-only | 15 | no identifier at all |

The `git-mined` entries need local clones or reclassification as a separate
internal split; a GitHub token does nothing for them.

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
manifest rather than a directory restructure. With resolution now complete the
manifest is authoritative: 631 `verified`, 2 `mismatched`, 1 `unreachable`, and
247 `n/a` (internal or no reference). A restructure is now *possible*; whether it
is desirable is a separate call, since moving files breaks every existing
citation of an entry's path.

## Exit criteria for release

1. ~~Resolve the remaining 616 references.~~ **Done** — 634/634 resolved,
   631 verified, 3 problems named above.
2. Regenerate labels from observed diffs for every verified entry.
3. Decide the disposition of the 226 internal entries — validate from local
   clones or reclassify as a separate internal split.
4. Remove or quarantine the entries with no resolvable source.
5. Flip the provenance gate in `dataset.yml` from `continue-on-error` to
   blocking.
6. Publish the validator alongside the dataset so any reader can re-run it.

Point 6 is the actual upgrade. "882 entries" is a weaker claim than "every entry
is machine-verifiable against its source commit, and here is the script."
