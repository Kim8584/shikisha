#!/usr/bin/env bun
/**
 * =========================================================================
 * MOCK WORKFLOW RUNNER (Testing Utility)
 * =========================================================================
 * NOTE: This is an explicit local test runner for development and end-to-end
 * demonstration. It executes the exact same logical steps as the CRE workflow
 * (HTTP receipt fetch -> HTTP verifier call -> allowlist check -> on-chain
 * attestation) against a local EVM node (Anvil).
 * 
 * In accordance with Honesty Rule 3, this file is explicitly named MOCK and
 * MUST NEVER be described as the real CRE CLI simulation.
 * =========================================================================
 */

import { createWalletClient, createPublicClient, http, parseAbi } from 'viem'
import { privateKeyToAccount } from 'viem/accounts'
import * as fs from 'fs'
import * as path from 'path'

const CONFIG_PATH = path.join(__dirname, 'config.local.json')
const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'))

const registryAbi = parseAbi([
  'function attest(bytes32 modelCommitment, bytes32 inputHash, int256 output, bytes32 proofHash, uint8 proofStatus) external',
  'function isAttested(bytes32 modelCommitment, bytes32 inputHash) external view returns (bool)',
  'function getAttestation(bytes32 modelCommitment, bytes32 inputHash) external view returns (bytes32 commitment, bytes32 recordedInputHash, int256 output, bytes32 proofHash, uint8 proofStatus, uint256 timestamp, bool exists)',
  'function isModelRegistered(bytes32 modelCommitment) external view returns (bool)',
])

async function runMockWorkflow(targetReceiptUrl?: string, overrideRegistryAddress?: string) {
  const receiptUrl = targetReceiptUrl || config.receiptUrl
  const registryAddress = (overrideRegistryAddress || config.registryAddress) as `0x${string}`

  console.log(`[MOCK_WORKFLOW_RUNNER] Starting workflow execution`)
  console.log(`[MOCK_WORKFLOW_RUNNER] Target Registry: ${registryAddress}`)
  console.log(`[MOCK_WORKFLOW_RUNNER] Target Receipt URL: ${receiptUrl}`)

  // Step 1: Fetch Receipt via HTTP
  console.log(`[MOCK_WORKFLOW_RUNNER] Step 1: Fetching receipt...`)
  const receiptResp = await fetch(receiptUrl)
  if (!receiptResp.ok) {
    throw new Error(`[MOCK_WORKFLOW_RUNNER] HTTP Error ${receiptResp.status} fetching receipt from ${receiptUrl}`)
  }
  const receipt = await receiptResp.json()
  console.log(`[MOCK_WORKFLOW_RUNNER] Receipt fetched:`)
  console.log(`  - Model Commitment: ${receipt.modelCommitment}`)
  console.log(`  - Input Hash:       ${receipt.inputHash}`)
  console.log(`  - Output:           ${receipt.output}`)
  console.log(`  - Proof Status:     ${receipt.proofStatus}`)
  console.log(`  - Proof Hash:       ${receipt.proofHash}`)

  // Step 2: Allowlist Validation
  console.log(`[MOCK_WORKFLOW_RUNNER] Step 2: Validating model commitment against allowlist...`)
  const isAllowed = config.allowedModelCommitments
    .map((c: string) => c.toLowerCase())
    .includes(receipt.modelCommitment.toLowerCase())

  if (!isAllowed) {
    throw new Error(`[MOCK_WORKFLOW_RUNNER] Model commitment ${receipt.modelCommitment} is NOT in allowlist!`)
  }
  console.log(`[MOCK_WORKFLOW_RUNNER] Model commitment validated against allowlist.`)

  // Step 3: Call Verifier Service via HTTP
  console.log(`[MOCK_WORKFLOW_RUNNER] Step 3: Sending receipt to Verifier service (${config.verifierUrl})...`)
  const verifyResp = await fetch(config.verifierUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(receipt),
  })
  if (!verifyResp.ok) {
    throw new Error(`[MOCK_WORKFLOW_RUNNER] Verifier service returned HTTP ${verifyResp.status}`)
  }
  const verifyResult = await verifyResp.json()
  console.log(`[MOCK_WORKFLOW_RUNNER] Verifier Service Response:`, verifyResult)

  // Step 4: Determine Attestation Proof Status (Honesty Rule)
  let numericProofStatus: number
  if (verifyResult.verified === true && receipt.proofStatus === 'GENERATED_VERIFIED') {
    numericProofStatus = 2 // GENERATED_VERIFIED
    console.log(`[MOCK_WORKFLOW_RUNNER] Status confirmed as GENERATED_VERIFIED (uint8 = 2).`)
  } else if (receipt.proofStatus === 'GENERATED_UNVERIFIED') {
    numericProofStatus = 1 // GENERATED_UNVERIFIED
    console.log(`[MOCK_WORKFLOW_RUNNER] Status is GENERATED_UNVERIFIED (uint8 = 1).`)
  } else {
    numericProofStatus = 0 // NOT_GENERATED
    console.log(`[MOCK_WORKFLOW_RUNNER] Status is NOT_GENERATED (uint8 = 0).`)
  }

  // Step 5: Submit Attestation On-Chain
  console.log(`[MOCK_WORKFLOW_RUNNER] Step 5: Submitting attestation to Registry.attest...`)
  // Default Anvil Account #0
  const account = privateKeyToAccount('0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80')
  const client = createWalletClient({
    account,
    transport: http('http://127.0.0.1:8545')
  })
  const publicClient = createPublicClient({
    transport: http('http://127.0.0.1:8545')
  })

  const hash = await client.writeContract({
    address: registryAddress,
    abi: registryAbi,
    functionName: 'attest',
    args: [
      receipt.modelCommitment as `0x${string}`,
      receipt.inputHash as `0x${string}`,
      BigInt(receipt.output),
      receipt.proofHash as `0x${string}`,
      numericProofStatus,
    ],
  })

  console.log(`[MOCK_WORKFLOW_RUNNER] Transaction submitted! TxHash: ${hash}`)
  const receiptTx = await publicClient.waitForTransactionReceipt({ hash })
  console.log(`[MOCK_WORKFLOW_RUNNER] Transaction confirmed in block ${receiptTx.blockNumber}!`)
  return hash
}

// Allow CLI invocation
if (import.meta.main) {
  const customUrl = process.argv[2]
  const customRegistry = process.argv[3]
  runMockWorkflow(customUrl, customRegistry)
    .then(() => process.exit(0))
    .catch((err) => {
      console.error(`\n[MOCK_WORKFLOW_RUNNER] Execution Error: ${err.message}`)
      process.exit(1)
    })
}
