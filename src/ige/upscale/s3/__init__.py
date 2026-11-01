"""S3 Heterogeneous Upscale Execution.

Not E3 speed. Not quality PASS. Builds on S2.1 integrity/VM patterns.
"""

from .capability import WorkerCapability, score_worker_for_child
from .scheduler import CapabilityScheduler, ChildTask
from .transport_fs import FsLeaseTransport
from .adapter_base import UpscaleAdapter, ChildRunSpec, ChildRunResult
from .adapter_siax import SiaxAdapter
from .adapter_synthetic import SyntheticNearestAdapter
from .job_plan import plan_compute_children
from .rebuild import rebuild_from_receipts, pixel_match_children
from .worker_loop import run_worker_loop

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
    "SyntheticNearestAdapter",
    "plan_compute_children",
    "rebuild_from_receipts",
    "pixel_match_children",
    "run_worker_loop",
]
