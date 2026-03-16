# GLP-1 evolution on Google Colab (Option 1)

This repo includes a Colab-first workflow so you can run `evolve_glp1.py` on a free/paid GPU runtime with minimal setup.

## 1) Create Colab runtime
1. Open <https://colab.research.google.com>.
2. Create a new notebook.
3. Set **Runtime → Change runtime type → GPU** (T4 on free tier is fine).

## 2) Clone repo and switch branch
```bash
!git clone https://github.com/YOUR_USERNAME/autoresearch.git
%cd autoresearch
!git checkout glp1-evolution
```

## 3) Install dependencies
Use the helper script in this repo:
```bash
!bash scripts/setup_colab.sh
```

## 4) Run evolution
Recommended smoke test (10 experiments, no git commits):
```bash
!source .venv/bin/activate && python evolve_glp1.py --experiments 10 --no-git-commit
```

Full overnight run with persistent state file:
```bash
!source .venv/bin/activate && nohup python evolve_glp1.py --experiments 100 --state-file runs/glp1_state.json > glp1_log.txt 2>&1 &
!tail -n 50 glp1_log.txt
```

## 5) Resume after Colab disconnect
The script persists progress in `runs/glp1_state.json`; rerun with same `--state-file` and higher `--experiments` target.

```bash
!source .venv/bin/activate && python evolve_glp1.py --experiments 100 --state-file runs/glp1_state.json
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
!git clone https://github.com/YOUR_USERNAME/autoresearch.git
%cd autoresearch
!git checkout glp1-evolution
!bash scripts/setup_colab.sh
!source .venv/bin/activate && python evolve_glp1.py --experiments 20 --no-git-commit
```
