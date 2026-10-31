# ASSUMPTIONS

1. **Deterministic Featurizer Scope**:
   - The featurizer runs off-chain on raw legal clause text using a deterministic bag-of-keywords algorithm with fixed vocabulary and integer frequency counts.
   - Featurization itself is NOT proven in zkVM; only the ONNX model computation on the fixed feature vector is verifiable.

2. **Model Design & Sizing**:
   - The clause-risk classifier is a tiny linear/MLP model ($\le 5\text{k}$ parameters, 16 features) exported to ONNX to respect machine performance constraints.
   - The `modelCommitment` is the SHA-256 hash of the exact `.onnx` file bytes.

3. **Proof Verification & Attestation Flow**:
   - Prover execution is bounded by a 10-minute timeout (`timeout 600`) and a memory cap.
   - If proving cannot complete or fails, the receipt is marked `proofStatus: "NOT_GENERATED"`.
   - The Chainlink CRE workflow verifies the receipt with an off-chain verifier service (`/verifier`). Only when `verified: true` and `proofStatus == GENERATED_VERIFIED` is the attestation recorded as verified.
   - All receipts faithfully represent their proof status: `GENERATED_VERIFIED`, `GENERATED_UNVERIFIED`, or `NOT_GENERATED`.

4. **Network & Deployment Environment**:
   - For testing and simulation, a local EVM node (Hardhat / Anvil) running at `http://127.0.0.1:8545` is used.
   - Off-chain receipt and verifier services run on `http://127.0.0.1:<port>`. As documented, this works for local `cre workflow simulate`, but a live DON would require publicly accessible endpoints.

5. **First-Write-Wins Consensus**:
   - The `Registry.sol` contract enforces strict immutability: once `(modelCommitment, inputHash)` is attested, any subsequent attempt to write for the same pair reverts with an `AlreadyAttested` error.
