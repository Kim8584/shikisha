// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {Registry} from "../Registry.sol";

contract RegistryTest is Test {
    Registry public registry;

    address public owner = address(0xABCD);
    address public attester = address(0xCAFE);
    address public attacker = address(0xDEAD);

    bytes32 public sampleModelCommitment = 0x12ba895783aa2a61554d635d25d0ff7f671b22a58b8b33a15efa35b123ad141c;
    bytes32 public unregisteredModelCommitment = 0x9999999999999999999999999999999999999999999999999999999999999999;
    bytes32 public sampleInputHash = 0xfbeb8ead4590a23174d701bb8d7cd24f87d6f73a297034bbf6291b7b82bbb9f3;
    bytes32 public sampleProofHash = 0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890;

    function setUp() public {
        vm.prank(owner);
        registry = new Registry();

        // Set authorized attester
        vm.prank(owner);
        registry.setAuthorizedAttester(attester);

        // Register model
        registry.registerModel(sampleModelCommitment, "ipfs://bafybeishikishatestmodelmetadata");
    }

    function test_ModelRegistration() public {
        assertTrue(registry.isModelRegistered(sampleModelCommitment));
        (bytes32 commitment, string memory uri, uint256 regTime, bool exists) = registry.getModel(sampleModelCommitment);
        assertEq(commitment, sampleModelCommitment);
        assertEq(uri, "ipfs://bafybeishikishatestmodelmetadata");
        assertTrue(exists);
        assertGt(regTime, 0);
    }

    function test_DuplicateModelRegistrationReverts() public {
        vm.expectRevert(abi.encodeWithSelector(Registry.ModelAlreadyRegistered.selector, sampleModelCommitment));
        registry.registerModel(sampleModelCommitment, "ipfs://duplicate");
    }

    function test_AttestationSuccess() public {
        vm.prank(attester);
        registry.attest(
            sampleModelCommitment,
            sampleInputHash,
            1, // output
            sampleProofHash,
            2  // GENERATED_VERIFIED
        );

        assertTrue(registry.isAttested(sampleModelCommitment, sampleInputHash));
        (
            bytes32 com,
            bytes32 inHash,
            int256 out,
            bytes32 pHash,
            uint8 status,
            uint256 ts,
            bool exists
        ) = registry.getAttestation(sampleModelCommitment, sampleInputHash);

        assertEq(com, sampleModelCommitment);
        assertEq(inHash, sampleInputHash);
        assertEq(out, 1);
        assertEq(pHash, sampleProofHash);
        assertEq(status, 2);
        assertTrue(exists);
        assertGt(ts, 0);
    }

    function test_DuplicateAttestationReverts_FirstWriteWins() public {
        // First write succeeds
        vm.prank(attester);
        registry.attest(sampleModelCommitment, sampleInputHash, 1, sampleProofHash, 2);

        // Second write attempt with DIFFERENT output (e.g. attempting to rewrite history)
        vm.expectRevert(abi.encodeWithSelector(Registry.AlreadyAttested.selector, sampleModelCommitment, sampleInputHash));
        vm.prank(attester);
        registry.attest(sampleModelCommitment, sampleInputHash, 0, bytes32(0), 0);
    }

    function test_UnregisteredModelReverts() public {
        vm.prank(attester);
        vm.expectRevert(abi.encodeWithSelector(Registry.ModelNotRegistered.selector, unregisteredModelCommitment));
        registry.attest(unregisteredModelCommitment, sampleInputHash, 1, sampleProofHash, 2);
    }

    function test_UnauthorizedAttesterReverts() public {
        vm.prank(attacker);
        vm.expectRevert(abi.encodeWithSelector(Registry.UnauthorizedAttester.selector, attacker));
        registry.attest(sampleModelCommitment, sampleInputHash, 1, sampleProofHash, 2);
    }

    function test_SetAuthorizedAttesterOnlyOwner() public {
        vm.prank(attacker);
        vm.expectRevert(abi.encodeWithSelector(Registry.UnauthorizedOwner.selector, attacker));
        registry.setAuthorizedAttester(attacker);

        // Owner succeeds
        address newAttester = address(0x5555);
        vm.prank(owner);
        registry.setAuthorizedAttester(newAttester);
        assertEq(registry.authorizedAttester(), newAttester);
    }
}
