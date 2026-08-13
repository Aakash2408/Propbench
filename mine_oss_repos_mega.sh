#!/bin/bash
# PropBench: MEGA OSS Mining -- 50 repositories across 10 languages
# Target: 800+ new entries (20 per repo, ~60% yield after filtering)
#
# Run overnight: tmux new -s mega-mine && bash mine_oss_repos_mega.sh
# Estimated time: 45-60 minutes (rate limit: 5000 req/hr)
#
# Idempotent: won't re-add entries already mined. Safe to re-run.

set -e
cd /home/aakkaash/.meshclaw/workspace/judgment-engine

echo "════════════════════════════════════════════"
echo " PropBench MEGA Mining — 50 OSS Repositories"
echo "════════════════════════════════════════════"
echo ""

if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: Set GITHUB_TOKEN first!"
    echo "  export GITHUB_TOKEN=ghp_your_token_here"
    exit 1
fi

echo "Token found. Starting mega mine..."
echo ""

TOTAL_MINED=0
TOTAL_SKIPPED=0
REPO_NUM=0
TOTAL_REPOS=50

mine() {
    local repo=$1
    local output=$2
    local limit=${3:-20}
    local min_files=${4:-3}
    local max_files=${5:-20}
    
    REPO_NUM=$((REPO_NUM + 1))
    echo "=== [$REPO_NUM/$TOTAL_REPOS] $repo ==="
    
    python3 tools/github_miner.py "$repo" --limit "$limit" --min-files "$min_files" --max-files "$max_files" \
        --output "datasets/families/$output" || echo "  ⚠️ Error on $repo -- continuing..."
    echo ""
}

# ═══════════════════════════════════════════
# PYTHON (8 repos)
# ═══════════════════════════════════════════
echo "━━━ PYTHON ━━━"
mine "django/django"             "oss-django"        20
mine "tiangolo/fastapi"          "oss-fastapi"       20
mine "pallets/flask"             "oss-flask"         20
mine "pytorch/pytorch"           "oss-pytorch"       15 4 25
mine "huggingface/transformers"  "oss-transformers"  15 3 20
mine "scikit-learn/scikit-learn" "oss-sklearn"       15 3 20
mine "celery/celery"             "oss-celery"        15
mine "sqlalchemy/sqlalchemy"     "oss-sqlalchemy"    15

# ═══════════════════════════════════════════
# TYPESCRIPT / JAVASCRIPT (8 repos)
# ═══════════════════════════════════════════
echo "━━━ TYPESCRIPT ━━━"
mine "vercel/next.js"            "oss-nextjs"        20
mine "nestjs/nest"               "oss-nestjs"        20
mine "typeorm/typeorm"           "oss-typeorm"       15
mine "prisma/prisma"             "oss-prisma"        20
mine "angular/angular"           "oss-angular"       15 4 25
mine "sveltejs/svelte"           "oss-svelte"        15
mine "trpc/trpc"                 "oss-trpc"          15
mine "vercel/turborepo"          "oss-turborepo"     15

# ═══════════════════════════════════════════
# GO (7 repos)
# ═══════════════════════════════════════════
echo "━━━ GO ━━━"
mine "kubernetes/kubernetes"     "oss-kubernetes"    20 4 25
mine "grpc/grpc-go"              "oss-grpc-go"       20
mine "gin-gonic/gin"             "oss-gin"           15
mine "hashicorp/terraform-provider-aws" "oss-terraform-aws" 20
mine "prometheus/prometheus"     "oss-prometheus"    15
mine "etcd-io/etcd"              "oss-etcd"          15
mine "gohugoio/hugo"             "oss-hugo"          15

# ═══════════════════════════════════════════
# RUST (6 repos)
# ═══════════════════════════════════════════
echo "━━━ RUST ━━━"
mine "tokio-rs/tokio"            "oss-tokio"         20
mine "rust-lang/rust"            "oss-rust-lang"     20 4 25
mine "denoland/deno"             "oss-deno"          15
mine "tokio-rs/axum"             "oss-axum"          15
mine "actix/actix-web"           "oss-actix"         15
mine "serde-rs/serde"            "oss-serde"         10

# ═══════════════════════════════════════════
# JAVA (5 repos)
# ═══════════════════════════════════════════
echo "━━━ JAVA ━━━"
mine "spring-projects/spring-boot"  "oss-spring-boot"  20
mine "elastic/elasticsearch"        "oss-elasticsearch" 15 4 25
mine "apache/kafka"                 "oss-kafka"         15
mine "google/guava"                 "oss-guava"         15
mine "reactor/reactor-core"         "oss-reactor"       15

# ═══════════════════════════════════════════
# RUBY (4 repos)
# ═══════════════════════════════════════════
echo "━━━ RUBY ━━━"
mine "rails/rails"               "oss-rails"         20
mine "heartcombo/devise"         "oss-devise"        15
mine "sidekiq/sidekiq"           "oss-sidekiq"       15
mine "ruby-grape/grape"          "oss-grape"         10

# ═══════════════════════════════════════════
# C# / .NET (4 repos)
# ═══════════════════════════════════════════
echo "━━━ C# ━━━"
mine "dotnet/runtime"            "oss-dotnet-runtime" 20 4 25
mine "dotnet/aspnetcore"         "oss-aspnetcore"     20
mine "dotnet/efcore"             "oss-efcore"         15
mine "abpframework/abp"          "oss-abp"            15

# ═══════════════════════════════════════════
# KOTLIN (3 repos)
# ═══════════════════════════════════════════
echo "━━━ KOTLIN ━━━"
mine "JetBrains/kotlin"          "oss-kotlin"         15 4 25
mine "ktorio/ktor"               "oss-ktor"           15
mine "JetBrains/Exposed"         "oss-exposed"        10

# ═══════════════════════════════════════════
# SWIFT (2 repos)
# ═══════════════════════════════════════════
echo "━━━ SWIFT ━━━"
mine "vapor/vapor"               "oss-vapor"          15
mine "Alamofire/Alamofire"       "oss-alamofire"      10

# ═══════════════════════════════════════════
# PHP (3 repos)
# ═══════════════════════════════════════════
echo "━━━ PHP ━━━"
mine "laravel/framework"         "oss-laravel"        20
mine "symfony/symfony"            "oss-symfony"        20
mine "filamentphp/filament"      "oss-filament"       15

echo ""
echo "════════════════════════════════════════════"
echo " MEGA MINING COMPLETE!"
echo "════════════════════════════════════════════"
echo ""

OSS=$(find datasets/families/oss-* -name "*.yaml" 2>/dev/null | wc -l)
TOTAL=$(find datasets/families/ -name "*.yaml" | wc -l)

echo "OSS entries:   $OSS"
echo "Total entries: $TOTAL"
echo ""
echo "Next:"
echo "  python3 tools/validate_dataset.py"
echo "  python3 tools/freeze_dataset.py"
echo "  python3 src/evaluation.py --baseline file_predictor --dataset datasets/frozen/v1.0.yaml"
