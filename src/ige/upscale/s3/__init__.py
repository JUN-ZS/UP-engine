"""S3 Heterogeneous Upscale Execution (architecture v0).

Not E3 speed. Not quality PASS. Builds on S2.1 integrity/VM patterns.
"""

from .capability import WorkerCapability, score_worker_for_child
from .scheduler import CapabilityScheduler, ChildTask
from .transport_fs import FsLeaseTransport
from .adapter_base import UpscaleAdapter, ChildRunSpec, ChildRunResult
from .adapter_siax import SiaxAdapter

__all__ = [
    "WorkerCapability",
    "score_worker_for_child",
    "CapabilityScheduler",
    "ChildTask",
    "FsLeaseTransport",
    "UpscaleAdapter",
    "ChildRunSpec",
    "ChildRunResult",
    "SiaxAdapter",
]
