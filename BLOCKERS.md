# BLOCKERS

## 1. Chainlink CRE CLI Authentication Required for `cre workflow simulate`

- **Issue**: The CRE CLI (v1.39.0) requires authentication against the Chainlink CRE platform before executing `cre workflow simulate`. Running the command in non-interactive or automated environments prompts:
  ```
  ! You are not logged in
  Would you like to login now? [y/N]
  ```
  Or fails with:
  ```
  ✗ authentication required: credential validation failed: authentication failed: unable to retrieve organization info.
  ```

- **Exact Action Required from User**:
  To run the real `cre workflow simulate` command on this machine:
  1. Generate a CRE API Key at [https://app.chain.link](https://app.chain.link) (under Account Settings) OR perform interactive browser login by running:
     ```bash
     ./bin/cre login
     ```
  2. If using an API key, export it in your shell environment:
     ```bash
     export CRE_API_KEY="<your-cre-api-key>"
     ```
  3. Once authenticated, run the real simulation command:
     ```bash
     ./bin/cre workflow simulate ./workflow --target=local-settings
     ```

- **Mitigation / Fallback**:
  In accordance with Rule 3, the project does NOT substitute or present any mock as the CRE simulation. An explicitly labeled testing utility `MOCK_WORKFLOW_RUNNER.ts` is provided to demonstrate the full end-to-end receipt-fetching, verification, allowlist-checking, and contract-attestation logic against the local Anvil node during development and demos.
