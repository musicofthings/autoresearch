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
ALLOW_HEURISTIC_FALLBACK = False
PREDICTOR_MODE = "transformers"  # transformers|heuristic
MODEL_INIT_ATTEMPTED = False
MODEL_INIT_ERROR = None
tokenizer = None

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
    global model, tokenizer, MODEL_MODE, MODEL_INIT_ATTEMPTED, MODEL_INIT_ERROR
    if model is not None and tokenizer is not None:
        return model, tokenizer

    if PREDICTOR_MODE == "heuristic":
        MODEL_MODE = "heuristic"
        return None, None

    if MODEL_INIT_ATTEMPTED:
        if ALLOW_HEURISTIC_FALLBACK:
            return None, None
        raise SystemExit(MODEL_INIT_ERROR)

    MODEL_INIT_ATTEMPTED = True
    try:
        get_torch()
        from transformers import AutoTokenizer, EsmForProteinFolding

        tok = AutoTokenizer.from_pretrained("facebook/esmfold_v1")
        mdl = EsmForProteinFolding.from_pretrained(
            "facebook/esmfold_v1",
            low_cpu_mem_usage=True,
        )
        mdl = mdl.eval().to(device)
        if device.type == "cuda":
            mdl.esm = mdl.esm.half()
        model = mdl
        tokenizer = tok
        MODEL_MODE = "esmfold_transformers"
        return model, tokenizer
    except Exception as exc:
        missing = getattr(exc, "name", exc.__class__.__name__)
        msg = (
            f"ESMFold(transformers) initialization failed ({missing}: {exc})\n"
            "Run:\n"
            "  bash scripts/setup_colab.sh\n"
            "Or manually install:\n"
            "  pip install transformers accelerate biopython torch"
        )
        MODEL_INIT_ERROR = msg
        if ALLOW_HEURISTIC_FALLBACK:
            MODEL_MODE = "heuristic"
            print(
                f"⚠️ ESMFold unavailable ({missing}: {exc}); using heuristic scoring mode for this run."
            )
            return None, None
        raise SystemExit(msg) from exc



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



def mean_plddt_from_output(output, torch_module):
    plddt = output.plddt
    if isinstance(plddt, (list, tuple)):
        plddt = plddt[0]
    if plddt.dim() == 3:
        plddt = plddt.mean(dim=-1)
    if plddt.dim() == 2:
        plddt = plddt[0]
    return plddt


def run_esmfold(sequence: str):
    start = time.time()
    seq_clean = approx_aib(sequence)

    local_model, local_tokenizer = get_model()
    if local_model is None or local_tokenizer is None:
        return run_heuristic(seq_clean)

    torch_module = get_torch()

    # Monomer prediction
    mono_inputs = local_tokenizer([seq_clean], return_tensors="pt", add_special_tokens=False)
    mono_inputs = {k: v.to(device) for k, v in mono_inputs.items()}
    with torch_module.no_grad():
        out_mono = local_model(**mono_inputs)
    mono_plddt = mean_plddt_from_output(out_mono, torch_module)
    plddt_mono = mono_plddt.mean().item()

    # Complex prediction (peptide + linker + ECD)
    complex_seq = seq_clean + LINKER + GLP1R_ECD
    comp_inputs = local_tokenizer([complex_seq], return_tensors="pt", add_special_tokens=False)
    comp_inputs = {k: v.to(device) for k, v in comp_inputs.items()}
    with torch_module.no_grad():
        out_comp = local_model(**comp_inputs)
    comp_plddt = mean_plddt_from_output(out_comp, torch_module)

    # Proxy for interface confidence: lower penalty when ECD side has high confidence
    peptide_len = len(seq_clean)
    if comp_plddt.numel() > peptide_len:
        ecd_conf = comp_plddt[peptide_len:].mean().item()
        interface_pae = max(1.0, min(35.0, 100.0 - ecd_conf))
    else:
        interface_pae = max(1.0, min(35.0, 100.0 - comp_plddt.mean().item()))

    runtime = time.time() - start

    # Simple helix proxy: average pLDDT in positions 10-30 (core helix)
    helix_plddt = mono_plddt[9:30].mean().item() if mono_plddt.numel() > 30 else plddt_mono

    return {
        "avg_plddt": plddt_mono,
        "helix_plddt": helix_plddt,
        "interface_pae": interface_pae,
        "runtime_sec": runtime,
        "predictor": "esmfold_transformers",
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
        "--predictor-mode",
        choices=["transformers", "heuristic"],
        default="transformers",
        help="Predictor backend mode: transformers (default) or heuristic.",
    )
    parser.add_argument(
        "--strict-esmfold",
        action="store_true",
        help="Fail if transformers ESMFold dependencies are missing instead of heuristic fallback.",
    )
    return parser.parse_args()


# ====================== MAIN EXPERIMENT LOOP ======================
if __name__ == "__main__":
    args = parse_args()
    random.seed(args.seed)

    ALLOW_HEURISTIC_FALLBACK = not args.strict_esmfold
    PREDICTOR_MODE = args.predictor_mode

    state = load_state(args.state_file)
    best_seq = state.get("best_seq", CURRENT_SEQ)
    best_score = float(state.get("best_score", 0.0))
    experiment = int(state.get("experiment", 0))
    history = list(state.get("history", []))

    print("🚀 Starting GLP-1 autoresearch evolution loop (ESMFold)")
    print(f"State file: {args.state_file}")
    print(f"Starting from experiment {experiment} / {args.experiments}")
    print(f"Predictor mode: {PREDICTOR_MODE}")

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
