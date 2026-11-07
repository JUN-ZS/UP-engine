"""Static ComfyUI workflow / API-prompt inventory audits (no GPU)."""

from .global_noise_contract import (
    FAILURE_NOISE,
    FIELD_KIND_COORDINATE_INDEXED,
    FIELD_KIND_SHARED_SEED_ONLY,
    TEST_ID_NOISE,
    classify_noise_evidence,
)
from .model_inventory import (
    FAILURE_BACKEND_INVENTORY,
    backend_model_inventory_verified,
    load_model_inventory,
    verify_against_workflow_audit,
)
from .tile_core_halo_ledger import (
    CODE_CORE_NOT_SUBSET,
    CODE_CORE_OVERLAP,
    CODE_COVERAGE_GAP,
    CODE_HALO_WRITE,
    CODE_SCHEMA,
    LEDGER_SCHEMA,
    UMBRELLA_FAILURE,
    audit_ledger,
    load_ledger,
    ledger_passes,
)
from .workflow_static_audit import (
    EXPECTED_DEV_FP8_MODELS,
    REQUIRED_FLUX_HR_TILE_CLASSES,
    audit_comfy_workflows,
    load_workflow_json,
)

__all__ = [
    "CODE_CORE_NOT_SUBSET",
    "CODE_CORE_OVERLAP",
    "CODE_COVERAGE_GAP",
    "CODE_HALO_WRITE",
    "CODE_SCHEMA",
    "EXPECTED_DEV_FP8_MODELS",
    "FAILURE_BACKEND_INVENTORY",
    "FAILURE_NOISE",
    "FIELD_KIND_COORDINATE_INDEXED",
    "FIELD_KIND_SHARED_SEED_ONLY",
    "LEDGER_SCHEMA",
    "REQUIRED_FLUX_HR_TILE_CLASSES",
    "TEST_ID_NOISE",
    "UMBRELLA_FAILURE",
    "audit_comfy_workflows",
    "audit_ledger",
    "backend_model_inventory_verified",
    "classify_noise_evidence",
    "ledger_passes",
    "load_ledger",
    "load_model_inventory",
    "load_workflow_json",
    "verify_against_workflow_audit",
]
