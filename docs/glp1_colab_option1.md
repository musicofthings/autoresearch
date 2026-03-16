# GLP-1 evolution on Google Colab (Option 1)

This repo includes a Colab-first workflow so you can run `evolve_glp1.py` on a free/paid GPU runtime with minimal setup.

## 1) Create Colab runtime
1. Open <https://colab.research.google.com>.
2. Create a new notebook.
3. Set **Runtime → Change runtime type → GPU** (T4 on free tier is fine).

## 2) Clone repo and switch branch
> If you rerun cells often, use absolute paths and remove existing folder first to avoid nested `autoresearch/autoresearch/...` directories.

```bash
!rm -rf /content/autoresearch
!git clone https://github.com/YOUR_USERNAME/autoresearch.git /content/autoresearch
%cd /content/autoresearch
!git checkout glp1-evolution
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
!git push origin glp1-evolution
```

## Single-cell quickstart
```python
!rm -rf /content/autoresearch
!git clone https://github.com/YOUR_USERNAME/autoresearch.git /content/autoresearch
%cd /content/autoresearch
!git checkout glp1-evolution
!bash scripts/setup_colab.sh
!.venv/bin/python evolve_glp1.py --experiments 20 --no-git-commit
```

## Troubleshooting
- If you see `Missing dependency: torch`, rerun `!bash scripts/setup_colab.sh` and use `!.venv/bin/python ...` to run commands.
- If CUDA is unavailable, verify Colab runtime type is set to GPU and restart runtime.
