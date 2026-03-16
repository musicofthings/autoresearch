#!/usr/bin/env bash
set -euo pipefail

# Colab reliability mode:
# - default USE_VENV=0 to avoid interpreter mismatch (most common torch error cause)
# - set USE_VENV=1 if you explicitly want isolated deps in .venv
USE_VENV="${USE_VENV:-0}"

# Always set a fallback runner early so callers can proceed even if setup fails midway.
RUN_PYTHON="python"
echo "${RUN_PYTHON}" > .run_python

python -m pip install --upgrade pip
python -m pip install --upgrade uv

if [ "${USE_VENV}" = "1" ]; then
  if [ -d ".venv" ]; then
    echo "ℹ️ Reusing existing .venv"
  else
    uv venv .venv --python 3.10
  fi
  RUN_PYTHON=".venv/bin/python"
  echo "${RUN_PYTHON}" > .run_python
  "${RUN_PYTHON}" -m ensurepip --upgrade >/dev/null 2>&1 || true
  uv pip install --python "${RUN_PYTHON}" --upgrade pip
  uv pip install --python "${RUN_PYTHON}" torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
  uv pip install --python "${RUN_PYTHON}" "fair-esm[esmfold]" biopython
else
  # Colab already ships torch; keep this idempotent and only add missing deps.
  "${RUN_PYTHON}" -m pip install "fair-esm[esmfold]" biopython
fi

# Verify runtime imports from the same interpreter that will execute evolve_glp1.py
"${RUN_PYTHON}" - <<'PY'
import sys
import torch
print(f"✅ python executable: {sys.executable}")
print(f"✅ torch import ok ({torch.__version__})")
print(f"✅ cuda available: {torch.cuda.is_available()}")
PY

echo "${RUN_PYTHON}" > .run_python
echo "✅ Colab setup complete. Run with: $(cat .run_python 2>/dev/null || echo python) evolve_glp1.py --experiments 10 --no-git-commit"
