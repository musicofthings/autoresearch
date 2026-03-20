# GLP-1 evolution on AWS SageMaker (GPU notebook)

This runbook replaces the Colab workflow with a stable SageMaker setup.

## 1) Create a GPU notebook instance
In AWS Console:
1. Open **Amazon SageMaker AI**.
2. Create a **Notebook instance** (or Studio JupyterLab with a GPU kernel).
3. Choose a GPU instance type (recommended minimum: `ml.g4dn.xlarge`; faster: `ml.g5.xlarge`+).
4. Start the instance and open Jupyter.

## 2) Open a terminal and clone repo
```bash
cd /home/ec2-user/SageMaker
rm -rf autoresearch
git clone https://github.com/musicofthings/autoresearch.git
cd autoresearch
```

## 3) Checkout GLP-1 branch if available
```bash
git fetch --all --prune
if git show-ref --verify --quiet refs/remotes/origin/glp1-evolution; then
  git checkout glp1-evolution
elif git show-ref --verify --quiet refs/remotes/origin/codex/set-up-peptide-evolution-lab-using-autoresearch; then
  git checkout codex/set-up-peptide-evolution-lab-using-autoresearch
else
  echo "no GLP-1 branch found; staying on default branch"
fi

test -f evolve_glp1.py || (echo "evolve_glp1.py not found on this branch" && git branch -a && exit 1)
```

## 4) Install dependencies (same script, works outside Colab)
```bash
bash scripts/setup_colab.sh
RUN_PYTHON="$(cat .run_python 2>/dev/null || echo python)"
"${RUN_PYTHON}" -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Notes:
- On SageMaker images with Python 3.12, setup auto-switches to a Python 3.10 `.venv` for better OpenFold compatibility.
- OpenFold install is attempted with `--no-build-isolation` so torch is visible during build.

## 5) Run a smoke experiment
```bash
RUN_PYTHON="$(cat .run_python 2>/dev/null || echo python)"
"${RUN_PYTHON}" evolve_glp1.py --strict-esmfold --experiments 5 --no-git-commit
```

## 6) Run long experiment in background
```bash
RUN_PYTHON="$(cat .run_python 2>/dev/null || echo python)"
nohup "${RUN_PYTHON}" evolve_glp1.py --experiments 100 --state-file runs/glp1_state.json > glp1_log.txt 2>&1 &
tail -n 50 glp1_log.txt
```

## 7) Resume after restart/disconnect
```bash
cd /home/ec2-user/SageMaker/autoresearch
RUN_PYTHON="$(cat .run_python 2>/dev/null || echo python)"
"${RUN_PYTHON}" evolve_glp1.py --experiments 100 --state-file runs/glp1_state.json
```

## 8) Optional: strict ESMFold mode
If you want the run to fail instead of heuristic fallback when ESMFold deps are missing:
```bash
RUN_PYTHON="$(cat .run_python 2>/dev/null || echo python)"
"${RUN_PYTHON}" evolve_glp1.py --strict-esmfold --experiments 20 --no-git-commit
```

## 9) Cost controls (important)
- Stop notebook instances when idle.
- Prefer `ml.g4dn.xlarge` for lower cost when iterating.
- Keep logs/state files and push checkpoints to GitHub periodically.

```bash
git add runs/glp1_state.json glp1_log.txt || true
git commit -m "SageMaker checkpoint" || true
git push origin HEAD
```


## Optional: override OpenFold repo/ref
```bash
OPENFOLD_REPO=https://github.com/deepmind/openfold.git OPENFOLD_REF=main bash scripts/setup_colab.sh
```
