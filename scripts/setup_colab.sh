#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install uv
uv venv .venv
source .venv/bin/activate
uv pip install --upgrade pip
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
uv pip install "fair-esm[esmfold]" biopython

echo "✅ Colab environment setup complete. Activate with: source .venv/bin/activate"
