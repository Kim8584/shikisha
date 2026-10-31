#!/usr/bin/env bash
set -e

# ==============================================================================
# SHIKISHA: VERIFIABLE ML MODEL REGISTRY & ATTESTATION DEMO
# ==============================================================================

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="$REPO_ROOT/bin:$PATH"
export HOME="$REPO_ROOT"
# Ensure localhost traffic is direct
export NO_PROXY="127.0.0.1,localhost"
export no_proxy="127.0.0.1,localhost"
unset HTTP_PROXY
unset http_proxy
unset HTTPS_PROXY
unset https_proxy

ANVIL_PORT=8545
VERIFIER_PORT=8080
RPC_URL="http://127.0.0.1:${ANVIL_PORT}"
DEPLOYER_KEY="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
DEPLOYER_ADDRESS="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

ANVIL_PID=""
VERIFIER_PID=""

cleanup() {
    echo ""
    echo "=================================================================="
    echo "Cleaning up demo processes..."
    if [ -n "$ANVIL_PID" ]; then
        kill "$ANVIL_PID" 2>/dev/null || true
    fi
    if [ -n "$VERIFIER_PID" ]; then
        kill "$VERIFIER_PID" 2>/dev/null || true
    fi
    echo "Cleanup complete."
}
trap cleanup EXIT

echo "=================================================================="
echo "          SHIKISHA: VERIFIABLE ML MODEL REGISTRY DEMO"
echo "=================================================================="
echo "Starting local Anvil node on port $ANVIL_PORT..."
anvil --port "$ANVIL_PORT" --silent &
ANVIL_PID=$!

echo "Starting Shikisha Verifier HTTP Service on port $VERIFIER_PORT..."
python3 verifier/server.py "$VERIFIER_PORT" > /dev/null 2>&1 &
VERIFIER_PID=$!

# Wait for services to be ready
echo "Waiting for services to initialize..."
for i in {1..15}; do
    if cast block-number --rpc-url "$RPC_URL" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

for i in {1..15}; do
    if curl -s "http://127.0.0.1:${VERIFIER_PORT}/health" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done
echo "Services ready."

# Deploy Registry.sol
echo ""
echo "Deploying Registry.sol smart contract to local EVM..."
DEPLOY_OUTPUT=$(cd contracts && forge script script/Deploy.s.sol:DeployScript --rpc-url "$RPC_URL" --broadcast --private-key "$DEPLOYER_KEY")
REGISTRY_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep -oE "Registry deployed at: 0x[a-fA-F0-9]{40}" | awk '{print $NF}' | tail -n 1)

if [ -z "$REGISTRY_ADDRESS" ]; then
    # Fallback to deterministic first contract address deployed by Anvil key 0
    REGISTRY_ADDRESS="0x5FbDB2315678afecb367f032d93F642f64180aa3"
fi
echo "✓ Registry Contract Deployed at: $REGISTRY_ADDRESS"

MODEL_COMMITMENT=$(cat model/model_commitment.txt | tr -d ' \n\r')
SAMPLE_1_INPUT_HASH=$(python3 -c "import json; d = json.load(open('model/sample_inputs.json')); print(d[0]['inputHash'])")

echo "=================================================================="
echo " STEP 1: REGISTER THE MODEL COMMITMENT ON-CHAIN BEFORE USE"
echo "=================================================================="
echo "Model Commitment (SHA-256): $MODEL_COMMITMENT"
echo "Registering model commitment in Registry contract..."

cast send "$REGISTRY_ADDRESS" \
    "registerModel(bytes32,string)" \
    "$MODEL_COMMITMENT" \
    "ipfs://bafybeishikishaclauserecognitionmodel" \
    --rpc-url "$RPC_URL" \
    --private-key "$DEPLOYER_KEY" > /dev/null

echo "✓ Model successfully registered on-chain!"
REGISTERED_CHECK=$(cast call "$REGISTRY_ADDRESS" "isModelRegistered(bytes32)(bool)" "$MODEL_COMMITMENT" --rpc-url "$RPC_URL")
echo "  Verification query: isModelRegistered = $REGISTERED_CHECK"

echo ""
echo "=================================================================="
echo " STEP 2: ATTEST RESULT A FOR SAMPLE INPUT 1 VIA WORKFLOW"
echo "=================================================================="
echo "Target Input Hash: $SAMPLE_1_INPUT_HASH"
echo "Executing workflow for Sample 1 (Result A: Output = 1, HIGH RISK)..."

# Run MOCK_WORKFLOW_RUNNER
./bin/bun workflow/MOCK_WORKFLOW_RUNNER.ts "http://127.0.0.1:${VERIFIER_PORT}/receipt/1" "$REGISTRY_ADDRESS"

IS_RECORDED=$(cast call "$REGISTRY_ADDRESS" "isAttested(bytes32,bytes32)(bool)" "$MODEL_COMMITMENT" "$SAMPLE_1_INPUT_HASH" --rpc-url "$RPC_URL")
echo "✓ Attestation A successfully recorded on-chain! isAttested = $IS_RECORDED"

echo ""
echo "=================================================================="
echo " STEP 3: ATTEMPT TO ATTEST A DIFFERENT RESULT B FOR THE SAME INPUT"
echo "=================================================================="
echo "An operator attempts to rewrite history by attesting a DIFFERENT Result B (Output = 0) for the exact same inputHash:"

TAMPERED_OUTPUT=0
TAMPERED_PROOF="0x1111111111111111111111111111111111111111111111111111111111111111"

echo "Calling Registry.attest with different Result B..."
set +e
REVERT_OUTPUT=$(cast send "$REGISTRY_ADDRESS" \
    "attest(bytes32,bytes32,int256,bytes32,uint8)" \
    "$MODEL_COMMITMENT" \
    "$SAMPLE_1_INPUT_HASH" \
    "$TAMPERED_OUTPUT" \
    "$TAMPERED_PROOF" \
    2 \
    --rpc-url "$RPC_URL" \
    --private-key "$DEPLOYER_KEY" 2>&1)
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo "✓ [EXPECTED REVERT TRIGGERED]"
    echo "$REVERT_OUTPUT" | grep -iE "revert|AlreadyAttested|custom error" || echo "$REVERT_OUTPUT"
    echo ">> The registry successfully REVERTED: First-Write-Wins prevents rewriting decision history!"
else
    echo "✗ ERROR: Duplicate attestation unexpectedly succeeded!"
    exit 1
fi

echo ""
echo "=================================================================="
echo " STEP 4: READ THE REGISTRY AND SHOW ORIGINAL RESULT A INTACT"
echo "=================================================================="
echo "Querying on-chain state for (modelCommitment, inputHash)..."
ATTESTATION_RAW=$(cast call "$REGISTRY_ADDRESS" \
    "getAttestation(bytes32,bytes32)(bytes32,bytes32,int256,bytes32,uint8,uint256,bool)" \
    "$MODEL_COMMITMENT" \
    "$SAMPLE_1_INPUT_HASH" \
    --rpc-url "$RPC_URL")

echo "On-Chain Stored Record:"
echo "------------------------------------------------------------------"
echo "$ATTESTATION_RAW"
echo "------------------------------------------------------------------"
echo ">> The original Result A remains permanently stored with its immutable timestamp."

echo ""
echo "=================================================================="
echo " STEP 5: ATTEMPT ATTESTATION WITH A SWAPPED (UNREGISTERED) MODEL"
echo "=================================================================="
SWAPPED_MODEL_COMMITMENT="0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
echo "Operator attempts to switch model to an unregistered commitment:"
echo "Swapped Model Commitment: $SWAPPED_MODEL_COMMITMENT"

set +e
SWAP_REVERT=$(cast send "$REGISTRY_ADDRESS" \
    "attest(bytes32,bytes32,int256,bytes32,uint8)" \
    "$SWAPPED_MODEL_COMMITMENT" \
    "$SAMPLE_1_INPUT_HASH" \
    1 \
    "$TAMPERED_PROOF" \
    2 \
    --rpc-url "$RPC_URL" \
    --private-key "$DEPLOYER_KEY" 2>&1)
SWAP_EXIT=$?
set -e

if [ $SWAP_EXIT -ne 0 ]; then
    echo "✓ [EXPECTED REVERT TRIGGERED]"
    echo "$SWAP_REVERT" | grep -iE "revert|ModelNotRegistered|custom error" || echo "$SWAP_REVERT"
    echo ">> Rejected as unregistered! Operator cannot swap the model after the fact."
else
    echo "✗ ERROR: Unregistered model attestation unexpectedly succeeded!"
    exit 1
fi

echo ""
echo "=================================================================="
echo "                    DEMO COMPLETED SUCCESSFULLY                   "
echo "=================================================================="
