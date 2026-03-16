#!/usr/bin/env bash
set -euo pipefail

# Deterministic Colab bootstrap to avoid cwd/branch/venv feedback loops.
REPO_URL="${REPO_URL:-https://github.com/musicofthings/autoresearch.git}"
TARGET_DIR="${TARGET_DIR:-/content/autoresearch}"
PREFERRED_BRANCH="${PREFERRED_BRANCH:-glp1-evolution}"
FALLBACK_BRANCH="${FALLBACK_BRANCH:-codex/set-up-peptide-evolution-lab-using-autoresearch}"
EXPERIMENTS="${EXPERIMENTS:-10}"

mkdir -p /content
cd /content

rm -rf "${TARGET_DIR}"
git clone "${REPO_URL}" "${TARGET_DIR}"
cd "${TARGET_DIR}"

git fetch --all --prune
if git show-ref --verify --quiet "refs/remotes/origin/${PREFERRED_BRANCH}"; then
  git checkout "${PREFERRED_BRANCH}"
elif git show-ref --verify --quiet "refs/remotes/origin/${FALLBACK_BRANCH}"; then
  git checkout "${FALLBACK_BRANCH}"
else
  echo "⚠️ Preferred branches not found; staying on default branch $(git branch --show-current)"
fi

if [ ! -f evolve_glp1.py ]; then
  echo "❌ evolve_glp1.py not found on checked out branch."
  git branch -a
  exit 1
fi

bash scripts/setup_colab.sh

RUN_PYTHON="$(cat .run_python 2>/dev/null || echo python)"

# Verify interpreter and torch import before running long loop.
"${RUN_PYTHON}" - <<'PY'
import sys
import torch
print(f"✅ python: {sys.executable}")
print(f"✅ torch: {torch.__version__}")
print(f"✅ cuda available: {torch.cuda.is_available()}")
PY

"${RUN_PYTHON}" evolve_glp1.py --experiments "${EXPERIMENTS}" --no-git-commit
