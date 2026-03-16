# GLP-1 evolution on Google Colab (Option 1)

This repo includes a Colab-first workflow so you can run `evolve_glp1.py` on a free/paid GPU runtime with minimal setup.

## 1) Create Colab runtime
1. Open <https://colab.research.google.com>.
2. Create a new notebook.
3. Set **Runtime → Change runtime type → GPU** (T4 on free tier is fine).

## 2) Clone repo
> If you rerun cells often, use absolute paths and remove existing folder first to avoid nested `autoresearch/autoresearch/...` directories.

```bash
%cd /content
!rm -rf /content/autoresearch
!git clone https://github.com/musicofthings/autoresearch.git /content/autoresearch
%cd /content/autoresearch
```

### Checkout a GLP-1 branch if present
The previous `pathspec ... did not match` error happens when the branch name is not present in that remote. This snippet tries both known branch names and fails early if `evolve_glp1.py` is missing.

```bash
!git fetch --all --prune
!if git show-ref --verify --quiet refs/remotes/origin/glp1-evolution; then git checkout glp1-evolution; elif git show-ref --verify --quiet refs/remotes/origin/codex/set-up-peptide-evolution-lab-using-autoresearch; then git checkout codex/set-up-peptide-evolution-lab-using-autoresearch; else echo "no GLP-1 branch found; staying on default branch"; fi
!test -f evolve_glp1.py || (echo "evolve_glp1.py not found on this branch" && git branch -a && false)
```

## 3) Install dependencies
Use the helper script in this repo:
```bash
!bash scripts/setup_colab.sh
```

## 4) Run evolution
Use `.venv/bin/python` directly (recommended in Colab because each `!` command is a new shell):

Recommended smoke test (10 experiments, no git commits):
```bash
!.venv/bin/python evolve_glp1.py --experiments 10 --no-git-commit
```

Full overnight run with persistent state file:
```bash
!nohup .venv/bin/python evolve_glp1.py --experiments 100 --state-file runs/glp1_state.json > glp1_log.txt 2>&1 &
!tail -n 50 glp1_log.txt
```

## 5) Resume after Colab disconnect
The script persists progress in `runs/glp1_state.json`; rerun with same `--state-file` and target.

```bash
!.venv/bin/python evolve_glp1.py --experiments 100 --state-file runs/glp1_state.json
```

## 6) Optional: push progress to GitHub
```bash
!git config --global user.email "your@email.com"
!git config --global user.name "Your Name"
!git add .
!git commit -m "Colab checkpoint"
!git push origin HEAD
```

## Single-cell quickstart
```python
%cd /content
!rm -rf /content/autoresearch
!git clone https://github.com/musicofthings/autoresearch.git /content/autoresearch
%cd /content/autoresearch
!git fetch --all --prune
!if git show-ref --verify --quiet refs/remotes/origin/glp1-evolution; then git checkout glp1-evolution; elif git show-ref --verify --quiet refs/remotes/origin/codex/set-up-peptide-evolution-lab-using-autoresearch; then git checkout codex/set-up-peptide-evolution-lab-using-autoresearch; else echo "no GLP-1 branch found; staying on default branch"; fi
!test -f evolve_glp1.py || (echo "evolve_glp1.py not found on this branch" && git branch -a && false)
!bash scripts/setup_colab.sh
!.venv/bin/python evolve_glp1.py --experiments 20 --no-git-commit
```


## Fastest fix for feedback-loop setup failures
If Colab keeps failing due to cwd issues, missing branches, or torch not found, run this minimal sequence:

```bash
%cd /content
!rm -rf /content/autoresearch
!git clone https://github.com/musicofthings/autoresearch.git /content/autoresearch
%cd /content/autoresearch
!EXPERIMENTS=10 bash scripts/colab_bootstrap_and_run.sh
```

Or if already cloned:

```bash
%cd /content/autoresearch
!EXPERIMENTS=10 bash scripts/colab_bootstrap_and_run.sh
```

This wrapper script handles:
- `cd /content` before clone
- safe clone into `/content/autoresearch`
- branch fallback (`glp1-evolution` -> `codex/set-up-peptide-evolution-lab-using-autoresearch` -> default)
- dependency setup in `.venv`
- explicit interpreter checks (`.venv/bin/python`, `torch`, CUDA)
- starting `evolve_glp1.py` with the same venv interpreter

## Troubleshooting
- If you hit `getcwd`/`Unable to read current working directory` errors, run the recovery block in `docs/colab_recovery_snippet.md` starting with `%cd /content`.
- If you see `pathspec 'glp1-evolution' did not match`, remove/skip hardcoded branch checkout or use the conditional checkout snippet above.
- If you see `.venv/bin/python: No module named pip`, rerun `!bash scripts/setup_colab.sh` (script now bootstraps pip in `.venv`).
- If you see `Missing dependency: torch`, make sure you run with `!.venv/bin/python ...`.
- If CUDA is unavailable, verify runtime type is GPU and restart the Colab runtime.
