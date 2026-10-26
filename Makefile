# CASCADE 4.1 Makefile
# Canonical developer and deployment workflow targets.
# All Python commands use `uv run --project backend` exclusively.

.PHONY: help preflight deploy record verify-deploy dry-run proof check-proof api web test test-backend test-contracts test-frontend

help:
	@echo "CASCADE 4.1 Development & Sepolia Operations"
	@echo "Available targets:"
	@echo "  make preflight     - Validate Sepolia RPC, keystore, addresses, and balances"
	@echo "  make deploy        - Show manual Forge broadcast command (never broadcasts automatically)"
	@echo "  make record        - Parse broadcast artifacts into data/deployments.proof.json"
	@echo "  make verify-deploy - Verify on-chain contract wiring and bytecode (view calls only)"
	@echo "  make dry-run       - Execute dry-run proof publishing (no transactions broadcast)"
	@echo "  make proof         - Execute real proof publishing and replay attack on Sepolia"
	@echo "  make check-proof   - Independently validate on-chain receipts, logs, and secret hygiene"
	@echo "  make api           - Start FastAPI backend server in proof mode on port 8000"
	@echo "  make web           - Start Vite frontend dev server on port 5173"
	@echo "  make test          - Run full backend, contract, and frontend test suites"

preflight:
	@bash scripts/preflight_deploy.sh

deploy:
	@echo "================================================================================"
	@echo "MANUAL DEPLOYMENT STEP REQUIRED"
	@echo "================================================================================"
	@echo "Automated broadcast is blocked to prevent unintended gas expenditure."
	@echo "Execute the following command manually to broadcast to Ethereum Sepolia:"
	@echo ""
	@echo "  cd contracts && forge script script/DeployProof.s.sol \\"
	@echo "    --rpc-url \"\$$AMOY_RPC\" \\"
	@echo "    --account \"\$${DEPLOYER_ACCOUNT:-amoy-deployer}\" \\"
	@echo "    --broadcast"
	@echo "================================================================================"

record:
	uv run --project backend python scripts/write_proof_deployments.py

verify-deploy:
	uv run --project backend python scripts/verify_deployment.py

dry-run:
	uv run --project backend python scripts/publish_proof.py --dry-run

proof:
	uv run --project backend python scripts/publish_proof.py --with-replay

check-proof:
	uv run --project backend python scripts/check_proof.py

api:
	CHAIN_MODE=proof uv run --project backend uvicorn app.main:app --host 0.0.0.0 --port 8000

web:
	cd frontend && npm run dev

test: test-backend test-contracts test-frontend
	@echo "All tests passed successfully!"

test-backend:
	uv run --project backend pytest -q

test-contracts:
	cd contracts && forge test -q

test-frontend:
	cd frontend && npm test && npm run lint && npm run build
