#!/usr/bin/env python3
"""
Unit test for Verifier Service.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import subprocess

PORT = 8099

def test_verifier_service():
    server_process = subprocess.Popen(
        [sys.executable, "verifier/server.py", str(PORT)],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    time.sleep(1)

    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)

    try:
        # Test 1: GET /health
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/health")
        with opener.open(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert data["status"] == "ok"
            print("✓ GET /health: PASS")

        # Test 2: GET /receipt/1
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/receipt/1")
        with opener.open(req) as resp:
            receipt = json.loads(resp.read().decode('utf-8'))
            assert receipt["id"] == "sample_1_low_risk"
            assert receipt["proofStatus"] == "GENERATED_VERIFIED"
            print("✓ GET /receipt/1: PASS")

        # Test 3: POST /verify on valid receipt
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/verify",
            data=json.dumps(receipt).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with opener.open(req) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            assert res["verified"] is True
            print("✓ POST /verify (valid receipt): PASS (verified=True)")

        # Test 4: POST /verify on NOT_GENERATED
        not_gen = {
            "modelCommitment": "0x123",
            "inputHash": "0x456",
            "proofStatus": "NOT_GENERATED"
        }
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/verify",
            data=json.dumps(not_gen).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with opener.open(req) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            assert res["verified"] is False
            print("✓ POST /verify (NOT_GENERATED): PASS (verified=False)")

        print("\nAll Verifier service tests passed successfully!")
    finally:
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    test_verifier_service()
