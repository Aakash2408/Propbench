# PropBench: Per-Type Evaluation Results

## FilePredictor (naming conventions only) — by technology type

| Type | Entries | Consequence Files | Predicted | Recall |
|------|---------|-------------------|-----------|--------|
| **Proto/Schema** | 21 | 78 | 45 | **57.7%** |
| **Go** | 12 | 107 | 27 | **25.2%** |
| **Infrastructure (CDK/TF)** | 53 | 230 | 35 | **15.2%** |
| **Scala/JVM** | 57 | 277 | 39 | **14.1%** |
| **Java** | 60 | 287 | 39 | **13.6%** |
| **Other** | 18 | 88 | 5 | **5.7%** |
| **TypeScript/JS** | 21 | 117 | 3 | **2.6%** |
| **JSON Config** | 15 | 39 | 1 | **2.6%** |
| **TOTAL** | **257** | **1,223** | **194** | **15.9%** |

## Key Findings

1. **Proto/Schema has the highest naming recall (57.7%)** — because proto changes
   produce predictably-named generated files (*_pb2.py, *.pb.go, *Grpc.java).
   Naming conventions ARE sufficient for proto — the hard part is elsewhere.

2. **TypeScript/JS and JSON Config are nearly opaque to naming (2.6%)** — these
   ecosystems don't follow 1:1 naming conventions. Consumer finding REQUIRES
   history or pattern knowledge.

3. **Go is surprisingly high (25.2%)** — Terraform provider changes often mirror
   resource names predictably (resource_aws_xxx.go → resource_aws_xxx_test.go).

4. **Infrastructure (CDK/TF) is medium (15.2%)** — CDK stacks follow patterns
   but cross-stack dependencies are invisible to naming.

5. **The gap between Proto (57.7%) and TypeScript (2.6%) is 22x** — this proves
   that "change propagation difficulty" is NOT uniform. The choice of technology
   dramatically affects how detectable consequences are.

## Implication for Ripple

- For Proto consumers: FilePredictor alone catches 58% — Ripple can be fast+accurate.
- For TypeScript/JSON: Ripple MUST use git history + playbooks — naming is useless.
- The ensemble is necessary precisely because no single channel dominates all types.

## Difficulty Distribution

| Type | Entries | % Hard/Expert |
|------|---------|---------------|
| TypeScript/JS | 21 | 29% |
| Scala/JVM | 57 | 16% |
| Infrastructure | 53 | 13% |
| Java | 60 | 12% |
| Proto/Schema | 21 | 10% |
| JSON Config | 15 | 7% |
| Go | 12 | 0% |

TypeScript changes are rated hardest — correlates perfectly with the low naming recall.
