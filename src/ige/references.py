from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


class ReferenceCatalogError(ValueError):
    """Reference metadata is missing, ambiguous, or inconsistent."""


@dataclass(frozen=True)
class ReferenceEntry:
    asset_id: str
    label: str
    role: str
    skills: tuple[str, ...]
    tags: tuple[str, ...]
    description: str
    uri: str
    availability: str
    source_repo: str
    source_commit: str
    source_path: str
    source_section: str
    expected_sha256: str | None = None
    local_path: str | None = None
    license_status: str = "not_applicable"
    source_contexts: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ReferenceEntry":
        required = ("asset_id", "label", "role", "skills", "description", "uri", "availability", "source_repo", "source_commit", "source_path", "source_section")
        missing = [key for key in required if key not in raw]
        if missing:
            raise ReferenceCatalogError(f"reference entry missing: {', '.join(missing)}")
        for key in required:
            if isinstance(raw[key], str) and not raw[key].strip():
                raise ReferenceCatalogError(f"reference {key} must be non-empty")
        if not isinstance(raw["skills"], list) or any(not isinstance(x, str) for x in raw["skills"]):
            raise ReferenceCatalogError("reference skills must be an array of strings")
        tags = raw.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(x, str) for x in tags):
            raise ReferenceCatalogError("reference tags must be an array of strings")
        digest = raw.get("expected_sha256")
        if digest is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest)):
            raise ReferenceCatalogError("expected_sha256 must be 64 hexadecimal characters")
        return cls(str(raw["asset_id"]), str(raw["label"]), str(raw["role"]), tuple(raw["skills"]), tuple(tags), str(raw["description"]), str(raw["uri"]), str(raw["availability"]), str(raw["source_repo"]), str(raw["source_commit"]), str(raw["source_path"]), str(raw["source_section"]), str(digest).lower() if digest else None, str(raw["local_path"]) if raw.get("local_path") else None, str(raw.get("license_status", "not_applicable")), tuple(str(x) for x in raw.get("source_contexts", [])), tuple(str(x) for x in raw.get("aliases", [])))

    def to_dict(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id, "label": self.label, "role": self.role, "skills": list(self.skills), "tags": list(self.tags), "description": self.description, "uri": self.uri, "availability": self.availability, "source_repo": self.source_repo, "source_commit": self.source_commit, "source_path": self.source_path, "source_section": self.source_section, "expected_sha256": self.expected_sha256, "local_path": self.local_path, "license_status": self.license_status, "source_contexts": list(self.source_contexts), "aliases": list(self.aliases)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReferenceCatalog:
    """Offline snapshot of reviewed legacy references; never fetches legacy assets implicitly."""

    def __init__(self, entries: tuple[ReferenceEntry, ...], catalog_path: Path):
        self.entries = entries
        self.catalog_path = catalog_path
        seen: set[str] = set()
        for entry in entries:
            key = entry.asset_id.lower()
            if key in seen:
                raise ReferenceCatalogError(f"duplicate asset_id in catalog: {entry.asset_id}")
            seen.add(key)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ReferenceCatalog":
        catalog_path = Path(path).resolve() if path is not None else (Path(__file__).parent / "data" / "legacy_reference_catalog.json").resolve()
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("catalog_version") != "1.0":
            raise ReferenceCatalogError("unsupported or malformed reference catalog")
        rows = raw.get("references")
        if not isinstance(rows, list):
            raise ReferenceCatalogError("catalog references must be an array")
        return cls(tuple(ReferenceEntry.from_dict(row) for row in rows), catalog_path)

    def search(self, query: str = "", *, role: str | None = None, skill: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9_+#.-]+", query) if token}
        scored: list[tuple[int, ReferenceEntry]] = []
        for entry in self.entries:
            if role and entry.role.lower() != role.lower():
                continue
            if skill and skill.upper() not in {item.upper() for item in entry.skills}:
                continue
            haystack = " ".join([entry.asset_id, entry.label, entry.role, entry.description, *entry.skills, *entry.tags, entry.source_section, *entry.source_contexts, *entry.aliases]).lower()
            score = sum(2 if token == entry.asset_id.lower() else 1 for token in tokens if token in haystack)
            if not tokens:
                score = 1
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda item: (-item[0], item[1].label.lower(), item[1].asset_id))
        return [self.inspect(entry.asset_id) | {"match_score": score} for score, entry in scored[:limit]]

    def inspect(self, asset_id: str, *, asset_root: str | Path | None = None) -> dict[str, Any]:
        key = asset_id.lower()
        matches = [entry for entry in self.entries if entry.asset_id.lower() == key]
        resolved_from_alias = False
        if not matches:
            matches = [entry for entry in self.entries if key in {alias.lower() for alias in entry.aliases}]
            resolved_from_alias = bool(matches)
        if not matches:
            raise KeyError(f"reference not found: {asset_id}")
        if len(matches) != 1:
            raise ReferenceCatalogError(f"reference is ambiguous: {asset_id}; use the full asset ID")
        entry = matches[0]
        result = entry.to_dict()
        if resolved_from_alias:
            result["resolved_from_alias"] = asset_id
        result["materialization"] = "reference_only"
        result["local_file"] = None
        if asset_root is not None:
            root = Path(asset_root).resolve()
            if not root.is_dir():
                raise FileNotFoundError(f"asset root does not exist: {root}")
            candidates: list[Path] = []
            if entry.local_path:
                candidate = (root / entry.local_path).resolve()
                if root not in candidate.parents and candidate != root:
                    raise ReferenceCatalogError("catalog local_path escapes asset root")
                candidates.append(candidate)
            else:
                candidates.extend(sorted(root.glob(f"**/{entry.asset_id}.*")))
            existing = [candidate for candidate in candidates if candidate.is_file()]
            if len(existing) > 1:
                raise ReferenceCatalogError(f"multiple local files match {entry.asset_id}; provide a unique local_path")
            if existing:
                path = existing[0]
                digest = _sha256(path)
                if entry.expected_sha256 and digest != entry.expected_sha256:
                    raise ReferenceCatalogError(f"SHA-256 mismatch for {entry.asset_id}: expected {entry.expected_sha256}, got {digest}")
                result["materialization"] = "local_verified" if entry.expected_sha256 else "local_unverified"
                result["local_file"] = str(path)
                result["actual_sha256"] = digest
        return result

    def resolve(self, asset_id: str, *, role: str | None = None, skill: str | None = None, asset_root: str | Path | None = None) -> dict[str, Any]:
        result = self.inspect(asset_id, asset_root=asset_root)
        if role and result["role"].lower() != role.lower():
            raise ReferenceCatalogError(f"{asset_id} has role {result['role']!r}, not requested {role!r}")
        if skill and skill.upper() not in {item.upper() for item in result["skills"]}:
            raise ReferenceCatalogError(f"{asset_id} is not indexed for skill {skill}")
        return result
