# NOTES

## Tool Status and Discoveries

### Initial Environment Check (Status and Resolution)
- Command `which python3 node npm cargo forge anvil cre` exited with code 1.
- **Diagnostics**:
  - Found: `python3` (v3.10.12), `node` (v20.20.2), `npm` (v10.8.2), `cargo` (v1.96.0).
  - Missing: `forge` (Foundry), `anvil` (Foundry), `cre` (Chainlink Runtime Environment CLI).
- **Resolution Plan**:
  - For `cre`: Installing official CRE CLI via `curl -sSL https://app.chain.link/cre/install.sh | bash` into `~/.cre/cre`.
  - For smart contracts (`/contracts`): Use Node.js/Hardhat with ethers / viem or Foundry (`foundryup`). Hardhat is self-contained in Node v20 and requires zero system binary dependencies.

### Jolt Atlas Findings
- **Repository**: Confirmed official repository at `https://github.com/ICME-Lab/jolt-atlas` (ICME Labs / NovaNet).
- **Architecture**: Adapts a16z Crypto's JOLT zkVM for neural network inference directly from ONNX computational graphs.
- **Core Mechanism**: Uses lookup arguments and sumcheck protocols for non-linear operations (e.g. ReLU, SoftMax) without traditional arithmetic circuits.
- **Proving & Verification**:
  - Official examples run via Cargo: `cargo run --release --package jolt-atlas-core --example <model>`
  - Tracer: `cargo run --release --package atlas-onnx-tracer --example <model>`

### Chainlink CRE CLI Findings
- **CLI Binary**: `cre` CLI installs to `~/.cre/cre` via `https://app.chain.link/cre/install.sh`.
- **SDK**: Official `@chainlink/cre-sdk` available on npm.
- **Workflow Simulation**:
  - Command: `cre workflow simulate <workflow-path> --target=<target-name>`
  - Simulates the workflow inside a local WASM environment while connecting to specified external endpoints.
- **Honesty & Environment Constraints**:
  - In simulation mode, `http://localhost:<port>` is accessible to the local runner, but in a production DON deployment, all endpoints must be publicly routable.
  - The verifier service is an off-chain trusted component; true on-chain verification would require a Groth16 wrapper contract.
