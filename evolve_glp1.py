import torch
import esm
import time
import random
import subprocess
from pathlib import Path

# ========================= CONFIG =========================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load ESMFold once (v1 is the best)
model = esm.pretrained.esmfold_v1()
model = model.eval().to(device)
# Optional: model.set_chunk_size(128)  # faster on short peptides

CURRENT_SEQ = "HAEGTFTSDVSSYLEGQAAKEFIAWLVRGRG"  # semaglutide-like backbone (best starter)

# GLP-1R ECD (residues 24-139, human UniProt P43220) – minimal binding domain
GLP1R_ECD = "RAGPRPQGATVSLWETVQKWREYRRQCQRSLTEDPPPATDLFCNRTFDEYACWPDGEPGSFVNVSCPWYLPWASSVPQGHVYRFCTAEGLWLQKDNSSLPWRDLSECEESKRGERSSPEEQLLFL"

LINKER = "GGGGGGGGGGG"  # flexible Gly10 linker for complex

SEEDS = [
    "HAEGTFTSDVSSYLEGQAAKEFIAWLVKGRG",      # native
    "HAEGTFTSDVSSYLEGQAAKEFIAWLVRGRG",      # semaglutide-like
    "HAEGTFTSDVSSYLEGQAAKEEFIAWLVRGRG",     # liraglutide-like
    "HGEGTFTSDLSKQMEEEAVRLFIEWLKNGGPSSGAPPPS",  # exenatide
]

AA_LIST = list("ACDEFGHIKLMNPQRSTVWY")  # 20 canonical (Aib added later by agent)

def approx_aib(seq: str) -> str:
    return seq.replace("[Aib]", "A").replace("X", "A")

def run_esmfold(sequence: str):
    start = time.time()
    seq_clean = approx_aib(sequence)

    # Monomer prediction
    with torch.no_grad():
        out_mono = model.infer([seq_clean])[0]
    plddt_mono = out_mono["plddt"].mean().item()

    # Complex prediction (peptide + linker + ECD)
    complex_seq = seq_clean + LINKER + GLP1R_ECD
    with torch.no_grad():
        out_comp = model.infer([complex_seq])[0]

    # Interface proxy: mean PAE on first ~len(peptide) residues vs ECD part
    pae = out_comp.get("predicted_aligned_error", torch.zeros(1)).mean().item()
    interface_pae = pae  # lower = better binding

    runtime = time.time() - start

    # Simple helix proxy: average pLDDT in positions 10-30 (core helix)
    helix_plddt = out_mono["plddt"][9:30].mean().item() if len(out_mono["plddt"]) > 30 else plddt_mono

    return {
        "avg_plddt": plddt_mono,
        "helix_plddt": helix_plddt,
        "interface_pae": interface_pae,
        "runtime_sec": runtime,
    }

def compute_fitness(metrics: dict) -> float:
    """Starter fitness – agent will heavily evolve this"""
    score = (
        0.45 * metrics["avg_plddt"] +          # stability
        0.25 * metrics["helix_plddt"] +        # helical content
        0.25 * (100 - metrics["interface_pae"]) +  # binding strength
        0.05 * (300 - metrics["runtime_sec"]) / 300  # speed bonus
    )
    return round(score, 4)

def propose_mutation(seq: str) -> str:
    """Simple random single-AA mutation – agent will make this smart"""
    if not seq:
        return random.choice(SEEDS)
    pos = random.randint(0, len(seq) - 1)
    new_aa = random.choice(AA_LIST)
    return seq[:pos] + new_aa + seq[pos + 1:]

def git_commit(message: str):
    try:
        subprocess.run(["git", "add", "evolve_glp1.py"], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        print(f"✅ Committed: {message}")
    except:
        print("⚠️ Git commit skipped (not in repo or error)")

# ====================== MAIN EXPERIMENT LOOP ======================
if __name__ == "__main__":
    print("🚀 Starting GLP-1 autoresearch evolution loop (ESMFold)")
    best_seq = CURRENT_SEQ
    best_score = 0.0
    experiment = 0

    while experiment < 100:  # agent can change this
        experiment += 1
        print(f"\n--- Experiment {experiment} ---")

        mutated = propose_mutation(best_seq)
        metrics = run_esmfold(mutated)
        score = compute_fitness(metrics)

        print(f"Mutant: {mutated}")
        print(f"Metrics: pLDDT={metrics['avg_plddt']:.1f} | Helix={metrics['helix_plddt']:.1f} | PAE={metrics['interface_pae']:.1f} | Time={metrics['runtime_sec']:.1f}s")
        print(f"Score: {score:.4f} (best so far: {best_score:.4f})")

        if score > best_score and metrics["runtime_sec"] < 300:
            best_seq = mutated
            best_score = score
            msg = f"Exp {experiment}: {mutated} → score {score:.4f} (pLDDT={metrics['avg_plddt']:.1f}, helix={metrics['helix_plddt']:.1f}, PAE={metrics['interface_pae']:.1f})"
            git_commit(msg)
            print(f"🎉 NEW BEST! Saved to git.")
        else:
            print("❌ Reverted (no improvement or too slow)")

        time.sleep(0.5)  # tiny cooldown

    print("\n✅ 100 experiments complete. Review git history for the evolved GLP-1 candidates!")
