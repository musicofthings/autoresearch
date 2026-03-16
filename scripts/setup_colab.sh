#!/usr/bin/env bash
set -euo pipefail

# Bootstrap tooling in notebook interpreter.
python -m pip install --upgrade pip
python -m pip install --upgrade uv

# Create or reuse project venv.
if [ -d ".venv" ]; then
  echo "ℹ️ Reusing existing .venv"
else
  uv venv .venv --python 3.10
fi

VENV_PYTHON=".venv/bin/python"

# Some uv-created envs in Colab may not have pip pre-seeded; ensure it's present.
"${VENV_PYTHON}" -m ensurepip --upgrade >/dev/null 2>&1 || true

# Install packages directly into .venv regardless of current shell activation.
uv pip install --python "${VENV_PYTHON}" --upgrade pip
uv pip install --python "${VENV_PYTHON}" torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
uv pip install --python "${VENV_PYTHON}" "fair-esm[esmfold]" biopython

# Verify runtime imports from the venv interpreter.
"${VENV_PYTHON}" - <<'PY'
import torch
print(f"✅ torch import ok ({torch.__version__})")
print(f"✅ cuda available: {torch.cuda.is_available()}")
PY

echo "✅ Colab setup complete. Run with: .venv/bin/python evolve_glp1.py --experiments 10 --no-git-commit"
