# Frontend redesign decisions

2026-10-26 — Work in nested cascade-4.1 checkout on abhigyan-frontend; user explicitly restricted GitHub pushes to this branch, and enclosing checkout has unrelated deletions.
2026-10-26 — Stage 0 creates documentation only; supplied builder prompt requires human plan approval and independent review before Stage 1.
2026-10-26 — Retain DAO Accountability Engine as product name; repository, backend and reviewer charter agree.
2026-10-26 — Scenario C means Clean reset and seed; show Allowed · Reset as expected mark and Reset complete as result, with payment comparison not applicable, matching runner semantics.
2026-10-26 — Do not describe C as an entire chain wipe; implementation clears selected demo records and deploys/seeds contracts.
2026-10-26 — Default to labelled offline demo data; live runner depends on absent deploy_and_seed.py and absent upgrade contract sources.
2026-10-26 — Local live API base proposed as http://127.0.0.1:8000 via public VITE_API_BASE_URL; README supplies address, not proof of uptime.
2026-10-26 — Reuse C as explicit live reset only after integration verification; never invent /reset, rely on ignored reset_first, or silently simulate live completion.
2026-10-26 — Preserve React/TypeScript/Vite/Oxlint toolchain and bootstrap; current App has no reusable workflow/API logic.
2026-10-26 — Propose Context/reducer plus React Router; isolated workspace records share one live chain and one global live-operation lock.
2026-10-26 — Treat success=true as runner completion, not allowance; adapt verdict/execution/reset separately and fail closed on missing or contradictory evidence.
2026-10-26 — Keep exact token amounts as integer strings/BigInt; do not infer unknown balances as zero or display unsourced USD valuations.
2026-10-26 — Propose graphite/ink-green and off-white with amber, green/red only for Allowed/Blocked; all theme pairs require measured contrast in Stage 1.
2026-10-26 — Propose self-hosted Space Grotesk, Source Sans 3 and drawer-only IBM Plex Mono; verify font licenses and record sources before inclusion.
2026-10-26 — Build original inline SVG/CSS lock, restrained Motion, landing-only Lenis; verify package compatibility/licenses before installation.
2026-10-26 — Use available measured/manual design checks if named external design databases/detectors are unavailable; never claim unrun tools.
2026-10-26 — Explain approved intent versus protected execution without implying OpenZeppelin Governor permits post-vote calldata substitution.
2026-10-26 — Keep reviewer-owned files untouched and preserve existing reviewer commits; builder handoffs carry actual checks and known weaknesses.
