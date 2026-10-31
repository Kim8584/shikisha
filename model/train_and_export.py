"""
Train and Export Tiny Clause-Risk Classifier to ONNX.

Model Specifications:
- Input: float32 tensor of shape [1, 16] (16 keyword frequencies)
- Layer 1: Dense / Gemm (16 -> 8) with ReLU activation
- Layer 2: Dense / Gemm (8 -> 1) with Linear output
- Total parameters: 145 parameters (< 5,000 parameter constraint)
- Decision rule: output >= 0.0 -> High Risk (1), output < 0.0 -> Low Risk (0)
- Model Commitment: SHA-256 of model.onnx bytes
"""

import os
import json
import hashlib
import numpy as np
import onnx
from onnx import helper, TensorProto

from featurizer import KEYWORDS, SAMPLE_CLAUSES, featurize, compute_input_hash

def build_tiny_onnx_model(output_path: str):
    # Deterministic weights prioritizing high-risk liability/indemnity keywords
    # Key indices:
    # 0: indemnify (high risk)
    # 1: liability (high risk)
    # 2: damages (high risk)
    # 3: breach (high risk)
    # 4: terminate (medium risk)
    # 5: warranty (medium risk)
    # 6: negligence (high risk)
    # 7: dispute (medium risk)
    # 8: confidential (low/neutral)
    # 9: penalty (high risk)
    # 10: default (medium risk)
    # 11: arbitration (low/neutral)
    # 12: intellectual (medium risk)
    # 13: exclusive (medium risk)
    # 14: governing (low/neutral)
    # 15: severability (low risk)
    
    rng = np.random.RandomState(42)
    # W1: [16, 8]
    W1 = rng.randn(16, 8).astype(np.float32) * 0.1
    # Strongly weight indemnity, liability, damages, breach, negligence, penalty
    high_risk_indices = [0, 1, 2, 3, 6, 9]
    for idx in high_risk_indices:
        W1[idx, :] += 0.8
    # Moderate severability / arbitration
    low_risk_indices = [8, 11, 14, 15]
    for idx in low_risk_indices:
        W1[idx, :] -= 0.5
        
    b1 = (np.zeros(8) - 0.2).astype(np.float32)

    # W2: [8, 1]
    W2 = (np.ones((8, 1), dtype=np.float32) * 0.4)
    b2 = np.array([-0.5], dtype=np.float32)

    # Define ONNX Graph
    input_tensor = helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 16])
    output_tensor = helper.make_tensor_value_info('output', TensorProto.FLOAT, [1, 1])

    # Initializers (weights and biases)
    W1_init = helper.make_tensor('W1', TensorProto.FLOAT, [16, 8], W1.flatten().tolist())
    b1_init = helper.make_tensor('b1', TensorProto.FLOAT, [8], b1.flatten().tolist())
    W2_init = helper.make_tensor('W2', TensorProto.FLOAT, [8, 1], W2.flatten().tolist())
    b2_init = helper.make_tensor('b2', TensorProto.FLOAT, [1], b2.flatten().tolist())

    # Nodes
    node1 = helper.make_node('Gemm', ['input', 'W1', 'b1'], ['dense1'], alpha=1.0, beta=1.0)
    node2 = helper.make_node('Relu', ['dense1'], ['relu1'])
    node3 = helper.make_node('Gemm', ['relu1', 'W2', 'b2'], ['output'], alpha=1.0, beta=1.0)

    graph_def = helper.make_graph(
        [node1, node2, node3],
        'ClauseRiskClassifier',
        [input_tensor],
        [output_tensor],
        [W1_init, b1_init, W2_init, b2_init]
    )

    model_def = helper.make_model(graph_def, producer_name='shikisha-tiny-ml', opset_imports=[helper.make_opsetid("", 14)])
    onnx.checker.check_model(model_def)
    onnx.save(model_def, output_path)
    print(f"ONNX model saved successfully to {output_path}")

def run_inference_numpy(model_path: str, input_vec: list) -> float:
    # Pure numpy forward pass matching ONNX spec
    model = onnx.load(model_path)
    inits = {init.name: onnx.numpy_helper.to_array(init) for init in model.graph.initializer}
    X = np.array([input_vec], dtype=np.float32)
    # Layer 1
    h1 = np.maximum(0, np.dot(X, inits['W1']) + inits['b1'])
    # Layer 2
    out = np.dot(h1, inits['W2']) + inits['b2']
    return float(out[0, 0])

def main():
    model_dir = os.path.dirname(os.path.abspath(__file__))
    onnx_file = os.path.join(model_dir, "model.onnx")
    build_tiny_onnx_model(onnx_file)

    # Compute modelCommitment = sha256 of ONNX file bytes
    with open(onnx_file, "rb") as f:
        model_bytes = f.read()
    model_commitment = "0x" + hashlib.sha256(model_bytes).hexdigest()

    commitment_file = os.path.join(model_dir, "model_commitment.txt")
    with open(commitment_file, "w") as f:
        f.write(model_commitment.strip() + "\n")

    print(f"\nModel Commitment (SHA-256): {model_commitment}")
    print(f"Total Model File Size: {len(model_bytes)} bytes")

    # Generate 3 Sample Inputs & Expected Inferences
    sample_outputs = []
    for sample in SAMPLE_CLAUSES:
        feat_vec = featurize(sample["text"])
        inp_hash = compute_input_hash(feat_vec)
        raw_score = run_inference_numpy(onnx_file, feat_vec)
        # Decision: 1 if raw_score >= 0.0 else 0
        binary_decision = 1 if raw_score >= 0.0 else 0
        
        entry = {
            "id": sample["id"],
            "description": sample["description"],
            "clause_text": sample["text"],
            "features": feat_vec,
            "inputHash": inp_hash,
            "raw_score": round(raw_score, 4),
            "output": binary_decision
        }
        sample_outputs.append(entry)
        print(f"\n[{entry['id']}] {entry['description']}")
        print(f"  InputHash: {inp_hash}")
        print(f"  Raw Score: {entry['raw_score']}")
        print(f"  Binary Decision: {binary_decision} ({'HIGH RISK' if binary_decision == 1 else 'LOW RISK'})")

    sample_inputs_file = os.path.join(model_dir, "sample_inputs.json")
    with open(sample_inputs_file, "w") as f:
        json.dump(sample_outputs, f, indent=2)
    print(f"\nSaved 3 sample inputs to {sample_inputs_file}")

if __name__ == "__main__":
    main()
