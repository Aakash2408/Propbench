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
echo "=== 1/5: Django ==="
python3 tools/github_miner.py django/django --limit 10 --min-files 3 --max-files 20 \
    --output datasets/families/oss-django

# 2. Next.js (TypeScript, React framework, complex build)
echo "=== 2/5: Next.js ==="
python3 tools/github_miner.py vercel/next.js --limit 10 --min-files 3 --max-files 20 \
    --output datasets/families/oss-nextjs

# 3. gRPC (Go + Proto, cross-language propagation)
echo "=== 3/5: gRPC ==="
python3 tools/github_miner.py grpc/grpc-go --limit 10 --min-files 3 --max-files 20 \
    --output datasets/families/oss-grpc-go

# 4. Prisma (TypeScript + DB schemas, ORM changes)
echo "=== 4/5: Prisma ==="
python3 tools/github_miner.py prisma/prisma --limit 10 --min-files 3 --max-files 20 \
    --output datasets/families/oss-prisma

# 5. Kubernetes (Go, massive repo, API changes)
echo "=== 5/5: Kubernetes ==="
python3 tools/github_miner.py kubernetes/kubernetes --limit 10 --min-files 4 --max-files 25 \
    --output datasets/families/oss-kubernetes

echo ""
echo "======================================"
echo " Mining complete!"
echo "======================================"
echo ""

# Count results
NEW=$(find datasets/families/oss-django datasets/families/oss-nextjs datasets/families/oss-grpc-go \
    datasets/families/oss-prisma datasets/families/oss-kubernetes -name "*.yaml" 2>/dev/null | wc -l)
TOTAL=$(find datasets/families/ -name "*.yaml" | wc -l)

echo "New entries: $NEW"
echo "Total entries: $TOTAL"
echo ""
echo "Next steps:"
echo "  1. Review entries for quality (grep 'needs-review' datasets/families/oss-*/)"
echo "  2. Run evaluation: python3 -m src.leave_one_out"
echo "  3. Update paper with new OSS count"
