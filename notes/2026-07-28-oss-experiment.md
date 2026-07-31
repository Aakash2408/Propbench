# Research Note: OSS Generalization Experiment (2026-07-28)

## What we tested

Added 2 open-source entries (Terraform, Kubernetes) to PropBench and ran the benchmark.

## Results

```
BY ORIGIN:
  Amazon:       P=74% R=82% (11 entries)
  Open Source:  P=100% R=100% (2 entries)
```

## Why the OSS numbers are misleading

The 100%/100% is an artifact of our scoring methodology, not evidence of generalization.

**The problem:** Our benchmark scores at the PACKAGE level. In Amazon's ecosystem,
propagation crosses packages (AIXAttributeConfigData → GAMCoreModel). In open-source
monorepos (K8s, Terraform), ALL consequences are in the SAME package (kubernetes/kubernetes
or terraform-provider-aws). So StructureOracle's "same package" prediction trivially
gets 100%.

**What we'd actually need to test:** File-level prediction within a monorepo. "Given that
you changed types.go, which OTHER files need changing?" That's a different scoring model.

## What the experiment DID show (through reasoning, not measurement)

1. The PATTERN channel exists in open source:
   - Terraform has documented contribution playbooks (schema → test → docs → changelog)
   - Kubernetes has rigid API evolution patterns (types.go → proto → deepcopy → validation)
   - These are organizational memory, just like AAS onboarding is at Amazon

2. The STRUCTURE channel exists in open source:
   - Generated files follow naming conventions (_test.go, zz_generated.*, generated.proto)
   - Doc files mirror resource names (website/docs/r/glue_job.html.markdown)

3. The SAME GAP exists:
   - Changelog files have no structural link (pure process knowledge)
   - Controller logic requires intent understanding
   - Validation package location is convention, not derivable from structure

## Honest status of H3

```
H3: Knowledge channels are organization-independent

Status: PLAUSIBLE but NOT YET EVIDENCED

What we have: Qualitative reasoning showing the same pattern
What we need: Quantitative replay of real OSS PRs scored at file level
```

## What would constitute real evidence

1. Take 10 real K8s PRs that added API fields
2. Hide all files except types.go
3. Predict which OTHER files changed
4. Score at file level (not package level)
5. Compare accuracy to the Amazon dataset

If file-level Pattern + Structure achieves >60% recall on K8s PRs,
THAT would be real evidence for H3.

## Next steps

- The current OSS entries should be marked as "reasoned examples" not "replayed PRs"
- A proper generalization test requires file-level scoring
- This is a benchmark improvement task, not an engine improvement task
- Adding file-level scoring is a prerequisite for testing H3 properly

## What this means for the product

Even without proving H3 quantitatively, the qualitative analysis suggests
the ARCHITECTURE is sound:
- Classify change type → select playbook → predict consequences
- This pattern works for ANY ecosystem with documented conventions

The question is: can you LEARN the playbook automatically (from git history
or contribution docs), or do you need to hand-code it per ecosystem?

If learnable → PLG product (install, scan history, works)
If hand-coded → Consulting/onboarding-heavy product (still viable, slower growth)
