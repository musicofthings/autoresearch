#!/usr/bin/env bash
set -euo pipefail

# Reliability modes:
# - default USE_VENV=0
# - set USE_VENV=1 for isolated deps in .venv
# - on Python >=3.12, auto-switch to USE_VENV=1 (Python 3.10) for OpenFold compatibility
USE_VENV="${USE_VENV:-0}"
RUN_PYTHON="python"
OPENFOLD_REPO="${OPENFOLD_REPO:-https://github.com/deepmind/openfold.git}"
OPENFOLD_REF="${OPENFOLD_REF:-main}"
OPENFOLD_FALLBACK_REPO="${OPENFOLD_FALLBACK_REPO:-https://github.com/aqlaboratory/openfold.git}"
OPENFOLD_FALLBACK_REF="${OPENFOLD_FALLBACK_REF:-4b41059694619831a7db195b7e0988fc4ff3a307}"
REQUIRE_ESMFOLD="${REQUIRE_ESMFOLD:-1}"
echo "${RUN_PYTHON}" > .run_python

python -m pip install --upgrade pip
python -m pip install --upgrade uv

PYVER=$(python - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)

if [ "${USE_VENV}" = "0" ] && python - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
then
  echo "ℹ️ Detected Python ${PYVER}; enabling USE_VENV=1 for OpenFold compatibility."
  USE_VENV="1"
fi

if [ "${USE_VENV}" = "1" ]; then
  if [ -d ".venv" ]; then
    echo "ℹ️ Reusing existing .venv"
  else
    uv venv .venv --python 3.10
  fi
  RUN_PYTHON=".venv/bin/python"
  echo "${RUN_PYTHON}" > .run_python
  "${RUN_PYTHON}" -m ensurepip --upgrade >/dev/null 2>&1 || true
  uv pip install --python "${RUN_PYTHON}" --upgrade pip setuptools wheel
fi

# Core runtime deps (required)
if "${RUN_PYTHON}" -c "import torch" >/dev/null 2>&1; then
  echo "ℹ️ torch already available in ${RUN_PYTHON}"
else
  "${RUN_PYTHON}" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
fi

# ESMFold stack installs (best effort); final import gate below enforces pass/fail.
if ! "${RUN_PYTHON}" -m pip install "fair-esm[esmfold]" biopython; then
  echo "⚠️ fair-esm install step failed"
fi
if ! "${RUN_PYTHON}" -m pip install "dllogger @ git+https://github.com/NVIDIA/dllogger.git"; then
  echo "⚠️ dllogger install step failed"
fi
if ! "${RUN_PYTHON}" -m pip install --no-build-isolation "openfold @ git+${OPENFOLD_REPO}@${OPENFOLD_REF}"; then
  echo "⚠️ primary openfold install failed (${OPENFOLD_REPO}@${OPENFOLD_REF}); trying fallback mirror."
  if ! "${RUN_PYTHON}" -m pip install --no-build-isolation "openfold @ git+${OPENFOLD_FALLBACK_REPO}@${OPENFOLD_FALLBACK_REF}"; then
    echo "⚠️ fallback openfold install failed; trying fallback mirror head."
    if ! "${RUN_PYTHON}" -m pip install --no-build-isolation "openfold @ git+${OPENFOLD_FALLBACK_REPO}"; then
      echo "⚠️ openfold install failed"
    fi
  fi
fi

# Verify imports from same interpreter used for run.
STATUS=0
"${RUN_PYTHON}" - <<'PY' || STATUS=$?
import sys
import torch
print(f"✅ python executable: {sys.executable}")
print(f"✅ torch import ok ({torch.__version__})")
print(f"✅ cuda available: {torch.cuda.is_available()}")

esm_ok = True
openfold_ok = True

try:
    import esm
    print(f"✅ esm import ok ({getattr(esm, '__version__', 'unknown')})")
except Exception as e:
    esm_ok = False
    print(f"⚠️ esm import unavailable: {e}")

try:
    import openfold
    print(f"✅ openfold import ok ({getattr(openfold, '__version__', 'unknown')})")
except Exception as e:
    openfold_ok = False
    print(f"⚠️ openfold import unavailable: {e}")

if not (esm_ok and openfold_ok):
    raise SystemExit(42)
PY

echo "${RUN_PYTHON}" > .run_python
if [ "${STATUS}" -eq 42 ] && [ "${REQUIRE_ESMFOLD}" = "1" ]; then
  echo "❌ ESMFold stack not ready (esm/openfold import failed)."
  echo "   Fix environment and re-run: bash scripts/setup_colab.sh"
  echo "   If you intentionally want heuristic mode, run: REQUIRE_ESMFOLD=0 bash scripts/setup_colab.sh"
  exit 1
fi

echo "✅ Setup complete. Run with: $(cat .run_python 2>/dev/null || echo python) evolve_glp1.py --strict-esmfold --experiments 10 --no-git-commit"
