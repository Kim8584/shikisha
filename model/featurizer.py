"""
Deterministic Bag-of-Keywords Featurizer for Shikisha.

NOTE: Featurization is executed client-side and is NOT proven in zkVM.
Only the ONNX model computation on the resulting feature vector is verifiable.
"""

import re
import json
import hashlib
from typing import List, Dict, Any, Tuple

# 16 deterministic legal risk keywords
KEYWORDS = [
    "indemnify",
    "liability",
    "damages",
    "breach",
    "terminate",
    "warranty",
    "negligence",
    "dispute",
    "confidential",
    "penalty",
    "default",
    "arbitration",
    "intellectual",
    "exclusive",
    "governing",
    "severability"
]

def featurize(text: str) -> List[float]:
    """
    Extracts a fixed 16-dimensional feature vector based on keyword frequencies.
    Produces float values compatible with ONNX float32 input tensors.
    """
    text_clean = text.lower()
    tokens = re.findall(r"\b[a-z]+\b", text_clean)
    counts = {kw: 0 for kw in KEYWORDS}
    for token in tokens:
        for kw in KEYWORDS:
            # Check prefix or exact match (e.g., indemnification matches indemnify)
            if token.startswith(kw) or kw.startswith(token):
                counts[kw] += 1
    return [float(counts[kw]) for kw in KEYWORDS]

def compute_input_hash(features: List[float]) -> str:
    """
    Computes deterministic SHA-256 hash (hex string with 0x prefix) of the feature vector.
    """
    # Deterministic canonical serialization of numbers
    serialized = json.dumps([round(x, 4) for x in features], separators=(',', ':'))
    h = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
    return "0x" + h

SAMPLE_CLAUSES = [
    {
        "id": "sample_1_low_risk",
        "description": "Standard Severability Clause (Low Risk)",
        "text": "If any provision of this Agreement is held to be invalid or unenforceable, such provision shall be severed and the remaining provisions shall continue in full force and effect."
    },
    {
        "id": "sample_2_medium_risk",
        "description": "Confidentiality and Dispute Governing Clause (Medium Risk)",
        "text": "Each party shall hold all confidential information in strict trust. Any dispute arising under this Agreement shall be settled by binding arbitration in accordance with the governing law."
    },
    {
        "id": "sample_3_high_risk",
        "description": "Unlimited Indemnity and Consequential Damages Clause (High Risk)",
        "text": "The Vendor shall unconditionally indemnify, defend and hold harmless the Client against all liability, damages, breach of contract, negligence, penalties, and default without any monetary limitation."
    }
]

if __name__ == "__main__":
    print("Testing Shikisha Featurizer...")
    for sample in SAMPLE_CLAUSES:
        vec = featurize(sample["text"])
        h = compute_input_hash(vec)
        print(f"\n[{sample['id']}] {sample['description']}")
        print(f"Features: {vec}")
        print(f"InputHash: {h}")
