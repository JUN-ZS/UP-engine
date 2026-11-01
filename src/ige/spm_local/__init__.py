"""SPM local Siax backend — thin executor for Grok Canvas / HERE handoff / MCP."""

from .executor import (
    local_pc_status,
    spm_local_execute,
    spm_local_result,
    JobStore,
)
from .handoff import new_request, write_request, list_pending, process_one

__all__ = [
    "local_pc_status",
    "spm_local_execute",
    "spm_local_result",
    "JobStore",
    "new_request",
    "write_request",
    "list_pending",
    "process_one",
]
