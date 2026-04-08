#!/bin/bash
# ============================================================
# Finance & Accounting Ecosystem — GitHub Setup Script
# Run this once from inside your finops/ folder
# Usage: bash github_setup.sh <your-github-repo-url>
# Example: bash github_setup.sh https://github.com/zahid/finops.git
# ============================================================

set -e

REPO_URL="$1"

if [ -z "$REPO_URL" ]; then
  echo "❌  Please provide your GitHub repo URL."
  echo "    Usage: bash github_setup.sh https://github.com/YOUR_USERNAME/YOUR_REPO.git"
  exit 1
fi

echo "🚀  Setting up git repository..."

# 1. Initialize
git init
git branch -M main

# 2. Stage all files (respects .gitignore — .env and *.db are excluded)
git add .

# 3. Show what will be committed (safety check)
echo ""
echo "📋  Files to be committed:"
git status --short

echo ""
echo "🔍  Files being EXCLUDED (secrets/databases protected):"
git status --ignored --short | grep "^!!"

# 4. Initial commit
git commit -m "Initial commit: Finance & Accounting Ecosystem

- Multi-agent architecture (accounting manager, controller, FP&A, audit, tax, treasury)
- Adapters for QuickBooks and market data
- REST API with escalation and tax routes
- Offline SQLite + online Postgres sync support
- Data ingestion pipeline (email, API, direct upload)
- Dashboard, reports, and config"

# 5. Add remote and push
git remote add origin "$REPO_URL"
git push -u origin main

echo ""
echo "✅  Done! Your project is now on GitHub: $REPO_URL"
