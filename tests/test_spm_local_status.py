from __future__ import annotations

from ige.spm_local import local_pc_status


def test_local_pc_status_shape():
    s = local_pc_status()
    assert s["format"] == "ige.spm.local_pc_status"
    assert s["cpu_threads"] >= 1
    assert s["backend"]["comfyui_required"] is False
    assert s["backend"]["s3_scheduler_required"] is False
    assert s["final_acceptance"] is False
