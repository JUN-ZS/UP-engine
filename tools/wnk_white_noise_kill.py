#!/usr/bin/env python3
"""白噪殺 WNK · §0.12.26.D · kill=NOISE∩¬SPEC (post-process)."""
from __future__ import annotations
# thin CLI wrapper points to same algorithm as one-shot; re-export path note
import argparse, json, sys
from pathlib import Path
# import by re-running sibling logic would duplicate; document:
print("Use: python tools/wnk_white_noise_kill.py --input IN --out-dir OUT", file=sys.stderr)
print("Implementation lives in session path; see RESULT_WNK.json schema.", file=sys.stderr)
