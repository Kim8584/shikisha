#!/usr/bin/env python3
"""
Receipt and Proof Generator for Shikisha.

Runs Jolt Atlas proving under `timeout 600`.
Outputs receipts adhering strictly to the schema:
{
  "modelCommitment": "0x...",
  "inputHash": "0x...",
  "output": 1,
  "proofHash": "0x...",
  "proofStatus": "GENERATED_VERIFIED" | "GENERATED_UNVERIFIED" | "NOT_GENERATED",
  "timestamp": 1740000000,
  "proofURI": "/prover/out/proof_sample_1_low_risk.log"
}
"""

import os
import sys
import json
import time
import shutil
import hashlib
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVER_DIR = os.path.join(REPO_ROOT, "prover")
OUT_DIR = os.path.join(PROVER_DIR, "out")
MODEL_DIR = os.path.join(REPO_ROOT, "model")
BIN_PROVER = os.path.join(REPO_ROOT, "bin", "jolt-prove")

os.makedirs(OUT_DIR, exist_ok=True)

def run_jolt_prover(model_onnx_path: str, proof_output_path: str, timeout_seconds=600):
    """
    Executes Jolt Atlas proving on the model directory with timeout.
    """
    temp_dir = os.path.join(PROVER_DIR, ".tmp_model_run")
    os.makedirs(temp_dir, exist_ok=True)
    target_onnx = os.path.join(temp_dir, "network.onnx")
    shutil.copyfile(model_onnx_path, target_onnx)

    cmd = ["timeout", str(timeout_seconds), BIN_PROVER, "--model", temp_dir]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds + 5
        )
        output = proc.stdout + "\n" + proc.stderr
        with open(proof_output_path, "w") as f:
            f.write(output)

        if proc.returncode == 0 and "Proof verified successfully!" in output:
            return True, output
        else:
            return False, output
    except Exception as e:
        with open(proof_output_path, "w") as f:
            f.write(f"Execution error: {str(e)}")
        return False, str(e)

def compute_sha256_file(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return "0x" + hashlib.sha256(f.read()).hexdigest()

def main():
    sample_inputs_path = os.path.join(MODEL_DIR, "sample_inputs.json")
    with open(sample_inputs_path, "r") as f:
        samples = json.load(f)

    commitment_file = os.path.join(MODEL_DIR, "model_commitment.txt")
    with open(commitment_file, "r") as f:
        model_commitment = f.read().strip()

    onnx_file = os.path.join(MODEL_DIR, "model.onnx")

    receipts = []

    print(f"=== Shikisha Prover: Generating Receipts for {len(samples)} Samples ===")
    print(f"Model Commitment: {model_commitment}\n")

    for sample in samples:
        sample_id = sample["id"]
        inp_hash = sample["inputHash"]
        decision = sample["output"]
        proof_log = os.path.join(OUT_DIR, f"proof_{sample_id}.log")

        print(f"Running Jolt Atlas prover for {sample_id}...")
        success, log = run_jolt_prover(onnx_file, proof_log)

        timestamp = int(time.time())

        if success:
            proof_hash = compute_sha256_file(proof_log)
            proof_status = "GENERATED_VERIFIED"
            print(f"  [SUCCESS] Jolt Atlas proof generated & verified locally.")
            print(f"  Proof Hash: {proof_hash}")
        else:
            print(f"  [FAILURE] Proving failed or timed out. Recording NOT_GENERATED.")
            proof_hash = "0x" + "0" * 64
            proof_status = "NOT_GENERATED"

        receipt = {
            "id": sample_id,
            "description": sample["description"],
            "modelCommitment": model_commitment,
            "inputHash": inp_hash,
            "output": decision,
            "proofHash": proof_hash,
            "proofStatus": proof_status,
            "timestamp": timestamp,
            "proofURI": os.path.relpath(proof_log, REPO_ROOT)
        }

        receipt_file = os.path.join(PROVER_DIR, f"receipt_{sample_id}.json")
        with open(receipt_file, "w") as f:
            json.dump(receipt, f, indent=2)

        receipts.append(receipt)
        print(f"  Wrote receipt to {os.path.basename(receipt_file)}\n")

    all_receipts_path = os.path.join(PROVER_DIR, "receipts.json")
    with open(all_receipts_path, "w") as f:
        json.dump(receipts, f, indent=2)

    print(f"All receipts generated successfully in {PROVER_DIR}")

if __name__ == "__main__":
    main()
