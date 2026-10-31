# Shikisha: Final Implementation Report

## Summary of Deliverables

| Step | Component | Status | Verification Command | Notes |
|---|---|---|---|---|
| 1 | Model & Featurizer | Completed | `PYTHONPATH=./python_libs python3 model/train_and_export.py` | 145-param ONNX model, 16 features, 887 bytes |
| 2 | Registry Contract | Completed | `cd contracts && HOME=$PWD/.. ../bin/forge test` | 7/7 tests passing in 1.75ms |
| 3 | Jolt Atlas Prover | Completed | `python3 prover/generate_receipts.py` | Proved & verified in <100ms under timeout 600 |
| 4 | Verifier Service | Completed | `python3 verifier/test_verifier.py` | 4/4 HTTP test cases passing |
| 5 | CRE Workflow | Configured & Tested | `./bin/cre workflow simulate ./workflow` / `MOCK_WORKFLOW_RUNNER.ts` | Simulation output saved in `demo/simulation-output.txt` |
| 6 | End-to-End Demo | Completed | `./demo/run.sh` | All 5 steps demonstrated, revert clearly shown |
| 7 | Documentation | Completed | Inspect `README.md`, `ASSUMPTIONS.md`, `NOTES.md`, `BLOCKERS.md` | Clear trust tiers and honesty rules documented |

---

## Detailed Step Breakdown

### Step 1: Model (`/model`)
- **Featurizer**: `model/featurizer.py` implements a deterministic 16-keyword bag-of-words tokenizer producing fixed float vectors. Explicitly documented that client-side featurization is not proven in zkVM.
- **ONNX Classifier**: `model/model.onnx` is a tiny MLP (16 inputs $\to$ 8 hidden ReLU $\to$ 1 output) with 145 parameters.
- **Commitment**: SHA-256 of ONNX file bytes is `0x12ba895783aa2a61554d635d25d0ff7f671b22a58b8b33a15efa35b123ad141c`.
- **Sample Inputs**: 3 clauses (Low Risk, Medium Risk, High Risk) with deterministic hashes saved to `model/sample_inputs.json`.

### Step 2: Registry Smart Contract (`/contracts`)
- **Contract**: `contracts/Registry.sol` provides:
  - `registerModel(bytes32 modelCommitment, string metadataURI)`
  - `attest(bytes32 modelCommitment, bytes32 inputHash, int256 output, bytes32 proofHash, uint8 proofStatus)`
  - View getters: `getModel`, `getAttestation`, `isModelRegistered`, `isAttested`.
- **Foundry Test Suite**: `contracts/test/Registry.t.sol` passed all 7 tests:
  - `test_ModelRegistration()`
  - `test_DuplicateModelRegistrationReverts()`
  - `test_AttestationSuccess()`
  - `test_DuplicateAttestationReverts_FirstWriteWins()`
  - `test_UnregisteredModelReverts()`
  - `test_UnauthorizedAttesterReverts()`
  - `test_SetAuthorizedAttesterOnlyOwner()`

### Step 3: Receipts & Jolt Atlas Proving (`/prover`)
- **Prover Integration**: Built using the official `ICME-Lab/jolt-atlas` zkML engine (`bin/jolt-prove`).
- **Timeout Compliance**: Executed under `timeout 600` via `prover/generate_receipts.py`. Proving the tiny model took 91.84ms and verification took 13.21ms.
- **Receipts**: Output schema contains `modelCommitment`, `inputHash`, `output`, `proofHash`, `proofStatus`, `timestamp`, and `proofURI`. Generated verified receipts for all 3 samples, plus test fixtures for unverified and ungenerated cases.

### Step 4: Verifier HTTP Service (`/verifier`)
- **Endpoints**:
  - `GET /health`: Health check.
  - `GET /receipt/:id`: Serves sample receipt JSON.
  - `POST /verify`: Checks proof file presence, SHA-256 integrity, and verification logs. Truthfully returns `verified: false` for `NOT_GENERATED` and `GENERATED_UNVERIFIED`.
- **Test Suite**: `verifier/test_verifier.py` verified 4/4 passing tests.

### Step 5: Chainlink CRE Workflow (`/workflow`)
- **Official Structure**:
  - `project.yaml`: Target network configurations (local-anvil and sepolia).
  - `workflow/workflow.yaml`: Workflow artifact settings.
  - `workflow/package.json`: `@chainlink/cre-sdk`, `viem`, `zod`, `typescript`.
  - `workflow/workflow.ts`: HTTP receipt fetch $\to$ Verifier check $\to$ Allowlist filter $\to$ Consensus $\to$ Contract attestation.
- **Simulation Status**:
  - Command: `./bin/cre workflow simulate ./workflow --target=local-settings --non-interactive`
  - Output captured in `demo/simulation-output.txt`.
  - The CRE CLI (v1.39.0) enforces interactive/API-key authentication against the Chainlink CRE platform. As specified in project instructions, this requirement is documented in `BLOCKERS.md` with the exact login/API-key steps.
  - A dedicated local test runner `workflow/MOCK_WORKFLOW_RUNNER.ts` executes the exact same steps against the local EVM node.

### Step 6: Demo Execution (`/demo/run.sh`)
Running `./demo/run.sh` produces:
1. Model commitment registration on-chain (`isModelRegistered = true`).
2. Attestation of Result A for Sample Input 1 recorded on-chain (`isAttested = true`).
3. Tamper attempt to attest different Result B for the same input $\to$ Contract triggers `AlreadyAttested` revert.
4. On-chain query displaying original Result A intact with immutable timestamp.
5. Tamper attempt using an unregistered swapped model commitment $\to$ Contract triggers `ModelNotRegistered` revert.
Script exits 0 with clean process shutdown.

---

## What Was Stubbed vs. Fully Implemented

- **Fully Implemented**:
  - ONNX model generation, featurization, and SHA-256 commitment calculation.
  - Jolt Atlas proving and local verification pipeline.
  - Solidity registry contract with first-write-wins enforcement.
  - Full Foundry test suite (7/7 tests passing).
  - Verifier HTTP service (`GET /receipt/:id`, `POST /verify`).
  - CRE project configuration and TypeScript workflow using `@chainlink/cre-sdk`.
  - Automated demo script (`demo/run.sh`).
- **Stubbed / Flagged**:
  - The CRE simulation CLI run (`cre workflow simulate`) requires user authentication credentials (`cre login` or `export CRE_API_KEY=...`). The simulation command was executed, the authentication prompt was captured and recorded in `demo/simulation-output.txt`, and full instructions were written to `BLOCKERS.md`.

---

## Blockers

Refer to `BLOCKERS.md` for full details:
1. **Chainlink CRE Authentication**: Run `./bin/cre login` or `export CRE_API_KEY="<key>"` from [https://app.chain.link](https://app.chain.link) to execute the simulation against the CRE platform.
