#!/bin/bash
# PropBench: Mine OSS repositories for new entries
# 
# Requirements:
#   - GITHUB_TOKEN env var set (personal access token with public_repo scope)
#   - python3 with pyyaml installed
#
# Usage:
#   export GITHUB_TOKEN=ghp_your_token_here
#   bash mine_oss_repos.sh
#
# Target: 40+ new entries across 5 diverse repos

set -e
cd /home/aakkaash/.meshclaw/workspace/judgment-engine

echo "======================================"
echo " PropBench OSS Mining - 5 repositories"
echo "======================================"
echo ""

if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: Set GITHUB_TOKEN first!"
    echo "  export GITHUB_TOKEN=ghp_your_token_here"
    echo ""
    echo "Get one at: https://github.com/settings/tokens"
    echo "Scopes needed: public_repo (read public repos)"
    exit 1
fi

echo "Token found. Rate limit: 5000 requests/hour."
echo ""

# 1. Django (Python, large OSS, many multi-file PRs)
echo "=== 1/15: Django ==="
python3 tools/github_miner.py django/django --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-django

# 2. Next.js (TypeScript, React framework, complex build)
echo "=== 2/15: Next.js ==="
python3 tools/github_miner.py vercel/next.js --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-nextjs

# 3. gRPC (Go + Proto, cross-language propagation)
echo "=== 3/15: gRPC ==="
python3 tools/github_miner.py grpc/grpc-go --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-grpc-go

# 4. Prisma (TypeScript + DB schemas, ORM changes)
echo "=== 4/15: Prisma ==="
python3 tools/github_miner.py prisma/prisma --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-prisma

# 5. Kubernetes (Go, massive repo, API changes)
echo "=== 5/15: Kubernetes ==="
python3 tools/github_miner.py kubernetes/kubernetes --limit 20 --min-files 4 --max-files 25 \
    --output datasets/families/oss-kubernetes

# 6. Tokio (Rust, async runtime, complex dependency graph)
echo "=== 6/15: Tokio (Rust) ==="
python3 tools/github_miner.py tokio-rs/tokio --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-tokio

# 7. Ruby on Rails (Ruby, full-stack framework)
echo "=== 7/15: Rails (Ruby) ==="
python3 tools/github_miner.py rails/rails --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-rails

# 8. Spring Boot (Java, enterprise framework)
echo "=== 8/15: Spring Boot (Java) ==="
python3 tools/github_miner.py spring-projects/spring-boot --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-spring-boot

# 9. FastAPI (Python, modern web framework)
echo "=== 9/15: FastAPI (Python) ==="
python3 tools/github_miner.py tiangolo/fastapi --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-fastapi

# 10. Rust Compiler (Rust, massive, complex propagation)
echo "=== 10/15: Rust Compiler ==="
python3 tools/github_miner.py rust-lang/rust --limit 20 --min-files 4 --max-files 25 \
    --output datasets/families/oss-rust-lang

# 11. TypeORM (TypeScript + DB, ORM like Prisma)
echo "=== 11/15: TypeORM ==="
python3 tools/github_miner.py typeorm/typeorm --limit 15 --min-files 3 --max-files 20 \
    --output datasets/families/oss-typeorm

# 12. Gin (Go, HTTP framework)
echo "=== 12/15: Gin (Go) ==="
python3 tools/github_miner.py gin-gonic/gin --limit 15 --min-files 3 --max-files 15 \
    --output datasets/families/oss-gin

# 13. NestJS (TypeScript, enterprise Node framework)
echo "=== 13/15: NestJS ==="
python3 tools/github_miner.py nestjs/nest --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-nestjs

# 14. Deno (TypeScript + Rust, runtime)
echo "=== 14/15: Deno ==="
python3 tools/github_miner.py denoland/deno --limit 15 --min-files 3 --max-files 20 \
    --output datasets/families/oss-deno

# 15. Terraform AWS Provider (Go, infrastructure)
echo "=== 15/15: Terraform AWS ==="
python3 tools/github_miner.py hashicorp/terraform-provider-aws --limit 20 --min-files 3 --max-files 20 \
    --output datasets/families/oss-terraform-aws

echo ""
echo "======================================"
echo " Mining complete!"
echo "======================================"
echo ""

# Count results
NEW=$(find datasets/families/oss-* -name "*.yaml" 2>/dev/null | wc -l)
TOTAL=$(find datasets/families/ -name "*.yaml" | wc -l)

echo "OSS entries: $NEW"
echo "Total entries: $TOTAL"
echo ""
echo "Next steps:"
echo "  1. Validate: python3 tools/validate_dataset.py"
echo "  2. Freeze: python3 tools/freeze_dataset.py"
echo "  3. Evaluate: python3 src/evaluation.py --baseline file_predictor --dataset datasets/frozen/v1.0.yaml"
