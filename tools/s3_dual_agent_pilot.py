#!/usr/bin/env python3
"""S3.6 dual-agent pilot entry.

Prefer tools/s3_controller.py + tools/s3_worker_agent.py on real hosts.
This wrapper documents the pilot; automated evidence lives in docs/evidence/S3_6_*.
"""
from __future__ import annotations
import argparse
print(__doc__)
print("See docs/S3_DUAL_HOST_PILOT.md and docs/S3_6_RESULTS.md")
print("Physical dual-host: run controller on host A, agents on A/B against shared job-dir.")
raise SystemExit(0)
