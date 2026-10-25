// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title GovernanceRegistry
 * @notice Stores the immutable hash chain of proposal versions and governance approvals.
 */
contract GovernanceRegistry {
    struct Version {
        bytes32 versionHash;
        bytes32 actionHash;
        bytes32 evidenceRoot;
    }

    struct ApprovedRecord {
        bytes32 versionHash;
        bytes32 actionHash;
        bytes32 evidenceRoot;
    }

    address public immutable governance;

    // proposalId => proposer (first committer)
    mapping(bytes32 => address) public proposalOwner;
    // proposalId => sequential versions (1-indexed via array indexing)
    mapping(bytes32 => Version[]) private _versions;
    // proposalId => versionHash => bool (prevents duplicate version hashes)
    mapping(bytes32 => mapping(bytes32 => bool)) public hasVersionHash;
    // proposalId => approved version record
    mapping(bytes32 => ApprovedRecord) private _approved;

    event VersionCommitted(
        bytes32 indexed proposalId,
        uint256 indexed version,
        bytes32 versionHash,
        bytes32 actionHash,
        bytes32 evidenceRoot,
        address proposer
    );

    event ProposalApproved(
        bytes32 indexed proposalId,
        bytes32 indexed versionHash,
        bytes32 actionHash,
        bytes32 evidenceRoot
    );

    constructor(address governance_) {
        require(governance_ != address(0), "invalid governance");
        governance = governance_;
    }

    /**
     * @notice Commits a new version for a proposal.
     * @dev First committer becomes the owner of proposalId.
     *      Version numbers increment sequentially starting at 1.
     * @param pid Proposal identifier.
     * @param versionHash Hash of canonical manifest combined with prevVersionHash.
     * @param actionHash Hash of deterministic target, value, calldata.
     * @param evidenceRoot Merkle root or combined hash of evidence documents.
     * @return versionNumber The sequential version number (1, 2, ...).
     */
    function commitVersion(
        bytes32 pid,
        bytes32 versionHash,
        bytes32 actionHash,
        bytes32 evidenceRoot
    ) external returns (uint256 versionNumber) {
        require(pid != bytes32(0), "invalid proposalId");
        require(versionHash != bytes32(0), "invalid versionHash");
        require(actionHash != bytes32(0), "invalid actionHash");
        require(evidenceRoot != bytes32(0), "invalid evidenceRoot");

        address owner = proposalOwner[pid];
        if (owner == address(0)) {
            proposalOwner[pid] = msg.sender;
        } else {
            require(msg.sender == owner, "only proposer");
        }

        require(!hasVersionHash[pid][versionHash], "duplicate version hash");
        hasVersionHash[pid][versionHash] = true;

        // Invalidate prior approval upon committing a new version
        if (_approved[pid].versionHash != bytes32(0)) {
            delete _approved[pid];
        }

        _versions[pid].push(Version({
            versionHash: versionHash,
            actionHash: actionHash,
            evidenceRoot: evidenceRoot
        }));

        versionNumber = _versions[pid].length;

        emit VersionCommitted(pid, versionNumber, versionHash, actionHash, evidenceRoot, msg.sender);
    }

    /**
     * @notice Approves the latest committed version for execution.
     * @dev Governance-only. Only the latest version can be approved.
     * @param pid Proposal identifier.
     * @param versionHash The version hash of the latest committed version.
     */
    function approve(bytes32 pid, bytes32 versionHash) external {
        require(msg.sender == governance, "only governance");
        require(pid != bytes32(0), "invalid proposalId");
        require(versionHash != bytes32(0), "invalid versionHash");

        uint256 count = _versions[pid].length;
        require(count > 0, "no committed versions");

        Version storage latest = _versions[pid][count - 1];
        require(latest.versionHash == versionHash, "not latest version");

        _approved[pid] = ApprovedRecord({
            versionHash: latest.versionHash,
            actionHash: latest.actionHash,
            evidenceRoot: latest.evidenceRoot
        });

        emit ProposalApproved(pid, latest.versionHash, latest.actionHash, latest.evidenceRoot);
    }

    /**
     * @notice Returns the approved version, action hash, and evidence root for proposalId.
     * @param pid Proposal identifier.
     */
    function approved(bytes32 pid)
        external
        view
        returns (bytes32 versionHash, bytes32 actionHash, bytes32 evidenceRoot)
    {
        ApprovedRecord storage rec = _approved[pid];
        return (rec.versionHash, rec.actionHash, rec.evidenceRoot);
    }

    /**
     * @notice Returns the latest committed version for proposalId.
     */
    function latestVersion(bytes32 pid)
        external
        view
        returns (uint256 versionNumber, bytes32 versionHash, bytes32 actionHash, bytes32 evidenceRoot)
    {
        uint256 count = _versions[pid].length;
        require(count > 0, "no committed versions");
        Version storage ver = _versions[pid][count - 1];
        return (count, ver.versionHash, ver.actionHash, ver.evidenceRoot);
    }

    /**
     * @notice Returns version data for a specific 1-indexed version number.
     */
    function getVersion(bytes32 pid, uint256 versionNumber)
        external
        view
        returns (bytes32 versionHash, bytes32 actionHash, bytes32 evidenceRoot)
    {
        require(versionNumber > 0 && versionNumber <= _versions[pid].length, "invalid version number");
        Version storage ver = _versions[pid][versionNumber - 1];
        return (ver.versionHash, ver.actionHash, ver.evidenceRoot);
    }

    /**
     * @notice Returns the total number of versions committed for proposalId.
     */
    function versionCount(bytes32 pid) external view returns (uint256) {
        return _versions[pid].length;
    }
}
