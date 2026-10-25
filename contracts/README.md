# Contract scaffold

Stage 0 only: Foundry's Counter sample plus an OpenZeppelin import smoke test.
No registry, treasury, guarded executor, attestation or upgrade implementation exists.

From this directory: `forge build` and `forge test`.
See the root README for tool installation, pinned compiler, dependency setup,
local-only Anvil usage and the current validation results.

`lib/` contains vendored dependencies installed with `--no-git`. OpenZeppelin is
v5.4.0. The initial forge-std snapshot reports package version 1.17.0; it was
installed by `forge init`, without an explicit Git ref. Keep the vendored sources
for the validated snapshot; reinstalling forge-std's default branch can change it.
