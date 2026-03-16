#!/usr/bin/env bash
set -euo pipefail

# Colab reliability mode:
# - default USE_VENV=0 to avoid interpreter mismatch
# - set USE_VENV=1 for isolated deps in .venv
USE_VENV="${USE_VENV:-0}"
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
fi

# Core runtime deps
if "${RUN_PYTHON}" -c "import torch" >/dev/null 2>&1; then
  echo "ℹ️ torch already available in ${RUN_PYTHON}"
else
  "${RUN_PYTHON}" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
fi

# ESMFold official dependency path
"${RUN_PYTHON}" -m pip install "fair-esm[esmfold]" biopython
"${RUN_PYTHON}" -m pip install "dllogger @ git+https://github.com/NVIDIA/dllogger.git"
if ! "${RUN_PYTHON}" -m pip install "openfold @ git+https://github.com/aqlaboratory/openfold.git@4b41059694619831a7db195b7e0988fc4ff3a307"; then
  # Fallback to head if pinned commit fails in environment
  "${RUN_PYTHON}" -m pip install "openfold @ git+https://github.com/aqlaboratory/openfold.git"
fi

# Verify imports from same interpreter used for run
"${RUN_PYTHON}" - <<'PY'
import sys
import torch
import esm
import openfold
print(f"✅ python executable: {sys.executable}")
print(f"✅ torch import ok ({torch.__version__})")
print(f"✅ esm import ok ({getattr(esm, '__version__', 'unknown')})")
print(f"✅ openfold import ok ({getattr(openfold, '__version__', 'unknown')})")
print(f"✅ cuda available: {torch.cuda.is_available()}")
PY

echo "${RUN_PYTHON}" > .run_python
echo "✅ Colab setup complete. Run with: $(cat .run_python 2>/dev/null || echo python) evolve_glp1.py --experiments 10 --no-git-commit"
