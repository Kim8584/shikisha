#!/usr/bin/env python3
"""
Shikisha Verifier HTTP Service.

Endpoints:
- GET /health: Health check.
- GET /receipt/:id: Serves sample receipts (e.g. /receipt/1, /receipt/sample_1_low_risk).
- POST /verify: Verifies a receipt and its Jolt Atlas proof.
  Returns { "verified": true|false, "modelCommitment": "...", "inputHash": "...", "proofStatus": "..." }.
"""

import os
import json
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVER_DIR = os.path.join(REPO_ROOT, "prover")

ID_MAP = {
    "1": "receipt_sample_1_low_risk.json",
    "2": "receipt_sample_2_medium_risk.json",
    "3": "receipt_sample_3_high_risk.json",
    "sample_1_low_risk": "receipt_sample_1_low_risk.json",
    "sample_2_medium_risk": "receipt_sample_2_medium_risk.json",
    "sample_3_high_risk": "receipt_sample_3_high_risk.json",
    "unverified": "receipt_sample_unverified.json",
    "not_generated": "receipt_sample_not_generated.json",
}

class VerifierHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path == "/health" or path == "":
            return self._send_json(200, {"status": "ok", "service": "shikisha-verifier"})

        if path.startswith("/receipt/"):
            receipt_id = path[len("/receipt/"):]
            filename = ID_MAP.get(receipt_id)
            if not filename:
                # Try direct file match
                candidate = os.path.join(PROVER_DIR, f"receipt_{receipt_id}.json")
                if os.path.exists(candidate):
                    filename = os.path.basename(candidate)
            
            if filename:
                filepath = os.path.join(PROVER_DIR, filename)
                if os.path.exists(filepath):
                    with open(filepath, "r") as f:
                        data = json.load(f)
                    return self._send_json(200, data)

            return self._send_json(404, {"error": f"Receipt '{receipt_id}' not found"})

        return self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path == "/verify":
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                payload = json.loads(raw_body.decode('utf-8'))
            except Exception as e:
                return self._send_json(400, {"verified": False, "error": f"Invalid JSON: {str(e)}"})

            model_commitment = payload.get("modelCommitment", "")
            input_hash = payload.get("inputHash", "")
            proof_hash = payload.get("proofHash", "")
            proof_status = payload.get("proofStatus", "")
            proof_uri = payload.get("proofURI", "")

            # Rule: proofStatus NOT_GENERATED must return verified: false
            if proof_status == "NOT_GENERATED":
                return self._send_json(200, {
                    "verified": False,
                    "reason": "Proof was not generated",
                    "modelCommitment": model_commitment,
                    "inputHash": input_hash,
                    "proofStatus": "NOT_GENERATED"
                })

            if proof_status != "GENERATED_VERIFIED":
                return self._send_json(200, {
                    "verified": False,
                    "reason": f"Proof status is {proof_status}",
                    "modelCommitment": model_commitment,
                    "inputHash": input_hash,
                    "proofStatus": proof_status
                })

            # For GENERATED_VERIFIED, check underlying proof file and hash
            if not proof_uri:
                return self._send_json(200, {
                    "verified": False,
                    "reason": "Missing proofURI for GENERATED_VERIFIED receipt",
                    "modelCommitment": model_commitment,
                    "inputHash": input_hash,
                    "proofStatus": proof_status
                })

            full_proof_path = os.path.join(REPO_ROOT, proof_uri.lstrip("/"))
            if not os.path.exists(full_proof_path):
                return self._send_json(200, {
                    "verified": False,
                    "reason": f"Proof file not found: {proof_uri}",
                    "modelCommitment": model_commitment,
                    "inputHash": input_hash,
                    "proofStatus": proof_status
                })

            with open(full_proof_path, "rb") as f:
                content = f.read()

            computed_hash = "0x" + hashlib.sha256(content).hexdigest()
            if computed_hash.lower() != proof_hash.lower():
                return self._send_json(200, {
                    "verified": False,
                    "reason": "Proof hash mismatch",
                    "modelCommitment": model_commitment,
                    "inputHash": input_hash,
                    "proofStatus": proof_status
                })

            if b"Proof verified successfully!" not in content:
                return self._send_json(200, {
                    "verified": False,
                    "reason": "Proof verification record invalid",
                    "modelCommitment": model_commitment,
                    "inputHash": input_hash,
                    "proofStatus": proof_status
                })

            # All checks pass
            return self._send_json(200, {
                "verified": True,
                "modelCommitment": model_commitment,
                "inputHash": input_hash,
                "proofStatus": "GENERATED_VERIFIED"
            })

        return self._send_json(404, {"error": "Endpoint not found"})

def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, VerifierHandler)
    print(f"Shikisha Verifier Server listening on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
