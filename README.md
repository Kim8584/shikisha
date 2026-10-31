<p align="center">
  <img src="assets/shikisha_banner.jpg" alt="Shikisha Hero Banner" width="100%" />
</p>

<p align="center">
  <img src="assets/shikisha_emblem.jpg" alt="Shikisha Emblem" width="180" />
</p>

# Shikisha

> **A Verifiable ML Model Registry with First-Write-Wins Consensus**

Shikisha solves a critical vulnerability in machine learning deployments: **an operator quietly swapping a model or rewriting historical inference outcomes after the fact**.

In Shikisha:
1. **Pre-Registration**: The operator commits an ONNX model's cryptographic hash (`modelCommitment = sha256(model.onnx)`) on-chain before inference occurs.
2. **Execution Receipts**: Inferences produce structured cryptographic receipts linking `(modelCommitment, inputHash, output, proofHash, proofStatus)`.
3. **Verifiable Proving**: Inferences are proven using the **Jolt Atlas** zkML framework, generating integrity proofs directly over ONNX computations.
4. **Decentralized Workflow**: A **Chainlink Runtime Environment (CRE)** workflow fetches the receipt, evaluates proof validity via an off-chain verifier service, validates allowlists, reaches DON consensus, and writes an attestation to the on-chain registry.
5. **First-Write-Wins Immutability**: The smart contract enforces first-write-wins per `(modelCommitment, inputHash)`. Once a decision is recorded for an input, subsequent attempts to rewrite history revert.

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph Client / Operator
        Input[Raw Legal Clause Text] --> Feat[Deterministic Bag-of-Keywords Featurizer]
        Feat --> InputHash[inputHash = sha256(feature_vector)]
        Feat --> Model[Tiny ONNX Model]
        Model --> Infer[Binary Risk Decision]
        Model --> Commit[modelCommitment = sha256(ONNX bytes)]
        Infer & Commit & InputHash --> Prover[Jolt Atlas Prover]
        Prover --> Receipt[Receipt JSON]
    end

    subgraph Off-Chain Verifier & Hosting
        Receipt --> ReceiptHost[Receipt Endpoint: /receipt/:id]
        Receipt --> VerifierSvc[Verifier HTTP Service: /verify]
    end

    subgraph Chainlink CRE Workflow
        ReceiptHost -->|HTTP GET| CRE[CRE Simulation / DON Node Consensus]
        CRE -->|HTTP POST| VerifierSvc
        VerifierSvc -->|Verification Status| CRE
        CRE -->|Verify Allowlist & Consensus| CRE
    end

    subgraph On-Chain EVM (Registry.sol)
        Commit -->|registerModel| RegModel[(Registered Models)]
        CRE -->|attest(commitment, inputHash, output, proofHash, status)| RegAttest[(Attestations: First-Write-Wins)]
        RegAttest -.->|Duplicate Input Attempt| Revert[REVERT: AlreadyAttested]
    end
```

---

## Trust Tiers: What Is and Isn't Proven

In accordance with strict technical honesty:
- **PROVEN (Integrity Only)**:
  - The ONNX computational graph execution (weights, layer additions, matrix multiplications, ReLU activations) on the fixed input vector is mathematically proven if and only if `proofStatus` is `GENERATED_VERIFIED`.
  - **No Zero-Knowledge Claim**: We do not claim zero-knowledge privacy. Jolt proofs provide verifiable computational integrity and minimal disclosure (raw clause text is never revealed on-chain), not cryptographic zero-knowledge.
- **CHECKED BY CRE NODES**:
  - Receipt schema and structure.
  - Verification response from the verifier HTTP service.
  - Model commitment membership in the authorized allowlist.
  - Consensus across DON nodes before writing to the target chain.
- **NOT CHECKED / UNPROVEN**:
  - **Featurization**: The transformation from raw legal clause text to the 16-element integer/float feature vector occurs client-side and is **NOT** proven in zkVM.
  - **Legal Ground Truth**: The contract cannot verify whether the classification of a clause as "high risk" is legally accurate—only that the pre-registered model deterministically produced that output from that feature vector.

---

## Current Architecture Limitations

1. **Off-Chain Verifier Service**:
   - Proof verification currently executes off-chain via the `/verifier` service. The verifier service is an off-chain trusted component today.
   - **Roadmap**: Wrapping Jolt Atlas proofs in a Groth16 SNARK wrapper (or direct EVM pairing precompile verifier) for fully autonomous on-chain proof verification without off-chain verifier services.
2. **Localhost Endpoints**:
   - In local development and simulation, the workflow accesses `http://127.0.0.1:<port>`.
   - A production Chainlink DON deployment requires publicly hosted, authenticated endpoints reachable across decentralized oracle nodes.

---

## Repository Structure

```
├── model/                # Tiny ONNX model, deterministic featurizer, test inputs
│   ├── featurizer.py     # Deterministic 16-keyword bag-of-words featurizer
│   ├── train_and_export.py # ONNX model generator & commitment calculator
│   ├── model.onnx        # Exported ONNX binary (887 bytes, 145 params)
│   ├── model_commitment.txt # SHA-256 model commitment
│   └── sample_inputs.json # 3 sample inputs with expected outputs
├── prover/               # Jolt Atlas prover integration & receipt generator
│   ├── generate_receipts.py # Prover runner under timeout 600
│   └── out/              # Generated Jolt Atlas proof logs
├── verifier/             # Lightweight HTTP verifier service
│   ├── server.py         # Serves GET /receipt/:id and POST /verify
│   └── test_verifier.py  # Unit test suite for verifier service
├── contracts/            # Foundry smart contracts
│   ├── Registry.sol      # Core registry enforcing first-write-wins
│   ├── script/Deploy.s.sol # Deployment script
│   └── test/Registry.t.sol # Test suite covering registration, attestation, reverts
├── workflow/             # Chainlink CRE workflow
│   ├── workflow.yaml     # CRE workflow configuration
│   ├── package.json      # @chainlink/cre-sdk, viem, zod
│   ├── main.ts           # CRE workflow entrypoint
│   ├── workflow.ts       # CRE workflow definition & consensus logic
│   └── MOCK_WORKFLOW_RUNNER.ts # Local test runner utility
├── demo/                 # Demonstration & simulation artifacts
│   ├── run.sh            # Complete end-to-end demo script
│   └── simulation-output.txt # Output record of CRE simulation
├── NOTES.md              # Environment discoveries & tool logs
├── ASSUMPTIONS.md        # Technical assumptions
├── BLOCKERS.md           # Authentication blocker documentation
└── REPORT.md             # Final implementation report
```

---

## How to Run Everything

### Prerequisites
- Python 3.10+
- Node.js v20+ / Bun 1.4+
- Foundry (`forge`, `cast`, `anvil`)

### 1. Model Featurization and Training
```bash
PYTHONPATH=./python_libs python3 model/train_and_export.py
```

### 2. Run Smart Contract Tests
```bash
cd contracts
HOME=$PWD/.. ../bin/forge test
cd ..
```

### 3. Generate Jolt Atlas Proofs and Receipts
```bash
python3 prover/generate_receipts.py
```

### 4. Run Verifier Service Tests
```bash
python3 verifier/test_verifier.py
```

### 5. Run the End-to-End Demo
```bash
./demo/run.sh
```

---

## Chainlink CRE CLI Simulation

To simulate the workflow using the official Chainlink CRE CLI:
```bash
# 1. Log in or provide API key from https://app.chain.link
./bin/cre login
# OR: export CRE_API_KEY="<your-api-key>"

# 2. Run simulation
./bin/cre workflow simulate ./workflow --target=local-settings
```
*Note: As detailed in `BLOCKERS.md`, the CRE CLI requires authentication before executing `cre workflow simulate`. The local development flow is fully validated via `workflow/MOCK_WORKFLOW_RUNNER.ts`.*
