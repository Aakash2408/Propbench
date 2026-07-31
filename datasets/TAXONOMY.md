# Dataset Taxonomy

## Current families (Amazon-specific naming)

These are how the dataset is currently organized. As it grows,
we should migrate toward universal categories that work for any codebase.

## Mapping: Amazon → Universal

| Current (Amazon)     | Universal Category        | What it captures |
|---------------------|---------------------------|------------------|
| aas-onboarding      | Interface Evolution       | Adding new types/sources to a typed system |
| country-expansion   | Configuration Evolution   | Adding variants to config-driven behavior |
| cdk-infrastructure  | Infrastructure Evolution  | IaC changes that cross account/service boundaries |
| config-changes      | Configuration Evolution   | Modifying shared config with multiple consumers |
| integration-tests   | Test Evolution            | Adding tests that require build dependencies |

## Universal categories (target taxonomy)

```
Interface Evolution
  Adding/changing types, fields, APIs, protos, schemas
  Examples: new proto field, GraphQL type, REST endpoint, CRD spec

Configuration Evolution  
  Adding/changing config that drives runtime behavior
  Examples: feature flags, country configs, permission policies

Infrastructure Evolution
  IaC changes that affect cross-service topology
  Examples: CDK stacks, Terraform modules, IAM policies, SNS topics

Schema Evolution
  Database/event schema changes that ripple to consumers
  Examples: DDB table changes, Kafka schema, event format changes

Dependency Evolution
  Upgrading/adding dependencies that affect the build graph
  Examples: package version bumps, new SDK imports, library swaps

Test Evolution
  Test changes that require infrastructure or dependency updates
  Examples: new integ test needing SDK, test config changes

Generated Artifacts
  Changes that trigger regeneration of derived code
  Examples: OpenAPI → client SDK, proto → generated types, schema → migrations

Deployment Evolution
  Changes to how code is deployed/rolled out
  Examples: new Lambda, new pipeline stage, deployment config
```

## Why this matters

If we label entries with universal categories, we can:
1. Compare Amazon results vs open-source results in the same category
2. Test whether "Interface Evolution" patterns transfer across ecosystems
3. Build oracles that recognize the CATEGORY (not the Amazon-specific family)

## The key question

> Does "adding a new field to a typed schema always requires updating consumers"
> hold true regardless of whether the schema is a protobuf, GraphQL type,
> Kubernetes CRD, or OpenAPI spec?

If yes → the Pattern oracle generalizes.
If no → we need per-ecosystem playbooks (still a product, but more work per customer).
