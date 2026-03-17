# Colab recovery snippet (fixes broken current working directory)

If you ran `rm -rf /content/autoresearch` while your notebook was currently in that directory, Colab shell commands can fail with:

- `shell-init: error retrieving current directory: getcwd: cannot access parent directories`
- `fatal: Unable to read current working directory`

Run this block once to recover:

```bash
%cd /content
!rm -rf /content/autoresearch
!git clone https://github.com/musicofthings/autoresearch.git /content/autoresearch
%cd /content/autoresearch
!git fetch --all --prune
!if git show-ref --verify --quiet refs/remotes/origin/glp1-evolution; then git checkout glp1-evolution; elif git show-ref --verify --quiet refs/remotes/origin/codex/set-up-peptide-evolution-lab-using-autoresearch; then git checkout codex/set-up-peptide-evolution-lab-using-autoresearch; else echo "no GLP-1 branch found; staying on default branch"; fi
!test -f evolve_glp1.py || (echo "evolve_glp1.py not found on this branch" && git branch -a && false)
!bash scripts/setup_colab.sh
!$(cat .run_python 2>/dev/null || echo python) evolve_glp1.py --strict-esmfold --experiments 10 --no-git-commit
```
