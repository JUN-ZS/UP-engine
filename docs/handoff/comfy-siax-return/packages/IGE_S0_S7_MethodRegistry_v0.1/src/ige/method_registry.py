#!/usr/bin/env python3
"""Queryable Method Registry loader for IGE S0–S7 (PR #12 contract seed).

Authority: PR #12 Geometry Lock / AI Usage Guide (highest operating contract).
Policy: fail_closed. default_edit_permission = false.
AI / loader NEVER auto-grants edit_permission.

This module loads a versioned JSON registry, validates structure, and resolves
methods by method_id / stage / capability / backend_id / implementation_status.

Non-claims:
- Does NOT wire fossils (research/shq_v9) into production.
- Does NOT run ComfyUI / GPU inference.
- Does NOT merge PRs #12/#15/#5/#11/#7/#9/#10.
- DIFF evidence ≠ edit_permission.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Union

PathLike = Union[str, Path]

REQUIRED_METHOD_FIELDS = frozenset(
    {
        "method_id",
        "version",
        "stage",
        "capability",
        "implementation_status",
        "entrypoint",
        "preconditions",
        "inputs",
        "outputs",
        "edit_permission",
        "failure_codes",
        "test_ids",
        "acceptance",
    }
)

ALLOWED_STATUSES = frozenset(
    {
        "implemented_candidate_only_in_pr5",
        "implemented_experimental_in_pr11_not_live_comfy_verified",
        "implemented_optional_runtime_in_pr5_inference_not_run_by_pr_ci",
        "workflow_candidate_not_live_verified",
        "research_only_fixed_debug_scaffold_not_production_wired",
        "research_only_non_generative",
        "research_only_external_donor_transfer_not_destination_tile_diffusion",
        "partial_non_generative_in_pr5",
        "research_proxy_only_not_calibrated_3d",
    }
)

EXPECTED_SCHEMA = "ige-method-registry/0.1"
DEFAULT_CONTRACT_NAME = "IGE_S0_S7_METHOD_REGISTRY_V0.1.json"


class MethodRegistryError(Exception):
    """Base fail-closed registry error."""


class RegistryValidationError(MethodRegistryError):
    """Registry JSON failed structural / policy validation."""

    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        msg = "; ".join(self.errors) if self.errors else "validation failed"
        super().__init__(msg)


class MethodNotFoundError(MethodRegistryError):
    """resolve() could not find a matching method under fail-closed policy."""

    def __init__(self, method_id: str, detail: str = ""):
        self.method_id = method_id
        suffix = f": {detail}" if detail else ""
        super().__init__(f"method not found (fail_closed): {method_id}{suffix}")


def validate_registry_data(data: Mapping[str, Any]) -> list[str]:
    """Validate registry document. Returns a list of error strings (empty = PASS).

    Enforces:
    - schema / fail_closed policy
    - required fields, unique method_id
    - non-empty test_ids
    - edit_permission must be False for every method (AI cannot self-grant)
    - default_edit_permission must be False when present
    """
    errors: list[str] = []
    if data.get("registry_schema") != EXPECTED_SCHEMA:
        errors.append(f"registry_schema must be {EXPECTED_SCHEMA}")
    if data.get("policy") != "fail_closed":
        errors.append("policy must be fail_closed")
    if "default_edit_permission" in data and data.get("default_edit_permission") is not False:
        errors.append("default_edit_permission must be false")

    methods = data.get("methods")
    if not isinstance(methods, list) or not methods:
        return errors + ["methods must be a non-empty array"]

    seen: set[str] = set()
    for idx, method in enumerate(methods):
        prefix = f"methods[{idx}]"
        if not isinstance(method, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_METHOD_FIELDS - set(method)
        if missing:
            errors.append(f"{prefix} missing fields: {sorted(missing)}")
        mid = method.get("method_id")
        if not isinstance(mid, str) or not mid:
            errors.append(f"{prefix}.method_id must be a non-empty string")
        elif mid in seen:
            errors.append(f"duplicate method_id: {mid}")
        else:
            seen.add(mid)
        if method.get("implementation_status") not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.implementation_status is not an allowed maturity label")
        # Hard policy: registry seed may never grant write; AI cannot auto-set True.
        if method.get("edit_permission") is not False:
            errors.append(f"{prefix}.edit_permission must default to false")
        for key in ("stage", "preconditions", "inputs", "outputs", "failure_codes", "test_ids"):
            if not isinstance(method.get(key), list):
                errors.append(f"{prefix}.{key} must be an array")
        if not method.get("test_ids"):
            errors.append(f"{prefix}.test_ids must not be empty")
        if not method.get("acceptance"):
            errors.append(f"{prefix}.acceptance must describe an independent gate")
    return errors


def _default_contract_candidates() -> list[Path]:
    here = Path(__file__).resolve()
    roots = [
        here.parents[2] / "contracts" / DEFAULT_CONTRACT_NAME,  # .../ige-pr12/contracts
        here.parents[3] / "contracts" / DEFAULT_CONTRACT_NAME if len(here.parents) > 3 else None,
        Path.cwd() / "contracts" / DEFAULT_CONTRACT_NAME,
        Path.cwd() / "method_registry.json",
        here.parents[2] / "IGE_S0_S7_MethodRegistry_v0.1" / "method_registry.json",
    ]
    out: list[Path] = []
    for p in roots:
        if p is not None and p not in out:
            out.append(p)
    return out


def load_registry(
    path: Optional[PathLike] = None,
    *,
    validate: bool = True,
) -> "MethodRegistry":
    """Load a versioned registry JSON. Fail-closed on validation errors."""
    if path is None:
        for candidate in _default_contract_candidates():
            if candidate.is_file():
                path = candidate
                break
        if path is None:
            raise MethodRegistryError(
                "no registry path given and no default contract found "
                f"(looked for {DEFAULT_CONTRACT_NAME})"
            )
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — surface as fail-closed registry error
        raise MethodRegistryError(f"failed to load registry JSON from {p}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RegistryValidationError(["registry root must be an object"])
    return MethodRegistry(raw, source_path=p, validate=validate)


def resolve(
    method_id: str,
    path: Optional[PathLike] = None,
    *,
    registry: Optional["MethodRegistry"] = None,
) -> dict[str, Any]:
    """Convenience: load (if needed) and resolve one method_id fail-closed."""
    reg = registry if registry is not None else load_registry(path)
    return reg.resolve(method_id)


class MethodRegistry:
    """In-memory queryable Method Registry (fail-closed)."""

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        source_path: Optional[Path] = None,
        validate: bool = True,
    ):
        payload = deepcopy(dict(data))
        if validate:
            errors = validate_registry_data(payload)
            if errors:
                raise RegistryValidationError(errors)
        # Defence in depth: never allow True edit_permission to survive load,
        # even if caller passed validate=False (still refuse auto-grant).
        for method in payload.get("methods", []):
            if isinstance(method, dict) and method.get("edit_permission") is True:
                raise RegistryValidationError(
                    [
                        f"edit_permission=True refused for method_id="
                        f"{method.get('method_id')!r}; AI/loader cannot auto-grant write"
                    ]
                )
        self._data = payload
        self.source_path = Path(source_path) if source_path else None
        self._by_id: dict[str, dict[str, Any]] = {}
        for method in self._data["methods"]:
            mid = method["method_id"]
            self._by_id[mid] = method

    # --- metadata ---

    @property
    def registry_id(self) -> str:
        return str(self._data.get("registry_id", ""))

    @property
    def registry_version(self) -> str:
        return str(self._data.get("registry_version", ""))

    @property
    def registry_schema(self) -> str:
        return str(self._data.get("registry_schema", ""))

    @property
    def policy(self) -> str:
        return str(self._data.get("policy", ""))

    @property
    def default_edit_permission(self) -> bool:
        # Contract: always false; never invent True.
        return False

    @property
    def method_count(self) -> int:
        return len(self._data["methods"])

    def raw(self) -> dict[str, Any]:
        """Deep copy of the registry document (mutations do not affect the loader)."""
        return deepcopy(self._data)

    def method_ids(self) -> list[str]:
        return list(self._by_id.keys())

    def all_methods(self) -> list[dict[str, Any]]:
        return [deepcopy(m) for m in self._data["methods"]]

    # --- queries ---

    def get(self, method_id: str) -> Optional[dict[str, Any]]:
        """Return a deep copy of the method record, or None if missing."""
        method = self._by_id.get(method_id)
        return deepcopy(method) if method is not None else None

    def resolve(self, method_id: str) -> dict[str, Any]:
        """Fail-closed resolve by method_id.

        Returns a deep copy of the method record.
        Raises MethodNotFoundError if unknown.
        Guarantees returned edit_permission is False (never auto-granted).
        """
        method = self._by_id.get(method_id)
        if method is None:
            raise MethodNotFoundError(method_id)
        out = deepcopy(method)
        # Hard invariant: loader never returns or invents write permission.
        if out.get("edit_permission") is not False:
            raise RegistryValidationError(
                [
                    f"resolve({method_id!r}) refused: edit_permission must remain false "
                    "(DIFF/evidence ≠ edit_permission; S3 human compile required)"
                ]
            )
        out["edit_permission"] = False
        return out

    def query(
        self,
        *,
        method_id: Optional[str] = None,
        stage: Optional[str] = None,
        capability: Optional[str] = None,
        backend_id: Optional[str] = None,
        implementation_status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Filter methods by any combination of fields. All filters AND together.

        stage: matches if the method's stage list contains the value.
        Other string fields: exact match.
        Returns deep copies; empty list if nothing matches (query is soft;
        use resolve() when absence must fail closed).
        """
        results: list[dict[str, Any]] = []
        for method in self._data["methods"]:
            if method_id is not None and method.get("method_id") != method_id:
                continue
            if stage is not None:
                stages = method.get("stage") or []
                if stage not in stages:
                    continue
            if capability is not None and method.get("capability") != capability:
                continue
            if backend_id is not None and method.get("backend_id") != backend_id:
                continue
            if (
                implementation_status is not None
                and method.get("implementation_status") != implementation_status
            ):
                continue
            results.append(deepcopy(method))
        return results

    def by_stage(self, stage: str) -> list[dict[str, Any]]:
        return self.query(stage=stage)

    def by_capability(self, capability: str) -> list[dict[str, Any]]:
        return self.query(capability=capability)

    def by_backend_id(self, backend_id: str) -> list[dict[str, Any]]:
        return self.query(backend_id=backend_id)

    def by_implementation_status(self, status: str) -> list[dict[str, Any]]:
        return self.query(implementation_status=status)

    def assert_no_edit_permission_granted(self) -> None:
        """Raise if any method has edit_permission != False."""
        bad = [
            m["method_id"]
            for m in self._data["methods"]
            if m.get("edit_permission") is not False
        ]
        if bad:
            raise RegistryValidationError(
                [f"edit_permission must be false for: {bad}"]
            )

    def summary(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "registry_schema": self.registry_schema,
            "policy": self.policy,
            "default_edit_permission": self.default_edit_permission,
            "method_count": self.method_count,
            "method_ids": self.method_ids(),
            "all_edit_permission_false": all(
                m.get("edit_permission") is False for m in self._data["methods"]
            ),
            "source_path": str(self.source_path) if self.source_path else None,
            "production_wired": False,
        }


# Back-compat alias used by the original package validator pattern.
def validate(data: Mapping[str, Any]) -> list[str]:
    """Alias for validate_registry_data (matches validate_registry.py API)."""
    return validate_registry_data(data)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: validate + print summary for a registry JSON path."""
    import sys

    args = list(argv) if argv is not None else sys.argv[1:]
    path = Path(args[0]) if args else None
    try:
        reg = load_registry(path)
    except RegistryValidationError as exc:
        print(
            json.dumps(
                {"status": "FAIL", "errors": exc.errors, "production_wired": False},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    except MethodRegistryError as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error": str(exc), "production_wired": False},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    out = {"status": "PASS", **reg.summary()}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
