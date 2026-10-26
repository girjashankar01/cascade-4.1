# QUESTIONS — DAO Accountability Engine Frontend

Items requiring confirmation from the backend owner before the front end can be accurate.

---

## Q1: What does Scenario C actually do?

**Status:** OPEN — ASSUMPTION in PROJECT-TRUTH.md  
**Default used:** The Stage 3 handoff shows a disputed proposal with $5.0M vs $5.8M conflict blocking manifest confirmation. Treating C as the conflicting-evidence case where confirmation is blocked before execution.  
**Why it matters:** The current front end incorrectly implemented C as "environment reset". The pitch walkthrough step 2 (Evidence, 90 s) covers the conflict scenario — C may be that demo path rather than a `/scenarios/C/run` execution.

---

## Q2: Which rule numbering is final?

**Status:** OPEN  
**Default used:** Front end will display rule ID and message text as returned by the backend. No rule meanings are hard-coded.  
**Why it matters:** The build guide and Stage 3 handoff list conflicting rule numbers. Until the backend owner confirms, fixtures will label rules as "Demo data — rule ID subject to change".

---

## Q3: Does `/scenarios/{name}/run` exist or is it planned?

**Status:** OPEN — marked "not yet built" in truth file  
**Default used:** Execution page runs from fixtures with an adapter ready to swap in the real endpoint.  
**Why it matters:** If the endpoint exists, the scenario runner should call it. If not, fixtures are correct.

---

## Q4: What are the exact Anvil account addresses after `deploy_and_seed.py`?

**Status:** OPEN — cannot run the seed script (hard safety rule 4)  
**Default used:** Using role names (Proposer, Governance, Verifier, Attacker, Honest recipient) without hard-coded addresses. The truth file lists account indices 0–5.  
**Why it matters:** Real addresses are needed to show "Approved recipient: 0x9965…" accurately. Will read from `expected_claims.json` where available.

---

## Q5: Are the sources/claims/conflicts routes live and what are their exact paths?

**Status:** OPEN  
**Default used:** Fixtures; reading `backend/app/api/routes.py` to find real paths.  
**Why it matters:** The Proposal page needs to hit real data if the backend is running.
