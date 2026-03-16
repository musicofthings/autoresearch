#!/usr/bin/env bash
set -euo pipefail

# Use notebook Python for uv bootstrap, then install all runtime deps directly
# into .venv to avoid accidental system-site installs.
python -m pip install --upgrade pip
python -m pip install --upgrade uv

if [ -d ".venv" ]; then
  echo "ℹ️ Reusing existing .venv"
else
  uv venv .venv --python 3.10
fi

VENV_PYTHON=".venv/bin/python"
"${VENV_PYTHON}" -m pip install --upgrade pip
"${VENV_PYTHON}" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
"${VENV_PYTHON}" -m pip install "fair-esm[esmfold]" biopython

"${VENV_PYTHON}" - <<'PY'
import torch
print(f"✅ torch import ok ({torch.__version__})")
print(f"✅ cuda available: {torch.cuda.is_available()}")
PY

echo "✅ Colab environment setup complete. Run with: .venv/bin/python evolve_glp1.py --experiments 10 --no-git-commit"
