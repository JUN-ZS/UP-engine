# IGE S0–S7 Method Registry v0.1 (draft) + queryable loader

This package revises the prior IGE workflow optimization using UP-engine PR #12 as the normative operating contract.

## Contents

- `ARCHITECTURE_DECISION.md` — S0–S7 decisions, conditional four-state route, three backend families, current blockers and non-claims.
- `method_registry.json` — a draft registry seed that marks implementation maturity honestly.
- `COMFYUI_NODE_MAPPING.md` — maps the pasted workflow node IDs to stages and required proof.
- `ACCEPTANCE_MATRIX.md` — hard gates and anti-tautology rules.
- `validate_registry.py` — structural validation (bridges to `src/ige/method_registry.py` when present).
- `test_registry.py` — small regression tests for the registry validator.
- `../src/ige/method_registry.py` — **new**: versioned JSON loader + fail-closed `resolve()` / query API.
- `../contracts/IGE_S0_S7_METHOD_REGISTRY_V0.1.json` — versioned seed copy of `method_registry.json`.
- `../tests/test_method_registry.py` — loader unit tests (duplicate ID, missing test_ids, no auto edit_permission, load+query).
- `../ADOPTION_NOTE_zh.md` — Chinese adoption note (hierarchy correction, §8 order, non-claims).

## Validate (original package)

```bash
python validate_registry.py method_registry.json
python -m unittest -v test_registry.py
```

## Loader (step 1 of §8)

```bash
cd /path/to/ige-pr12
PYTHONPATH=src python -m ige.method_registry contracts/IGE_S0_S7_METHOD_REGISTRY_V0.1.json
PYTHONPATH=src python -m unittest -v tests.test_method_registry
```

## Status

This is a design + **queryable registry loader** package. It does **not** include ComfyUI custom-node implementations, a patched complete workflow JSON, live inference results, or a production-wired import inside the UP-engine feature branch. Do not use it to claim S7 acceptance.

## GitHub provenance

- PR #12: `4bc4bd472f1cc4188c4b1feaf94ab8f0d140ad15`
- PR #15: `0446130fb012a053fde8b8318617fb22d563d6f6`
- PR #5: `44744150d9093088fb1f575e746cc979f06787b9`
- PR #11: `1526ef56d7f341ffebd4e3a2b80cc268b16a3b83`

All are references only; this package does not merge or modify those PRs.
