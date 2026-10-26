"""Deterministic verification pipeline and rule engine for DAO proposals."""

from dataclasses import asdict, dataclass
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from eth_account import Account
from eth_utils import keccak, to_checksum_address
from web3 import Web3

from app.chain.attest import (
    VERIFIED,
    recover_attestation_signer,
    sign_attestation,
)
from app.chain.client import (
    PK_VERIFIER,
    get_onchain_approved,
    get_web3,
    load_artifact,
    proposal_id_to_bytes32,
)
from app.db import get_db_connection
from app.manifest.builder import verify_manifest_integrity
from app.verification.decode import DecodedTransaction, decode_transaction
from app.verification.simulate import SimulationError, simulate_execution

logger = logging.getLogger(__name__)

VERDICT_VERIFIED = "VERIFIED"
VERDICT_MISMATCH = "MISMATCH"
VERDICT_UNSUPPORTED = "UNSUPPORTED"
VERDICT_UNCERTAIN = "UNCERTAIN"
VERDICT_ALREADY_EXECUTED = "ALREADY_EXECUTED"
STATUS_ALREADY_EXECUTED = "ALREADY_EXECUTED"


@dataclass
class RuleOutcome:
    rule_id: str
    name: str
    status: str  # "PASS", "FAIL", "UNCERTAIN"
    explanation: str
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationReport:
    proposal_id: str
    version: int
    verdict: str
    all_passed: bool
    rules: List[RuleOutcome]
    decoded_tx: Dict[str, Any]
    diff: Dict[str, Any]
    simulation: Dict[str, Any]
    attestation_sig: Optional[str] = None
    deadline: Optional[int] = None
    verifier_address: Optional[str] = None
    error: Optional[str] = None
    executed: bool = False
    status: Optional[str] = None
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "version": self.version,
            "verdict": self.verdict,
            "status": self.status or self.verdict,
            "all_passed": self.all_passed,
            "rules": [r.to_dict() for r in self.rules],
            "decoded_tx": self.decoded_tx,
            "diff": self.diff,
            "simulation": self.simulation,
            "attestation_sig": self.attestation_sig,
            "deadline": self.deadline,
            "verifier_address": self.verifier_address,
            "error": self.error,
            "executed": self.executed,
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
        }


def scan_bytecode(code: bytes) -> Tuple[Set[str], Set[str]]:
    """Scan EVM runtime code for candidate function selectors and control opcodes.

    Heuristic Mechanics & Boundary Guarantees:
    - Scans EVM instructions sequentially.
    - When a PUSH1..PUSH32 instruction (0x60 <= op <= 0x7F) is encountered,
      the parser advances `1 + n` bytes, skipping the `n` immediate-data bytes.
      This ensures that constant bytes inside addresses, hashes, or numbers
      (such as a raw 0x63 or 0xF4 byte) are NOT misinterpreted as opcodes.
    - When `op == 0x63` (PUSH4), if at least 4 immediate bytes remain, the
      candidate 4-byte constant is recorded (e.g. function selector candidate
      in standard Solidity dispatch tables).
    - If a PUSH instruction is truncated at the end of the bytecode, the scanner
      safely terminates without IndexError.

    Security Limitations & Scope:
    - Candidate 4-byte constants include function selectors used in dispatch
      tables (`PUSH4 <selector> EQ ...`), but may also include 4-byte numeric literals.
    - Static opcode scanning is a defensive heuristic filter, NOT a complete
      proof of safety against arbitrary obfuscated bytecode, unaligned jump
      destinations, or dynamic delegatecall targets.
    - Full safety is achieved in defense-in-depth: Rule R6 (storage slot immutability),
      Rule R7 (selector whitelist and optional code hash), and on-chain GuardedExecutor.
    """
    if not code:
        return set(), set()

    i, ops, sels = 0, set(), set()
    code_len = len(code)
    while i < code_len:
        op = code[i]
        if 0x60 <= op <= 0x7F:  # PUSH1..PUSH32
            n = op - 0x5F
            if n == 4 and i + 5 <= code_len:
                sels.add("0x" + code[i + 1 : i + 5].hex().lower())
            i += 1 + n
        else:
            ops.add(op)
            i += 1
    names = {
        "DELEGATECALL": 0xF4,
        "CALLCODE": 0xF2,
        "SELFDESTRUCT": 0xFF,
        "CREATE": 0xF0,
        "CREATE2": 0xF5,
    }
    found_ops = {name for name, byte_val in names.items() if byte_val in ops}
    return found_ops, sels


def evaluate_rules(
    proposal_id: str,
    manifest: Dict[str, Any],
    onchain_approved_tuple: Tuple[str, str, str],
    decoded_tx: DecodedTransaction,
    sim_result: Dict[str, Any],
    w3: Optional[Web3] = None,
) -> Tuple[str, List[RuleOutcome]]:
    """Evaluate deterministic rules R1, R2, R3, R4, R5, R6, R7, R9 in strict order."""
    rules: List[RuleOutcome] = []
    app_vhash, app_ahash, app_eroot = onchain_approved_tuple

    # ----------------------------------------------------
    # Rule R1: Approved version and live governance check
    # ----------------------------------------------------
    from app.manifest.canon import canonicalize_manifest
    from app.manifest.hashes import INITIAL_PREV_VERSION_HASH, compute_version_hash

    canon_bytes = canonicalize_manifest(manifest)
    prev_vhash = manifest.get("prevVersionHash", INITIAL_PREV_VERSION_HASH)
    recomputed_vhash = compute_version_hash(canon_bytes, prev_vhash)
    manifest_vhash = manifest.get("version_hash") or manifest.get("versionHash") or recomputed_vhash
    manifest_eroot = manifest.get("evidenceRoot") or manifest.get("evidence_root", "")

    r1_pass = (
        app_vhash != "0x" + "00" * 32
        and (manifest_vhash.lower() == app_vhash.lower() or recomputed_vhash.lower() == app_vhash.lower())
        and manifest_eroot.lower() == app_eroot.lower()
    )
    r1_status = "PASS" if r1_pass else "FAIL"
    r1_expl = (
        "Approved version hash and evidence root match on-chain GovernanceRegistry record."
        if r1_pass
        else f"Version hash mismatch or no live approval: recomputed {recomputed_vhash} vs on-chain {app_vhash}"
    )
    rules.append(
        RuleOutcome(
            rule_id="R1",
            name="Approved Version and Governance Commitment",
            status=r1_status,
            explanation=r1_expl,
            evidence={
                "recomputed_version_hash": recomputed_vhash,
                "approved_version_hash": app_vhash,
                "manifest_evidence_root": manifest_eroot,
                "approved_evidence_root": app_eroot,
            },
        )
    )

    # ----------------------------------------------------
    # Rule R2: Action hash and calldata field match
    # ----------------------------------------------------
    action_hash_match = decoded_tx.action_hash.lower() == app_ahash.lower()
    fields_match = decoded_tx.matches_manifest

    r2_pass = action_hash_match and fields_match and decoded_tx.is_supported
    r2_status = "PASS" if r2_pass else "FAIL"
    r2_expl = (
        "Submitted transaction actionHash and decoded fields match the approved action exactly."
        if r2_pass
        else f"Transaction deviates from approved action: actionHash match={action_hash_match}, fields match={fields_match}"
    )
    rules.append(
        RuleOutcome(
            rule_id="R2",
            name="Action Hash and Decoded Transaction Parameters",
            status=r2_status,
            explanation=r2_expl,
            evidence={
                "submitted_action_hash": decoded_tx.action_hash,
                "approved_action_hash": app_ahash,
                "diff": decoded_tx.diff,
                "decoding_error": decoded_tx.decoding_error,
            },
        )
    )

    # ----------------------------------------------------
    # Rule R3: Token outflow envelope check
    # ----------------------------------------------------
    action = manifest.get("action", {})
    envelope = manifest.get("envelope", {})
    max_outflows = envelope.get("maxTokenOutflow", {})
    token = action.get("token", "").lower()
    max_allowed = int(max_outflows.get(token, action.get("amountRaw", 0)))
    approved_amount = int(action.get("amountRaw", 0))

    sim_outflow = sim_result.get("treasury_outflow", 0)
    sim_inflow = sim_result.get("recipient_inflow", 0)
    sim_success = sim_result.get("success", False)

    r3_pass = sim_success and (sim_outflow <= max_allowed) and (sim_inflow == approved_amount)
    r3_status = "PASS" if r3_pass else "FAIL"
    r3_expl = (
        f"Treasury outflow ({sim_outflow}) is within limit ({max_allowed}) and recipient received exact amount ({sim_inflow})."
        if r3_pass
        else f"Token outflow violation: outflow={sim_outflow} (max {max_allowed}), recipient inflow={sim_inflow} (expected {approved_amount})"
    )
    rules.append(
        RuleOutcome(
            rule_id="R3",
            name="Token Outflow Envelope Compliance",
            status=r3_status,
            explanation=r3_expl,
            evidence={
                "treasury_outflow": sim_outflow,
                "max_allowed_outflow": max_allowed,
                "recipient_inflow": sim_inflow,
                "expected_inflow": approved_amount,
                "simulation_success": sim_success,
            },
        )
    )

    # ----------------------------------------------------
    # Rule R4: Unexpected balance increases
    # ----------------------------------------------------
    is_proof = sim_result.get("proof_mode", False) or sim_result.get("simulation_mode") == "proof_onchain"
    r4_prefix = "[REDUCED IN PROOF MODE] Evaluated via static calldata & view calls without full EVM state tracing. " if is_proof else ""

    unexpected_gains = sim_result.get("unexpected_gains", {})
    r4_pass = len(unexpected_gains) == 0
    r4_status = "PASS" if r4_pass else "FAIL"
    r4_expl = (
        r4_prefix + "Zero unexpected token balance increases observed across watched addresses."
        if r4_pass
        else r4_prefix + f"Unexpected token gains detected: {unexpected_gains}"
    )
    rules.append(
        RuleOutcome(
            rule_id="R4",
            name="Prohibited Balance Increases",
            status=r4_status,
            explanation=r4_expl,
            evidence={"unexpected_gains": unexpected_gains},
        )
    )

    # ----------------------------------------------------
    # Rule R5: Allowance and approval changes
    # ----------------------------------------------------
    allow_approvals = envelope.get("allowApprovals", False)
    allowance_changes = sim_result.get("allowance_changes", {})
    r5_pass = allow_approvals or len(allowance_changes) == 0
    r5_status = "PASS" if r5_pass else "FAIL"
    r5_prefix = "[REDUCED IN PROOF MODE] Evaluated via static calldata & view calls without full EVM state tracing. " if is_proof else ""
    r5_expl = (
        r5_prefix + "Treasury allowances remained strictly unchanged."
        if r5_pass
        else r5_prefix + f"Unauthorized allowance changes detected: {allowance_changes}"
    )
    rules.append(
        RuleOutcome(
            rule_id="R5",
            name="Allowance and Approval Modifications",
            status=r5_status,
            explanation=r5_expl,
            evidence={"allowance_changes": allowance_changes, "allow_approvals": allow_approvals},
        )
    )

    # ----------------------------------------------------
    # Rule R6: Implementation slot changes
    # ----------------------------------------------------
    allow_impl_change = envelope.get("allowImplChange", False)
    slot_changes = sim_result.get("slot_changes", {})
    action = manifest.get("action", {})
    kind = action.get("kind", "erc20_payout")
    is_proof_mode = bool(sim_result.get("proof_mode", False))

    # Strengthening for proof mode: static inspection of calldata selector and EIP-1967 storage slots
    upgrade_selectors = {"0x3659cfe6", "0x4f1ef286", "0x8f283970", "0x5c19a95c"}
    target_selector = (decoded_tx.selector or "").lower()

    unauthorized_upgrade_call = (not allow_impl_change and target_selector in upgrade_selectors)

    # Inspect EIP-1967 implementation and admin slot via eth_getStorageAt if w3 is available
    eip1967_impl_slot = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    eip1967_admin_slot = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
    target_storage_impl = ""
    target_storage_admin = ""
    if w3 is not None and decoded_tx.target:
        try:
            cs_target = to_checksum_address(decoded_tx.target)
            raw_impl = w3.eth.get_storage_at(cs_target, eip1967_impl_slot)
            target_storage_impl = "0x" + raw_impl.hex()
            raw_admin = w3.eth.get_storage_at(cs_target, eip1967_admin_slot)
            target_storage_admin = "0x" + raw_admin.hex()
        except Exception:
            pass

    r6_name = "Implementation Slot Immutability [REDUCED IN PROOF MODE]" if is_proof_mode else "Implementation Slot Immutability"

    if unauthorized_upgrade_call:
        r6_pass = False
        r6_expl = f"Unauthorized upgrade selector {target_selector} detected in calldata when allowImplChange is False."
    elif kind == "proxy_upgrade":
        expected_proxy = (action.get("proxy") or "").lower()
        expected_impl = (action.get("newImpl") or "").lower()

        if not allow_impl_change:
            r6_pass = False
            r6_expl = "Implementation change not permitted by envelope policy (allowImplChange is False)."
        elif len(slot_changes) == 0:
            r6_pass = False
            r6_expl = "Implementation slot did not update to new implementation during simulation."
        else:
            invalid_changes = []
            for addr, change in slot_changes.items():
                if addr.lower() != expected_proxy:
                    invalid_changes.append(f"Unexpected contract {addr} slot changed")
                else:
                    after_slot = change.get("after", "")
                    after_addr = "0x" + after_slot[-40:].lower()
                    if after_addr != expected_impl:
                        invalid_changes.append(f"Slot implementation {after_addr} != expected {expected_impl}")
            if invalid_changes:
                r6_pass = False
                r6_expl = f"Unauthorized implementation slot change: {'; '.join(invalid_changes)}"
            else:
                r6_pass = True
                r6_expl = f"EIP-1967 implementation slot correctly updated to approved implementation ({expected_impl})."
    else:
        r6_pass = allow_impl_change or len(slot_changes) == 0
        if r6_pass:
            if is_proof_mode:
                r6_expl = (
                    "[REDUCED IN PROOF MODE] Evaluated via static calldata & EIP-1967 storage slot view inspection "
                    "without full EVM state tracing. Storage slots and selector remain unmutated."
                )
            else:
                r6_expl = "EIP-1967 implementation storage slots remained unchanged."
        else:
            r6_expl = f"Unauthorized implementation slot changes detected: {slot_changes}"

    r6_status = "PASS" if r6_pass else "FAIL"
    evidence_dict: Dict[str, Any] = {
        "slot_changes": slot_changes,
        "allow_impl_change": allow_impl_change,
        "reduced_in_proof_mode": is_proof_mode,
        "target_selector": target_selector,
    }
    if target_storage_impl:
        evidence_dict["eip1967_impl_slot"] = target_storage_impl
    if target_storage_admin:
        evidence_dict["eip1967_admin_slot"] = target_storage_admin

    rules.append(
        RuleOutcome(
            rule_id="R6",
            name=r6_name,
            status=r6_status,
            explanation=r6_expl,
            evidence=evidence_dict,
        )
    )

    # ----------------------------------------------------
    # Rule R7: Undeclared selector (upgrade scenario)
    # ----------------------------------------------------
    if kind == "proxy_upgrade":
        new_impl_addr = (action.get("newImpl") or "").lower()
        declared_selectors = {
            (s if s.startswith("0x") else f"0x{s}").lower()
            for s in action.get("declaredSelectors", [])
        }
        expected_code_hash = action.get("expectedImplCodeHash")

        active_w3 = w3 if w3 is not None else get_web3()
        code_bytes = b""
        if new_impl_addr:
            try:
                code_bytes = bytes(active_w3.eth.get_code(to_checksum_address(new_impl_addr)))
            except Exception:
                code_bytes = b""

        actual_code_hash = "0x" + keccak(code_bytes).hex().lower() if code_bytes else ""
        code_hash_match = True
        if expected_code_hash and actual_code_hash.lower() != expected_code_hash.lower():
            code_hash_match = False

        candidate_ops, candidate_sels = scan_bytecode(code_bytes)

        # Baseline selectors from previous proxy implementation
        proxy_addr = (action.get("proxy") or "").lower()
        baseline_code_bytes = b""
        if proxy_addr:
            try:
                from app.verification.simulate import EIP1967_IMPL_SLOT
                base_slot = active_w3.eth.get_storage_at(to_checksum_address(proxy_addr), EIP1967_IMPL_SLOT)
                base_impl_addr = "0x" + base_slot[-20:].hex().lower()
                if int(base_impl_addr, 16) != 0:
                    baseline_code_bytes = bytes(active_w3.eth.get_code(to_checksum_address(base_impl_addr)))
            except Exception:
                baseline_code_bytes = b""

        baseline_ops, baseline_sels = scan_bytecode(baseline_code_bytes)

        whitelist = baseline_sels | declared_selectors
        undeclared_sels = candidate_sels - whitelist
        new_ops = candidate_ops - baseline_ops

        if not code_hash_match:
            r7_pass = False
            r7_expl = f"Implementation bytecode hash mismatch: expected {expected_code_hash}, got {actual_code_hash}"
        elif len(undeclared_sels) > 0:
            r7_pass = False
            r7_expl = f"Undeclared selector candidates detected in implementation bytecode: {sorted(list(undeclared_sels))}"
        else:
            r7_pass = True
            r7_expl = "All candidate selectors in new implementation are within approved scope (baseline ∪ declared)."

        r7_status = "PASS" if r7_pass else "FAIL"
        rules.append(
            RuleOutcome(
                rule_id="R7",
                name="Selector Whitelist / Scope",
                status=r7_status,
                explanation=r7_expl,
                evidence={
                    "undeclared_selectors": sorted(list(undeclared_sels)),
                    "declared_selectors": sorted(list(declared_selectors)),
                    "candidate_selectors_count": len(candidate_sels),
                    "new_opcodes_relative_to_baseline": sorted(list(new_ops)),
                    "code_hash": actual_code_hash,
                },
            )
        )
    else:
        r7_pass = decoded_tx.is_supported and decoded_tx.selector != "0x4f1ef286"
        r7_status = "PASS" if r7_pass else "FAIL"
        rules.append(
            RuleOutcome(
                rule_id="R7",
                name="Selector Whitelist / Scope",
                status=r7_status,
                explanation="Selector is within approved scope." if r7_pass else "Undeclared or disallowed selector.",
                evidence={"selector": decoded_tx.selector, "is_supported": decoded_tx.is_supported},
            )
        )

    # ----------------------------------------------------
    # Rule R9: Contract owner / role changes
    # ----------------------------------------------------
    allow_role_changes = envelope.get("allowRoleChanges", False)
    owner_changes = sim_result.get("owner_changes", {})
    r9_pass = allow_role_changes or len(owner_changes) == 0
    r9_status = "PASS" if r9_pass else "FAIL"
    r9_prefix = "[REDUCED IN PROOF MODE] Evaluated via static calldata & view calls without full EVM state tracing. " if is_proof else ""
    r9_expl = (
        r9_prefix + "Contract ownership and access roles remained unchanged."
        if r9_pass
        else r9_prefix + f"Unauthorized role changes detected: {owner_changes}"
    )
    rules.append(
        RuleOutcome(
            rule_id="R9",
            name="Owner and Access Control Role Immutability",
            status=r9_status,
            explanation=r9_expl,
            evidence={"owner_changes": owner_changes, "allow_role_changes": allow_role_changes},
        )
    )

    # ----------------------------------------------------
    # Aggregate Verdict
    # ----------------------------------------------------
    # Precedence:
    # 1. Observation/simulation failure -> UNCERTAIN
    # 2. Unsupported selector/action -> UNSUPPORTED
    # 3. Any rule FAIL -> MISMATCH
    # 4. All PASS -> VERIFIED
    if not sim_result.get("restoration_verified", False):
        return VERDICT_UNCERTAIN, rules

    if not decoded_tx.is_supported:
        return VERDICT_UNSUPPORTED, rules

    if any(r.status == "FAIL" for r in rules):
        return VERDICT_MISMATCH, rules

    if any(r.status == "UNCERTAIN" for r in rules):
        return VERDICT_UNCERTAIN, rules

    return VERDICT_VERIFIED, rules


def verify_proposal_transaction(
    proposal_id: str,
    target: str,
    value: int,
    data: Union[str, bytes],
    registry_address: str,
    treasury_address: str,
    executor_address: str,
    verifier_private_key: str = PK_VERIFIER,
    ttl_seconds: int = 3600,
    rpc_url: Optional[str] = None,
    db_path: Optional[str] = None,
) -> VerificationReport:
    """Run full verification pipeline: decode, simulate, evaluate rules, and attest if VERIFIED."""
    w3 = get_web3(rpc_url)
    chain_id = w3.eth.chain_id

    # 1. Load manifest record from database
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM manifests WHERE proposal_id = ? ORDER BY version DESC LIMIT 1",
            (proposal_id,),
        )
        row = cursor.fetchone()

    if not row:
        return VerificationReport(
            proposal_id=proposal_id,
            version=0,
            verdict=VERDICT_UNCERTAIN,
            all_passed=False,
            rules=[],
            decoded_tx={},
            diff={},
            simulation={},
            error=f"No manifest found for proposal '{proposal_id}'",
        )

    manifest_dict = json.loads(row["manifest_dict"])
    version = row["version"]

    # 2. Strict decoding & field comparison against manifest
    decoded_tx = decode_transaction(
        target=target,
        value=value,
        data=data,
        manifest=manifest_dict,
    )

    # 3. Read live on-chain approved record
    onchain_tuple = get_onchain_approved(registry_address, proposal_id, rpc_url=rpc_url)

    # 3b. Check if already executed on-chain or in database BEFORE running simulation
    pid_b32 = proposal_id_to_bytes32(proposal_id)
    is_executed_onchain = False
    executor_contract = None
    if executor_address:
        try:
            executor_artifact = load_artifact("GuardedExecutor")
            executor_contract = w3.eth.contract(
                address=Web3.to_checksum_address(executor_address),
                abi=executor_artifact["abi"],
            )
            is_executed_onchain = bool(executor_contract.functions.executed(pid_b32).call())
        except Exception as e:
            logger.debug(f"Could not query executor.executed on-chain: {e}")

    orig_tx_hash = None
    orig_block_number = None
    db_executed = False
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tx_hash, block_number, executed FROM verifications
            WHERE proposal_id = ? AND executed = 1
            ORDER BY rowid DESC LIMIT 1
            """,
            (proposal_id,),
        )
        exec_row = cursor.fetchone()
        if exec_row:
            db_executed = bool(exec_row["executed"])
            orig_tx_hash = exec_row["tx_hash"]
            orig_block_number = exec_row["block_number"]

    # If executed on-chain but SQLite verifications table has no tx info, query ExecutionSucceeded event
    if is_executed_onchain and (not orig_tx_hash or not orig_block_number) and executor_contract is not None:
        try:
            events = executor_contract.events.ExecutionSucceeded().get_logs(
                from_block=0,
                argument_filters={"proposalId": pid_b32},
            )
            if events:
                orig_tx_hash = events[-1].transactionHash.hex()
                orig_block_number = events[-1].blockNumber
        except Exception as e:
            logger.debug(f"Could not retrieve ExecutionSucceeded events: {e}")

    if orig_tx_hash and not orig_tx_hash.startswith("0x"):
        orig_tx_hash = "0x" + orig_tx_hash

    if is_executed_onchain or db_executed:
        logger.info(
            f"Proposal '{proposal_id}' has already been executed on-chain (tx: {orig_tx_hash}, block: {orig_block_number}). "
            f"Returning ALREADY_EXECUTED explicit result before simulation."
        )
        return VerificationReport(
            proposal_id=proposal_id,
            version=version,
            verdict=STATUS_ALREADY_EXECUTED,
            all_passed=False,
            rules=[],
            decoded_tx=decoded_tx.to_dict(),
            diff=decoded_tx.diff,
            simulation={
                "success": True,
                "status": STATUS_ALREADY_EXECUTED,
                "skipped": True,
                "message": f"Proposal '{proposal_id}' has already been executed on-chain; simulation skipped to prevent false outflow violation.",
            },
            attestation_sig=None,
            deadline=None,
            verifier_address=Account.from_key(verifier_private_key).address,
            error=f"Proposal '{proposal_id}' has already been executed on-chain (replay blocked).",
            executed=True,
            status=STATUS_ALREADY_EXECUTED,
            tx_hash=orig_tx_hash,
            block_number=orig_block_number,
        )

    # 4. EVM simulation
    try:
        sim_result = simulate_execution(
            w3=w3,
            treasury_address=treasury_address,
            executor_address=executor_address,
            target=target,
            value=value,
            data=data,
            manifest=manifest_dict,
            token_address=manifest_dict.get("action", {}).get("token"),
        )
    except SimulationError as sim_err:
        logger.error(f"Simulation failed: {sim_err}")
        sim_result = {
            "success": False,
            "tx_status": 0,
            "revert_reason": str(sim_err),
            "restoration_verified": False,
            "treasury_outflow": 0,
            "recipient_inflow": 0,
            "unexpected_gains": {},
            "allowance_changes": {},
            "slot_changes": {},
            "owner_changes": {},
            "dynamic_addresses": [],
            "discovery_cap_reached": False,
            "logs_count": 0,
            "baseline_state": {},
            "post_state": {},
        }

    # 5. Rule evaluation & verdict aggregation
    verdict, rules = evaluate_rules(
        proposal_id=proposal_id,
        manifest=manifest_dict,
        onchain_approved_tuple=onchain_tuple,
        decoded_tx=decoded_tx,
        sim_result=sim_result,
        w3=w3,
    )

    all_passed = verdict == VERDICT_VERIFIED
    attestation_sig = None
    deadline = None
    verifier_addr = Account.from_key(verifier_private_key).address

    # 6. EIP-712 Attestation only if VERIFIED
    if all_passed:
        latest_block = w3.eth.get_block("latest")
        deadline = int(latest_block["timestamp"]) + int(ttl_seconds)

        raw_sig = sign_attestation(
            private_key=verifier_private_key,
            proposal_id=proposal_id_to_bytes32(proposal_id),
            version_hash=manifest_dict.get("versionHash") or row["version_hash"],
            action_hash=decoded_tx.action_hash,
            evidence_root=manifest_dict.get("evidenceRoot") or row["evidence_root"],
            verdict=VERIFIED,
            deadline=deadline,
            chain_id=chain_id,
            verifying_contract=executor_address,
        )
        attestation_sig = "0x" + raw_sig.hex()

    # 7. Persist audit trail in verifications table
    verif_id = f"vrf_{proposal_id}_{version}_{w3.eth.block_number}"
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO verifications (
                id, proposal_id, version, target, value, calldata, action_hash,
                verdict, rules_json, diff_json, simulation_json, attestation_sig,
                deadline, executed, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
            """,
            (
                verif_id,
                proposal_id,
                version,
                target,
                str(value),
                "0x" + decoded_tx.raw_data.hex(),
                decoded_tx.action_hash,
                verdict,
                json.dumps([r.to_dict() for r in rules]),
                json.dumps(decoded_tx.diff),
                json.dumps({
                    "success": sim_result.get("success"),
                    "treasury_outflow": sim_result.get("treasury_outflow"),
                    "recipient_inflow": sim_result.get("recipient_inflow"),
                    "unexpected_gains": sim_result.get("unexpected_gains"),
                    "allowance_changes": sim_result.get("allowance_changes"),
                    "slot_changes": sim_result.get("slot_changes"),
                    "owner_changes": sim_result.get("owner_changes"),
                    "restoration_verified": sim_result.get("restoration_verified", True),
                    "revert_reason": sim_result.get("revert_reason"),
                    "baseline_state": sim_result.get("baseline_state", {}),
                    "post_state": sim_result.get("post_state", {}),
                }),
                attestation_sig,
                deadline,
            ),
        )

    return VerificationReport(
        proposal_id=proposal_id,
        version=version,
        verdict=verdict,
        all_passed=all_passed,
        rules=rules,
        decoded_tx=decoded_tx.to_dict(),
        diff=decoded_tx.diff,
        simulation={
            "success": sim_result.get("success"),
            "treasury_outflow": sim_result.get("treasury_outflow"),
            "recipient_inflow": sim_result.get("recipient_inflow"),
            "unexpected_gains": sim_result.get("unexpected_gains"),
            "allowance_changes": sim_result.get("allowance_changes"),
            "slot_changes": sim_result.get("slot_changes"),
            "owner_changes": sim_result.get("owner_changes"),
            "restoration_verified": sim_result.get("restoration_verified"),
            "revert_reason": sim_result.get("revert_reason"),
            "baseline_state": sim_result.get("baseline_state", {}),
            "post_state": sim_result.get("post_state", {}),
        },
        attestation_sig=attestation_sig,
        deadline=deadline,
        verifier_address=verifier_addr,
        error=None,
    )
