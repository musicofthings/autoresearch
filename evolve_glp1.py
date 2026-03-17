import argparse
import json
import os
import random
import subprocess
import time
from pathlib import Path

# ========================= CONFIG =========================
torch = None
device = None
model = None
MODEL_MODE = "unknown"
ALLOW_HEURISTIC_FALLBACK = True

HYDROPHOBIC = set("AILMFWVY")
CHARGED = set("DEKRH")

CURRENT_SEQ = "HAEGTFTSDVSSYLEGQAAKEFIAWLVRGRG"  # semaglutide-like backbone (best starter)

# GLP-1R ECD (residues 24-139, human UniProt P43220) – minimal binding domain
GLP1R_ECD = "RAGPRPQGATVSLWETVQKWREYRRQCQRSLTEDPPPATDLFCNRTFDEYACWPDGEPGSFVNVSCPWYLPWASSVPQGHVYRFCTAEGLWLQKDNSSLPWRDLSECEESKRGERSSPEEQLLFL"

LINKER = "GGGGGGGGGGG"  # flexible Gly10 linker for complex

SEEDS = [
    "HAEGTFTSDVSSYLEGQAAKEFIAWLVKGRG",  # native
    "HAEGTFTSDVSSYLEGQAAKEFIAWLVRGRG",  # semaglutide-like
    "HAEGTFTSDVSSYLEGQAAKEEFIAWLVRGRG",  # liraglutide-like
    "HGEGTFTSDLSKQMEEEAVRLFIEWLKNGGPSSGAPPPS",  # exenatide
]

AA_LIST = list("ACDEFGHIKLMNPQRSTVWY")  # 20 canonical (Aib added later by agent)


def get_torch():
    global torch, device
    if torch is not None:
        return torch
    try:
        import torch as torch_module
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency: torch. Install with your environment manager, e.g.: "
            "uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
        ) from exc
    torch = torch_module
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    return torch



def get_model():
    global model, MODEL_MODE
    if model is not None:
        return model
    try:
        import esm
        get_torch()
        loaded = esm.pretrained.esmfold_v1()
        loaded = loaded.eval().to(device)
        model = loaded
        MODEL_MODE = "esmfold"
        return model
    except Exception as exc:
        missing = getattr(exc, "name", exc.__class__.__name__)
        if ALLOW_HEURISTIC_FALLBACK:
            MODEL_MODE = "heuristic"
            print(
                f"⚠️ ESMFold unavailable ({missing}: {exc}); falling back to heuristic scoring mode. "
                "Use setup_colab.sh to install full ESMFold dependencies."
            )
            return None
        raise SystemExit(
            f"ESMFold initialization failed ({missing}: {exc})\n"
            "Run:\n"
            "  bash scripts/setup_colab.sh\n"
            "Or manually install:\n"
            "  pip install \"fair-esm[esmfold]\"\n"
            "  pip install \"dllogger @ git+https://github.com/NVIDIA/dllogger.git\"\n"
            "  pip install \"openfold @ git+https://github.com/aqlaboratory/openfold.git@4b41059694619831a7db195b7e0988fc4ff3a307\""
        ) from exc



def approx_aib(seq: str) -> str:
    return seq.replace("[Aib]", "A").replace("X", "A")




def run_heuristic(sequence: str):
    start = time.time()
    seq_clean = approx_aib(sequence)
    length = max(len(seq_clean), 1)
    hydrophobic_frac = sum(aa in HYDROPHOBIC for aa in seq_clean) / length
    charged_frac = sum(aa in CHARGED for aa in seq_clean) / length
    gly_pro_frac = sum(aa in {"G", "P"} for aa in seq_clean) / length

    avg_plddt = 65 + 20 * hydrophobic_frac - 8 * gly_pro_frac
    helix_plddt = 62 + 18 * hydrophobic_frac - 10 * gly_pro_frac
    # lower is better; keep in a plausible range
    interface_pae = 22 - 6 * charged_frac + 4 * gly_pro_frac

    runtime = time.time() - start
    return {
        "avg_plddt": float(max(20, min(95, avg_plddt))),
        "helix_plddt": float(max(20, min(95, helix_plddt))),
        "interface_pae": float(max(1, min(35, interface_pae))),
        "runtime_sec": runtime,
        "predictor": "heuristic",
    }


def run_esmfold(sequence: str):
    start = time.time()
    seq_clean = approx_aib(sequence)

    local_model = get_model()
    if local_model is None:
        return run_heuristic(seq_clean)

    torch_module = get_torch()

    # Monomer prediction
    with torch_module.no_grad():
        out_mono = local_model.infer([seq_clean])[0]
    plddt_mono = out_mono["plddt"].mean().item()

    # Complex prediction (peptide + linker + ECD)
    complex_seq = seq_clean + LINKER + GLP1R_ECD
    with torch_module.no_grad():
        out_comp = local_model.infer([complex_seq])[0]

    # Interface proxy: mean PAE on first ~len(peptide) residues vs ECD part
    pae = out_comp.get("predicted_aligned_error", torch_module.zeros(1)).mean().item()
    interface_pae = pae  # lower = better binding

    runtime = time.time() - start

    # Simple helix proxy: average pLDDT in positions 10-30 (core helix)
    helix_plddt = out_mono["plddt"][9:30].mean().item() if len(out_mono["plddt"]) > 30 else plddt_mono

    return {
        "avg_plddt": plddt_mono,
        "helix_plddt": helix_plddt,
        "interface_pae": interface_pae,
        "runtime_sec": runtime,
        "predictor": "esmfold",
    }


def compute_fitness(metrics: dict) -> float:
    """Starter fitness – agent will heavily evolve this"""
    score = (
        0.45 * metrics["avg_plddt"]
        + 0.25 * metrics["helix_plddt"]
        + 0.25 * (100 - metrics["interface_pae"])
        + 0.05 * (300 - metrics["runtime_sec"]) / 300
    )
    return round(score, 4)


def propose_mutation(seq: str) -> str:
    """Simple random single-AA mutation – agent will make this smart"""
    if not seq:
        return random.choice(SEEDS)
    pos = random.randint(0, len(seq) - 1)
    new_aa = random.choice(AA_LIST)
    return seq[:pos] + new_aa + seq[pos + 1 :]


def git_commit(message: str):
    try:
        subprocess.run(["git", "add", "evolve_glp1.py", "program.md"], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        print(f"✅ Committed: {message}")
    except Exception:
        print("⚠️ Git commit skipped (not in repo or error)")


def load_state(state_path: Path):
    if not state_path.exists():
        return {"best_seq": CURRENT_SEQ, "best_score": 0.0, "experiment": 0, "history": []}
    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    return state


def save_state(state_path: Path, state: dict):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, state_path)


def parse_args():
    parser = argparse.ArgumentParser(description="Run GLP-1 ESMFold evolution loop.")
    parser.add_argument("--experiments", type=int, default=100, help="Total number of experiments to run.")
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("runs/glp1_state.json"),
        help="Path to persistent run state (useful on Colab reconnects).",
    )
    parser.add_argument(
        "--no-git-commit",
        action="store_true",
        help="Disable git commits during evolution (recommended for quick Colab smoke tests).",
    )
    parser.add_argument("--seed", type=int, default=1337, help="Random seed for reproducibility.")
    parser.add_argument(
        "--strict-esmfold",
        action="store_true",
        help="Fail if ESMFold dependencies are missing instead of heuristic fallback.",
    )
    return parser.parse_args()


# ====================== MAIN EXPERIMENT LOOP ======================
if __name__ == "__main__":
    args = parse_args()
    random.seed(args.seed)

    ALLOW_HEURISTIC_FALLBACK = not args.strict_esmfold

    state = load_state(args.state_file)
    best_seq = state.get("best_seq", CURRENT_SEQ)
    best_score = float(state.get("best_score", 0.0))
    experiment = int(state.get("experiment", 0))
    history = list(state.get("history", []))

    print("🚀 Starting GLP-1 autoresearch evolution loop (ESMFold)")
    print(f"State file: {args.state_file}")
    print(f"Starting from experiment {experiment} / {args.experiments}")

    while experiment < args.experiments:
        experiment += 1
        print(f"\n--- Experiment {experiment} ---")

        mutated = propose_mutation(best_seq)
        metrics = run_esmfold(mutated)
        score = compute_fitness(metrics)

        print(f"Mutant: {mutated}")
        print(
            "Metrics: "
            f"pLDDT={metrics['avg_plddt']:.1f} | "
            f"Helix={metrics['helix_plddt']:.1f} | "
            f"PAE={metrics['interface_pae']:.1f} | "
            f"Time={metrics['runtime_sec']:.1f}s | "
            f"Predictor={metrics.get('predictor','unknown')}"
        )
        print(f"Score: {score:.4f} (best so far: {best_score:.4f})")

        improved = score > best_score and metrics["runtime_sec"] < 300
        history.append(
            {
                "experiment": experiment,
                "candidate": mutated,
                "score": score,
                "improved": improved,
                "metrics": metrics,
            }
        )

        if improved:
            best_seq = mutated
            best_score = score
            msg = (
                f"Exp {experiment}: {mutated} -> score {score:.4f} "
                f"(pLDDT={metrics['avg_plddt']:.1f}, "
                f"helix={metrics['helix_plddt']:.1f}, PAE={metrics['interface_pae']:.1f})"
            )
            if not args.no_git_commit:
                git_commit(msg)
            print("🎉 NEW BEST!")
        else:
            print("❌ Reverted (no improvement or too slow)")

        state = {
            "best_seq": best_seq,
            "best_score": best_score,
            "experiment": experiment,
            "history": history,
        }
        save_state(args.state_file, state)

        time.sleep(0.5)  # tiny cooldown

    print("\n✅ Evolution complete. Review state JSON and git history for evolved GLP-1 candidates!")
