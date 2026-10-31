// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title Shikisha Model & Attestation Registry
 * @notice Enforces verifiable ML model commitment registration and first-write-wins
 *         attestation per (modelCommitment, inputHash).
 */
contract Registry {
    // --- Data Types ---
    enum ProofStatus {
        NOT_GENERATED,
        GENERATED_UNVERIFIED,
        GENERATED_VERIFIED
    }

    struct ModelRecord {
        bytes32 modelCommitment;
        string metadataURI;
        uint256 registeredAt;
        bool exists;
    }

    struct AttestationRecord {
        bytes32 modelCommitment;
        bytes32 inputHash;
        int256 output;
        bytes32 proofHash;
        ProofStatus proofStatus;
        uint256 timestamp;
        bool exists;
    }

    // --- State Variables ---
    address public owner;
    address public authorizedAttester;

    mapping(bytes32 => ModelRecord) private _models;
    // modelCommitment => inputHash => AttestationRecord
    mapping(bytes32 => mapping(bytes32 => AttestationRecord)) private _attestations;

    // --- Events ---
    event ModelRegistered(
        bytes32 indexed modelCommitment,
        string metadataURI,
        uint256 timestamp
    );

    event Attested(
        bytes32 indexed modelCommitment,
        bytes32 indexed inputHash,
        int256 output,
        bytes32 proofHash,
        ProofStatus proofStatus,
        uint256 timestamp
    );

    event AuthorizedAttesterUpdated(
        address indexed oldAttester,
        address indexed newAttester
    );

    // --- Custom Errors ---
    error UnauthorizedOwner(address caller);
    error UnauthorizedAttester(address caller);
    error ModelAlreadyRegistered(bytes32 modelCommitment);
    error ModelNotRegistered(bytes32 modelCommitment);
    error AlreadyAttested(bytes32 modelCommitment, bytes32 inputHash);
    error InvalidProofStatus(uint8 status);

    // --- Modifiers ---
    modifier onlyOwner() {
        if (msg.sender != owner) {
            revert UnauthorizedOwner(msg.sender);
        }
        _;
    }

    modifier onlyAttester() {
        if (msg.sender != authorizedAttester && msg.sender != owner) {
            revert UnauthorizedAttester(msg.sender);
        }
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedAttester = msg.sender;
    }

    /**
     * @notice Set or rotate the authorized attester (e.g. CRE workflow forwarder / DON key).
     */
    function setAuthorizedAttester(address newAttester) external onlyOwner {
        address old = authorizedAttester;
        authorizedAttester = newAttester;
        emit AuthorizedAttesterUpdated(old, newAttester);
    }

    /**
     * @notice Register a model's SHA-256 commitment before inference.
     * @param modelCommitment SHA-256 hash of ONNX model bytes.
     * @param metadataURI Off-chain metadata URI (e.g. IPFS / HTTP link).
     */
    function registerModel(
        bytes32 modelCommitment,
        string calldata metadataURI
    ) external {
        if (_models[modelCommitment].exists) {
            revert ModelAlreadyRegistered(modelCommitment);
        }

        _models[modelCommitment] = ModelRecord({
            modelCommitment: modelCommitment,
            metadataURI: metadataURI,
            registeredAt: block.timestamp,
            exists: true
        });

        emit ModelRegistered(modelCommitment, metadataURI, block.timestamp);
    }

    /**
     * @notice Attest an inference result for a given model and inputHash.
     *         Enforces first-write-wins: cannot be rewritten once recorded.
     * @param modelCommitment The registered model commitment.
     * @param inputHash Deterministic hash of the featurized input vector.
     * @param output Model decision output (e.g. class label or fixed-point score).
     * @param proofHash SHA-256 hash of the Jolt Atlas proof bytes (0x0 if NOT_GENERATED).
     * @param proofStatus Status enum (0=NOT_GENERATED, 1=GENERATED_UNVERIFIED, 2=GENERATED_VERIFIED).
     */
    function attest(
        bytes32 modelCommitment,
        bytes32 inputHash,
        int256 output,
        bytes32 proofHash,
        uint8 proofStatus
    ) external onlyAttester {
        if (!_models[modelCommitment].exists) {
            revert ModelNotRegistered(modelCommitment);
        }

        if (_attestations[modelCommitment][inputHash].exists) {
            revert AlreadyAttested(modelCommitment, inputHash);
        }

        if (proofStatus > uint8(ProofStatus.GENERATED_VERIFIED)) {
            revert InvalidProofStatus(proofStatus);
        }

        ProofStatus status = ProofStatus(proofStatus);

        _attestations[modelCommitment][inputHash] = AttestationRecord({
            modelCommitment: modelCommitment,
            inputHash: inputHash,
            output: output,
            proofHash: proofHash,
            proofStatus: status,
            timestamp: block.timestamp,
            exists: true
        });

        emit Attested(
            modelCommitment,
            inputHash,
            output,
            proofHash,
            status,
            block.timestamp
        );
    }

    // --- View Functions ---

    function isModelRegistered(bytes32 modelCommitment) external view returns (bool) {
        return _models[modelCommitment].exists;
    }

    function getModel(bytes32 modelCommitment) external view returns (
        bytes32 commitment,
        string memory metadataURI,
        uint256 registeredAt,
        bool exists
    ) {
        ModelRecord memory m = _models[modelCommitment];
        return (m.modelCommitment, m.metadataURI, m.registeredAt, m.exists);
    }

    function isAttested(bytes32 modelCommitment, bytes32 inputHash) external view returns (bool) {
        return _attestations[modelCommitment][inputHash].exists;
    }

    function getAttestation(bytes32 modelCommitment, bytes32 inputHash) external view returns (
        bytes32 commitment,
        bytes32 recordedInputHash,
        int256 output,
        bytes32 proofHash,
        uint8 proofStatus,
        uint256 timestamp,
        bool exists
    ) {
        AttestationRecord memory a = _attestations[modelCommitment][inputHash];
        return (
            a.modelCommitment,
            a.inputHash,
            a.output,
            a.proofHash,
            uint8(a.proofStatus),
            a.timestamp,
            a.exists
        );
    }
}
