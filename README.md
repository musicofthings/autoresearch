# GLP-1 Peptide Evolution Lab

This repository is focused on one purpose: running autonomous, iterative **GLP-1 analog evolution** experiments to optimize half-life-related structural proxies using **ESMFold**.

## What this project does

- Starts from known GLP-1 seed backbones (native, semaglutide-like, liraglutide-like, exenatide).
- Proposes single-amino-acid mutations.
- Scores each candidate with ESMFold-based monomer + peptide/receptor-complex proxy metrics.
- Tracks the best sequence and persists progress to disk so runs can resume after interruption.
- Optionally commits improved candidates to git for experiment traceability.

## Core files

- `evolve_glp1.py` — main mutation/scoring loop and resumable experiment runner.
- `program.md` — autonomous-agent operating prompt for GLP-1 evolution behavior.
- `docs/glp1_colab_option1.md` — Google Colab workflow (recommended quick start).
- `scripts/setup_colab.sh` — one-shot dependency setup script for Colab.

## Quick start (Google Colab)

Use the full guide in `docs/glp1_colab_option1.md`. Minimal flow:

```bash
%cd /content
!rm -rf /content/autoresearch
!git clone https://github.com/musicofthings/autoresearch.git /content/autoresearch
%cd /content/autoresearch
!git fetch --all --prune
!if git show-ref --verify --quiet refs/remotes/origin/glp1-evolution; then git checkout glp1-evolution; elif git show-ref --verify --quiet refs/remotes/origin/codex/set-up-peptide-evolution-lab-using-autoresearch; then git checkout codex/set-up-peptide-evolution-lab-using-autoresearch; else echo "no GLP-1 branch found; staying on default branch"; fi
!test -f evolve_glp1.py || (echo "evolve_glp1.py not found on this branch" && git branch -a && false)
!bash scripts/setup_colab.sh
!.venv/bin/python evolve_glp1.py --experiments 10 --no-git-commit
```

For longer runs, keep the default `--state-file runs/glp1_state.json` so reconnects can resume from the last completed experiment.


### One-command Colab bootstrap (recommended when setup keeps looping)

```bash
%cd /content
!rm -rf /content/autoresearch
!git clone https://github.com/musicofthings/autoresearch.git /content/autoresearch
%cd /content/autoresearch
!EXPERIMENTS=10 bash scripts/colab_bootstrap_and_run.sh
```

This command avoids the common Colab loop (wrong cwd, missing branch, torch installed outside `.venv`, then runtime import failures).

If your notebook is already in a broken cwd state (`getcwd` errors), run the recovery block in `docs/colab_recovery_snippet.md`.

## Local run (GPU machine)

```bash
bash scripts/setup_colab.sh
.venv/bin/python evolve_glp1.py --experiments 100 --state-file runs/glp1_state.json
```

## Notes

- A CUDA GPU is strongly recommended for practical ESMFold throughput.
- The script prints clear install guidance if `torch` or `fair-esm[esmfold]` is missing.

## License

MIT
