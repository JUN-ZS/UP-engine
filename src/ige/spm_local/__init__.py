"""SPM local Siax backend — thin executor for Grok Canvas / MCP.

Does not rewrite SPM, ComfyUI, or S3 scheduler.
Cloud Imagine stays cloud; only native Siax inference can run here.
"""

from .executor import (
    local_pc_status,
    spm_local_execute,
    spm_local_result,
    JobStore,
)

__all__ = [
    "local_pc_status",
    "spm_local_execute",
    "spm_local_result",
    "JobStore",
]
