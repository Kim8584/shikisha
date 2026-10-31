import {
  ConsensusAggregationByFields,
  type CronPayload,
  cre,
  type HTTPSendRequester,
  type Runtime,
  TxStatus,
} from '@chainlink/cre-sdk'
import { encodeFunctionData, parseAbi, toHex, type Address } from 'viem'
import { z } from 'zod'

export const configSchema = z.object({
  schedule: z.string(),
  receiptUrl: z.string(),
  verifierUrl: z.string(),
  registryAddress: z.string(),
  allowedModelCommitments: z.array(z.string()),
  chainSelectorName: z.string(),
  gasLimit: z.string(),
})

export type Config = z.infer<typeof configSchema>

export interface Receipt {
  id: string
  modelCommitment: string
  inputHash: string
  output: number
  proofHash: string
  proofStatus: 'GENERATED_VERIFIED' | 'GENERATED_UNVERIFIED' | 'NOT_GENERATED'
  timestamp: number
  proofURI: string
}

export interface VerifierResponse {
  verified: boolean
  modelCommitment: string
  inputHash: string
  proofStatus: string
  reason?: string
}

// Registry ABI definition for attest function
const registryAbi = parseAbi([
  'function attest(bytes32 modelCommitment, bytes32 inputHash, int256 output, bytes32 proofHash, uint8 proofStatus) external'
])

export function fetchReceipt(sendRequester: HTTPSendRequester, config: Config): Receipt {
  const resp = sendRequester.sendRequest({
    method: 'GET',
    url: config.receiptUrl,
  }).result()

  if (resp.statusCode !== 200) {
    throw new Error(`Failed to fetch receipt: HTTP ${resp.statusCode}`)
  }

  const text = Buffer.from(resp.body).toString('utf-8')
  return JSON.parse(text) as Receipt
}

export function callVerifier(
  sendRequester: HTTPSendRequester,
  config: Config,
  receipt: Receipt
): VerifierResponse {
  const resp = sendRequester.sendRequest({
    method: 'POST',
    url: config.verifierUrl,
    headers: { 'Content-Type': 'application/json' },
    body: Buffer.from(JSON.stringify(receipt)),
  }).result()

  if (resp.statusCode !== 200) {
    throw new Error(`Verifier call failed: HTTP ${resp.statusCode}`)
  }

  const text = Buffer.from(resp.body).toString('utf-8')
  return JSON.parse(text) as VerifierResponse
}

export function executeAttestation(runtime: Runtime<Config>): string {
  runtime.log(`[Shikisha CRE Workflow] Starting verifiable attestation cycle`)

  const httpCapability = new cre.capabilities.HTTPClient()

  // 1. Fetch Receipt via consensus across DON nodes
  runtime.log(`Fetching receipt from: ${runtime.config.receiptUrl}`)
  const receipt = httpCapability
    .sendRequest(
      runtime,
      (req: HTTPSendRequester, cfg: Config) => fetchReceipt(req, cfg),
      ConsensusAggregationByFields<Receipt>({
        id: (v: string[]) => v[0],
        modelCommitment: (v: string[]) => v[0],
        inputHash: (v: string[]) => v[0],
        output: (v: number[]) => v[0],
        proofHash: (v: string[]) => v[0],
        proofStatus: (v: any[]) => v[0],
        timestamp: (v: number[]) => Math.max(...v),
        proofURI: (v: string[]) => v[0],
      })
    )(runtime.config)
    .result()

  runtime.log(`Receipt received for input: ${receipt.inputHash}, model: ${receipt.modelCommitment}`)

  // 2. Validate model commitment against allowlist
  const isAllowed = runtime.config.allowedModelCommitments
    .map((c: string) => c.toLowerCase())
    .includes(receipt.modelCommitment.toLowerCase())

  if (!isAllowed) {
    throw new Error(`Model commitment ${receipt.modelCommitment} not in workflow allowlist!`)
  }

  // 3. Verify Receipt via Verifier Service
  runtime.log(`Calling Verifier service at: ${runtime.config.verifierUrl}`)
  const verifierRes = httpCapability
    .sendRequest(
      runtime,
      (req: HTTPSendRequester, cfg: Config) => callVerifier(req, cfg, receipt),
      ConsensusAggregationByFields<VerifierResponse>({
        verified: (v: boolean[]) => v.every(Boolean),
        modelCommitment: (v: string[]) => v[0],
        inputHash: (v: string[]) => v[0],
        proofStatus: (v: string[]) => v[0],
        reason: (v: any[]) => v[0] || '',
      })
    )(runtime.config)
    .result()

  // 4. Enforce Honesty Rules:
  // Only mark GENERATED_VERIFIED (uint8 = 2) if verifier returned verified: true
  // and receipt carried GENERATED_VERIFIED.
  let numericProofStatus = 0 // NOT_GENERATED
  if (verifierRes.verified && receipt.proofStatus === 'GENERATED_VERIFIED') {
    numericProofStatus = 2 // GENERATED_VERIFIED
    runtime.log(`Proof verified by Jolt Atlas! Recording GENERATED_VERIFIED`)
  } else if (receipt.proofStatus === 'GENERATED_UNVERIFIED') {
    numericProofStatus = 1 // GENERATED_UNVERIFIED
    runtime.log(`Proof unverified or verifier rejected. Recording GENERATED_UNVERIFIED`)
  } else {
    runtime.log(`Proof NOT_GENERATED. Recording NOT_GENERATED`)
  }

  // 5. Submit on-chain attestation
  const evmClient = new cre.capabilities.EVMClient()
  
  const callData = encodeFunctionData({
    abi: registryAbi,
    functionName: 'attest',
    args: [
      receipt.modelCommitment as `0x${string}`,
      receipt.inputHash as `0x${string}`,
      BigInt(receipt.output),
      receipt.proofHash as `0x${string}`,
      numericProofStatus,
    ]
  })

  runtime.log(`Writing attestation to Registry at ${runtime.config.registryAddress}`)

  // Submit via CRE EVM Client
  const tx = evmClient.sendTransaction(runtime, {
    to: runtime.config.registryAddress as Address,
    data: callData,
    gasLimit: runtime.config.gasLimit,
  })

  if (tx.txStatus !== TxStatus.SUCCESS) {
    throw new Error(`Attestation transaction failed: ${tx.errorMessage || tx.txStatus}`)
  }

  const txHash = tx.txHash ? toHex(tx.txHash) : '0x'
  runtime.log(`Attestation successfully written! TxHash: ${txHash}`)

  return txHash
}

export function onCronTrigger(runtime: Runtime<Config>, _payload: CronPayload): string {
  return executeAttestation(runtime)
}

export function initWorkflow(config: Config) {
  const cronTrigger = new cre.capabilities.CronCapability()

  return [
    cre.handler(
      cronTrigger.trigger({
        schedule: config.schedule,
      }),
      onCronTrigger
    ),
  ]
}
