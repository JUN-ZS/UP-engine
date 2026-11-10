#!/usr/bin/env python3
"""SHQ Agent Driver v0.1 (write 01392)

Closes the PR#12 gap:
  Registry.resolve(method_id) → load entrypoint → check permission
  → execute callable → stage receipt → independent S7

Other AIs should call this driver, not invent shortcuts.

CLI:
  selftest
  validate-registry [--registry PATH]
  resolve --method-id ID
  run-full --src SRC --empty EMPTY --out RUN_DIR [--imagine-densify ASSET_MAP_JSON]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

WRITE_ID = "01392"
FORMAL = "SHQ_AGENT_DRIVER_V0_1"
SKILL_DIR = Path(__file__).resolve().parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha_arr(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def load_validator():
    p = SKILL_DIR / "validate_registry.py"
    if not p.exists():
        # fallback next to registry
        p = SKILL_DIR / "registry" / "validate_registry.py"
    spec = importlib.util.spec_from_file_location("validate_registry", str(p))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def load_registry(registry_path: Optional[Path] = None) -> Dict[str, Any]:
    path = registry_path or (SKILL_DIR / "method_registry.json")
    if not path.exists():
        raise FileNotFoundError(f"E_REGISTRY_FILE_MISSING: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    val = load_validator()
    errors = val.validate(data)
    if errors:
        raise RuntimeError("E_REGISTRY_INVALID: " + "; ".join(errors[:12]))
    return data


def index_methods(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {m["method_id"]: m for m in data["methods"]}


# --------------- entrypoint registry (callable map) ---------------

def _import_four_anti():
    p = SKILL_DIR / "shq_edit_hole_four_anti_debug.py"
    name = "shq_edit_hole_four_anti_debug"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(p))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class StageReceipt:
    stage: str
    method_id: str
    status: str  # PASS | FAIL | BLOCK | SKIP | WARN
    claim_level: str
    edit_permission: bool
    inputs_sha: Dict[str, str] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    allowed_claims: List[str] = field(default_factory=list)
    forbidden_non_claims: List[str] = field(default_factory=list)
    blocked_methods: List[str] = field(default_factory=list)
    error: str = ""
    asof: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentDriver:
    """Central state machine: AI proposes state; driver selects & executes."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.reg_data = load_registry(registry_path)
        self.methods = index_methods(self.reg_data)
        self.four = _import_four_anti()
        self.receipts: List[StageReceipt] = []
        self.state: Dict[str, Any] = {
            "identity_drift": "unknown",
            "topology_error": False,
            "outer_shape_broken": "absent",
            "human_permission": False,
            "backend_siax": False,
            "backend_flux": False,
            "external_donor": False,
            "material_blurry": "present",  # default route toward material densify
            "shape_clear_pixels_low": "absent",
        }

    def resolve(self, method_id: str) -> Dict[str, Any]:
        if method_id not in self.methods:
            raise KeyError(f"E_UNREGISTERED_METHOD_ID: {method_id}")
        m = self.methods[method_id]
        if m.get("edit_permission") is not False:
            raise RuntimeError(f"E_EDIT_PERMISSION_MUST_FALSE: {method_id}")
        return m

    def route_by_state(self) -> str:
        """Minimal fail-closed router aligned with PR12 intent (not full fossil)."""
        st = self.state
        if st.get("topology_error") or st.get("outer_shape_broken") == "present":
            return "OTL0_TOPOLOGY_REPAIR"
        if st.get("identity_drift") == "present" and not st.get("identity_ref"):
            return "PATH1E_IDENTITY_ECC_LOCK"
        if st.get("backend_flux") and st.get("geometry_locked"):
            return "FLUX_HR_TILE_IMG2IMG"
        if st.get("external_donor"):
            return "ALL24_AI_DONOR_MULTIBAND_TRANSFER"
        if st.get("material_blurry") == "present":
            return "HOLE_SCALELOCK_HF_RESIDUAL"
        if st.get("backend_siax"):
            return "SIAX4X_TILE_CORE_SR"
        return "HOLE_SCALELOCK_HF_RESIDUAL"

    def empty_is_freeframe(self, src: np.ndarray, empty: np.ndarray) -> bool:
        """True empty must share pose/layout with SRC. Freeframe hangar fails NCC."""
        if src.shape[:2] != empty.shape[:2]:
            return True
        gs = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32)
        ge = cv2.cvtColor(empty, cv2.COLOR_BGR2GRAY).astype(np.float32)
        ncc = float(np.corrcoef(gs.ravel(), ge.ravel())[0, 1])
        self.state["empty_ncc"] = ncc
        return ncc < 0.85

    def subject_mask_grabcut(self, bgr: np.ndarray, side: str) -> tuple:
        """Tight subject prior: GrabCut + definite BG on floor/edges + color assist."""
        H, W = bgr.shape[:2]
        mask = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
        if side == "L":
            # silver mecha typically left-center
            rect = (int(W * 0.08), int(H * 0.05), int(W * 0.32), int(H * 0.78))
            x0, x1 = 0, W // 2
        else:
            rect = (int(W * 0.52), int(H * 0.12), int(W * 0.40), int(H * 0.78))
            x0, x1 = W // 2, W
        # definite background: borders + floor band + other half
        mask[:, :] = cv2.GC_BGD
        mask[rect[1]:rect[1]+rect[3], rect[0]:rect[0]+rect[2]] = cv2.GC_PR_FGD
        # small sure FG seed in rect center
        cx, cy = rect[0] + rect[2] // 2, rect[1] + rect[3] // 2
        cv2.circle(mask, (cx, cy), max(20, min(rect[2], rect[3]) // 8), int(cv2.GC_FGD), -1)
        # floor always BG
        mask[int(H * 0.82):, :] = cv2.GC_BGD
        # opposite half BG
        if side == "L":
            mask[:, W // 2 :] = cv2.GC_BGD
        else:
            mask[:, : W // 2] = cv2.GC_BGD
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(bgr, mask, None, bgd, fgd, 8, cv2.GC_INIT_WITH_MASK)
            m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        except Exception:
            m = np.zeros((H, W), np.uint8)
            x, y, w, h = rect
            m[y:y+h, x:x+w] = 255
        # color assist: silver high L / red high a*
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        L, A, B = cv2.split(lab)
        if side == "L":
            col = ((L > 90) & (np.abs(A.astype(np.int16) - 128) < 25)).astype(np.uint8) * 255
        else:
            col = ((A > 145) & (L > 40)).astype(np.uint8) * 255
        col[:, :x0] = 0
        col[:, x1:] = 0
        col[int(H * 0.85):, :] = 0
        m = cv2.bitwise_or(m, cv2.bitwise_and(col, col))
        m[int(H * 0.88):, :] = 0
        if side == "L":
            m[:, W // 2 :] = 0
        else:
            m[:, : W // 2] = 0
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        n, labc, st, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
        if n > 1:
            # pick largest CC that intersects sure seed
            best, best_a = 0, 0
            for i in range(1, n):
                a = int(st[i, cv2.CC_STAT_AREA])
                if a > best_a:
                    best, best_a = i, a
            m = (labc == best).astype(np.uint8) * 255
        # erode slightly to avoid floor halo
        m = cv2.erode(m, np.ones((3, 3), np.uint8), iterations=1)
        area = int((m > 0).sum())
        x, y, w, h = cv2.boundingRect(m) if area else (0, 0, 0, 0)
        return m, area, [int(x), int(y), int(w), int(h)]

    def elev_same_pose(self, peep: np.ndarray, dens: np.ndarray, alpha: np.ndarray, hf: float = 1.25) -> np.ndarray:
        """Geometry-locked elev: NO phaseCorrelate warp. peep owns pose/scale."""
        th, tw = peep.shape[:2]
        if dens.shape[:2] != (th, tw):
            dens = cv2.resize(dens, (tw, th), interpolation=cv2.INTER_LANCZOS4)
        pf = peep.astype(np.float32)
        mf = dens.astype(np.float32)
        # peep-dominant: protect pose; HF residual only
        out = cv2.GaussianBlur(pf, (0, 0), 0.8) + (mf - cv2.GaussianBlur(mf, (0, 0), 0.8)) * hf
        out = np.clip(out * 0.15 + mf * 0.10 + pf * 0.75, 0, 255).astype(np.uint8)
        if alpha is not None:
            if alpha.shape[:2] != (th, tw):
                alpha = cv2.resize(alpha, (tw, th), interpolation=cv2.INTER_NEAREST)
            a = alpha > 0
            mix = peep.copy()
            mix[a] = out[a]
            return mix
        return out

    def _receipt(self, **kw) -> StageReceipt:
        r = StageReceipt(**kw)
        self.receipts.append(r)
        return r

    # ----- stage callables -----

    def s0_freeze(self, src: Path, empty: Optional[Path], out: Path) -> StageReceipt:
        out.mkdir(parents=True, exist_ok=True)
        im = cv2.imread(str(src), cv2.IMREAD_COLOR)
        if im is None:
            return self._receipt(stage="S0", method_id="S0_BASE_FREEZE", status="FAIL",
                                 claim_level="C0", edit_permission=False, error="src unreadable")
        H, W = im.shape[:2]
        file_sha = sha_file(src)
        pix = sha_arr(im)
        cv2.imwrite(str(out / "I0.png"), im)
        empty_meta = None
        if empty and empty.exists():
            em = cv2.imread(str(empty), cv2.IMREAD_COLOR)
            if em is None:
                return self._receipt(stage="S0", method_id="S0_BASE_FREEZE", status="FAIL",
                                     claim_level="C0", edit_permission=False, error="empty unreadable")
            if em.shape[:2] != (H, W):
                return self._receipt(stage="S0", method_id="S0_BASE_FREEZE", status="BLOCK",
                                     claim_level="C0", edit_permission=False,
                                     error="empty size mismatch — no silent resize")
            cv2.imwrite(str(out / "EMPTY.png"), em)
            empty_meta = {"file_sha": sha_file(empty), "pix_sha": sha_arr(em)}
        meta = {
            "wh": [W, H],
            "file_sha": file_sha,
            "pix_sha": pix,
            "reread_ok": sha_arr(cv2.imread(str(out / "I0.png"))) == pix,
            "empty": empty_meta,
        }
        (out / "S0_BASE_FREEZE.json").write_text(json.dumps(meta, indent=2) + "\n")
        self.state["src"] = str(out / "I0.png")
        self.state["empty"] = str(out / "EMPTY.png") if empty_meta else None
        self.state["wh"] = [W, H]
        return self._receipt(
            stage="S0", method_id="S0_BASE_FREEZE", status="PASS" if meta["reread_ok"] else "FAIL",
            claim_level="C3", edit_permission=False,
            inputs_sha={"src_file": file_sha}, outputs=meta,
            allowed_claims=["s0_freeze_receipt"], forbidden_non_claims=["accept_full_hd"],
        )


    def s1_diff_read(self, out: Path) -> StageReceipt:
        src = cv2.imread(self.state["src"])
        empty_p = self.state.get("empty")
        H, W = src.shape[:2]
        mout = out / "s1"
        mout.mkdir(parents=True, exist_ok=True)
        method = "EMPTY_REVERSE_DIFF"
        freeframe = False
        heat = None
        m = None
        if empty_p:
            empty = cv2.imread(empty_p)
            freeframe = self.empty_is_freeframe(src, empty)
            m, heat = self.four.anti_diff(src, empty, thr=14)
            cv2.imwrite(str(mout / "HEAT.jpg"), heat)
            if freeframe:
                method = "SRC_GRABCUT_DUAL_PRIOR (empty freeframe NCC low)"
        else:
            freeframe = True
            method = "SRC_GRABCUT_DUAL_PRIOR (no empty)"

        parts = []
        if freeframe:
            for name, side in (("U0_LEFT", "L"), ("U1_RIGHT", "R")):
                mask, area, box = self.subject_mask_grabcut(src, side)
                if area >= 2500:
                    parts.append({"name": name, "area": area, "xywh": box, "mask": mask})
        else:
            mid = W // 2
            mL, mR = m.copy(), m.copy()
            mL[:, mid:] = 0
            mR[:, :mid] = 0

            def largest(mm):
                n, lab, st, _ = cv2.connectedComponentsWithStats((mm > 0).astype(np.uint8), 8)
                if n <= 1:
                    return np.zeros_like(mm), 0, [0, 0, 0, 0]
                i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
                mask = (lab == i).astype(np.uint8) * 255
                x, y, w, h, area = st[i]
                return mask, int(area), [int(x), int(y), int(w), int(h)]

            for name, mm in (("U0_LEFT", mL), ("U1_RIGHT", mR)):
                mask, area, box = largest(mm)
                if area >= 2500:
                    parts.append({"name": name, "area": area, "xywh": box, "mask": mask})

        if not parts:
            # last resort: center rects
            for name, side in (("U0_LEFT", "L"), ("U1_RIGHT", "R")):
                mask, area, box = self.subject_mask_grabcut(src, side)
                parts.append({"name": name, "area": area, "xywh": box, "mask": mask})

        union = np.zeros((H, W), np.uint8)
        meta_parts = []
        for p in parts:
            cv2.imwrite(str(mout / f"{p['name']}_cand.png"), p["mask"])
            union = cv2.bitwise_or(union, p["mask"])
            meta_parts.append({k: v for k, v in p.items() if k != "mask"})
            p["mask_path"] = str(mout / f"{p['name']}_cand.png")
        cv2.imwrite(str(mout / "M_UNION.png"), union)
        cov = float((union > 0).mean())
        self.state["parts"] = parts
        self.state["union_mask"] = str(mout / "M_UNION.png")
        self.state["empty_freeframe"] = freeframe
        self.state["mask_coverage"] = cov
        status = "PASS"
        if cov > 0.36:
            status = "WARN"  # still bloated
        return self._receipt(
            stage="S1", method_id="S1_OBJECT_READ_DIFF_CANDIDATE", status=status,
            claim_level="C1", edit_permission=False,
            outputs={
                "n_parts": len(parts), "parts": meta_parts, "method": method,
                "empty_freeframe": freeframe, "empty_ncc": self.state.get("empty_ncc"),
                "mask_coverage": cov,
            },
            allowed_claims=["diff_candidate_mask"],
            forbidden_non_claims=["human_verified_identity", "edit_permission"],
        )

    def s2_geometry_lock(self, out: Path) -> StageReceipt:
        src = cv2.imread(self.state["src"])
        H, W = src.shape[:2]
        peep_dir = out / "peep"
        peep_dir.mkdir(parents=True, exist_ok=True)
        locked = []
        for p in self.state.get("parts", []):
            x, y, w, h = p["xywh"]
            pad = 8
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
            peep = src[y0:y1, x0:x1].copy()
            am = p["mask"][y0:y1, x0:x1]
            peep_locked = peep.copy()
            peep_locked[am == 0] = 0
            rgba = cv2.cvtColor(peep, cv2.COLOR_BGR2BGRA)
            rgba[:, :, 3] = am
            cv2.imwrite(str(peep_dir / f"{p['name']}_peep_LOCKED.png"), peep_locked)
            cv2.imwrite(str(peep_dir / f"{p['name']}_geo_RGBA.png"), rgba)
            corners = {
                "TL": [x0, y0], "TR": [x1 - 1, y0], "BR": [x1 - 1, y1 - 1], "BL": [x0, y1 - 1],
                "B_xywh": [x0, y0, x1 - x0, y1 - y0],
            }
            p.update(peep=peep_locked, am=am, bbox=(x0, y0, x1, y1), corners_4=corners)
            locked.append({"name": p["name"], "corners_4": corners, "alpha_area": int((am > 0).sum())})
        self.state["geometry_locked"] = True
        return self._receipt(
            stage="S2", method_id="S2_GEOMETRY_LOCK_PEEP", status="PASS",
            claim_level="C2", edit_permission=False,
            outputs={"parts": locked, "elev_remap": False},
            allowed_claims=["geometry_lock_partial"],
            forbidden_non_claims=["5d_calibrated_3d"],
        )

    def s3_permission(self, out: Path) -> StageReceipt:
        # never self-grant
        perm = {
            "edit_permission_production": False,
            "diagnostic_write_in_hole": True,
            "human_permission": bool(self.state.get("human_permission")),
        }
        (out / "s3").mkdir(parents=True, exist_ok=True)
        (out / "s3" / "S3_PERMISSION.json").write_text(json.dumps(perm, indent=2) + "\n")
        return self._receipt(
            stage="S3", method_id="PATH1E_IDENTITY_ECC_LOCK", status="PASS",
            claim_level="C1", edit_permission=False, outputs=perm,
            allowed_claims=["identity_gate"],
            forbidden_non_claims=["identity_verified_without_ref"],
            blocked_methods=["DETAIL6_MATERIAL_RESIDUAL"] if self.state.get("identity_drift") == "unknown" else [],
        )

    def s4_route(self, out: Path) -> StageReceipt:
        mid = self.route_by_state()
        m = self.resolve(mid)
        decision = {
            "method_id": mid,
            "implementation_status": m["implementation_status"],
            "entrypoint": m["entrypoint"],
            "allowed_claims": m.get("allowed_claims", []),
            "forbidden_non_claims": m.get("forbidden_non_claims", []),
            "state": {k: self.state[k] for k in (
                "identity_drift", "topology_error", "material_blurry", "backend_siax", "backend_flux"
            ) if k in self.state},
        }
        (out / "s4").mkdir(parents=True, exist_ok=True)
        (out / "s4" / "S4_ROUTE.json").write_text(json.dumps(decision, indent=2) + "\n")
        self.state["routed_method_id"] = mid
        return self._receipt(
            stage="S4", method_id=mid, status="PASS",
            claim_level="C1", edit_permission=False, outputs=decision,
            allowed_claims=list(m.get("allowed_claims", [])),
            forbidden_non_claims=list(m.get("forbidden_non_claims", [])),
        )

    def s5_execute_routed(self, out: Path, densify_map: Optional[Dict[str, Path]] = None) -> StageReceipt:
        mid = self.state.get("routed_method_id", "HOLE_SCALELOCK_HF_RESIDUAL")
        self.resolve(mid)
        ref = out / "ref"
        ref.mkdir(parents=True, exist_ok=True)
        units = []
        for p in self.state.get("parts", []):
            peep, am = p["peep"], p["am"]
            dens_path = densify_map.get(p["name"]) if densify_map else None
            if dens_path and Path(dens_path).exists():
                dens = cv2.imread(str(dens_path))
                backend = "external_imagine_or_donor_file"
                claim = "C3"
                adapter = True
            else:
                dens = cv2.detailEnhance(peep, sigma_s=12, sigma_r=0.2)
                dens = cv2.edgePreservingFilter(dens, flags=1, sigma_s=40, sigma_r=0.3)
                backend = "opencv_detailEnhance_HF"
                claim = "C1"
                adapter = False
            sz = self.four.check_size_grow(peep, dens)
            # NO phaseCorrelate warp — peep owns pose (return bug fix 01392b)
            elev = self.elev_same_pose(peep, dens, am, hf=0.55)
            cv2.imwrite(str(ref / f"{p['name']}_DENS.png"), dens)
            cv2.imwrite(str(ref / f"{p['name']}_ELEV.png"), elev)
            p["elev"] = elev
            units.append({
                "name": p["name"], "backend": backend, "adapter_log": adapter,
                "claim_level": claim if sz.get("size_ok") else "C1_SIZE_WARN",
                "size_ok": sz.get("size_ok"), "canvas_ratio": sz.get("canvas_ratio"),
            })
        claim_max = "C3" if all(u["claim_level"].startswith("C3") for u in units) else "C1"
        return self._receipt(
            stage="S5", method_id=mid, status="PASS",
            claim_level=claim_max, edit_permission=False,
            outputs={"units": units},
            allowed_claims=["hf_scalelock_control"] if claim_max == "C1" else ["path_c_or_imagine_densify"],
            forbidden_non_claims=["true_diffusion_8k", "accept_full_hd"],
        )


    def s6_return(self, out: Path) -> StageReceipt:
        """Hardpaste ONLY peep alpha at frozen corners_4. Never paste full bloated CC mask."""
        src = cv2.imread(self.state["src"])
        out_img = src.copy()
        H, W = src.shape[:2]
        leak_total = 0
        paste_logs = []
        peep_union = np.zeros((H, W), np.uint8)
        for p in self.state.get("parts", []):
            x0, y0, x1, y1 = p["bbox"]
            elev, am = p["elev"], p["am"]
            ch, cw = y1 - y0, x1 - x0
            if elev.shape[:2] != (ch, cw):
                elev = cv2.resize(elev, (cw, ch), interpolation=cv2.INTER_LINEAR)
            if am.shape[:2] != (ch, cw):
                am = cv2.resize(am, (cw, ch), interpolation=cv2.INTER_NEAREST)
            # full-frame peep hole only
            m_full = np.zeros((H, W), np.uint8)
            m_full[y0:y1, x0:x1] = am
            peep_union = cv2.bitwise_or(peep_union, m_full)
            hd = src.copy()
            reg = hd[y0:y1, x0:x1]
            m = am > 0
            reg[m] = elev[m]
            hd[y0:y1, x0:x1] = reg
            out_img, leak = self.four.hardpaste_hole(out_img, hd, m_full)
            leak_total += leak
            paste_logs.append({
                "name": p["name"], "leak": leak, "corners_4": p["corners_4"],
                "peep_alpha_area": int((am > 0).sum()),
            })
        outside = peep_union == 0
        max_out = int(np.abs(out_img[outside].astype(np.int16) - src[outside].astype(np.int16)).max()) if outside.any() else 0
        # alignment health vs SRC
        gs = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gr = cv2.cvtColor(out_img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        ncc = float(np.corrcoef(gs.ravel(), gr.ravel())[0, 1])
        (dx, dy), _ = cv2.phaseCorrelate(gs, gr)
        phase = float(np.hypot(dx, dy))
        s6 = out / "s6"
        s6.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(s6 / "RETURN_HARDPASTE.png"), out_img)
        cv2.imwrite(str(s6 / "BEFORE_AFTER.jpg"), np.hstack([
            cv2.resize(src, (640, 360)), cv2.resize(out_img, (640, 360))
        ]))
        # peep-union overlay debug
        dbg = src.copy()
        dbg[peep_union > 0] = (0.55 * src[peep_union > 0] + 0.45 * np.array([0, 255, 0])).astype(np.uint8)
        cv2.imwrite(str(s6 / "PEEP_HOLE_OVERLAY.jpg"), dbg)
        self.state["return_path"] = str(s6 / "RETURN_HARDPASTE.png")
        self.state["return_img"] = out_img
        self.state["peep_union"] = peep_union
        # FAIL closed if pose drifted
        ok = leak_total == 0 and max_out == 0 and ncc >= 0.90 and phase < 1.5
        status = "PASS" if ok else "FAIL"
        return self._receipt(
            stage="S6", method_id="SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD",
            status=status,
            claim_level=self.receipts[-1].claim_level if self.receipts else "C1",
            edit_permission=False,
            outputs={
                "leak_total": leak_total,
                "outside_max_absdiff": max_out,
                "elev_remap": False,
                "ncc_src_return": ncc,
                "phase_shift_px": phase,
                "paste_logs": paste_logs,
                "paste_mode": "peep_alpha_at_corners_4_only",
            },
            allowed_claims=["geometry_guard"],
            forbidden_non_claims=["soft_alpha_fix", "halo_double_write", "full_cc_mask_paste"],
            error="" if ok else f"return align fail ncc={ncc:.4f} phase={phase:.3f}",
        )

    def s7_accept(self, out: Path) -> StageReceipt:
        ret_p = Path(self.state.get("return_path", ""))
        checks = {
            "return_exists": ret_p.exists(),
            "reread_sha_match": False,
            "registry_validated": True,
            "n_receipts": len(self.receipts),
            "any_edit_permission_true": any(r.edit_permission for r in self.receipts),
            "adapter_diffusion": False,
            "claim_levels": [r.claim_level for r in self.receipts],
        }
        if ret_p.exists():
            im = cv2.imread(str(ret_p), cv2.IMREAD_COLOR)
            checks["reread_sha_match"] = im is not None and sha_arr(im) == sha_arr(self.state["return_img"])
        # find S6 outs
        s6r = next((r for r in self.receipts if r.stage == "S6"), None)
        if s6r:
            checks["outside_max_absdiff"] = s6r.outputs.get("outside_max_absdiff")
            checks["leak_total"] = s6r.outputs.get("leak_total")
        s6r = next((r for r in self.receipts if r.stage == "S6"), None)
        checks["ncc_src_return"] = (s6r.outputs.get("ncc_src_return") if s6r else None)
        checks["phase_shift_px"] = (s6r.outputs.get("phase_shift_px") if s6r else None)
        checks["empty_freeframe"] = self.state.get("empty_freeframe")
        checks["mask_coverage"] = self.state.get("mask_coverage")
        checks["paste_mode"] = (s6r.outputs.get("paste_mode") if s6r else None)
        ncc = checks.get("ncc_src_return") or 0.0
        phase = checks.get("phase_shift_px") or 99.0
        diag_ok = (
            checks["return_exists"] and checks["reread_sha_match"]
            and not checks["any_edit_permission_true"]
            and (checks.get("leak_total", 1) == 0)
            and (checks.get("outside_max_absdiff", 1) == 0)
            and ncc >= 0.90
            and phase < 1.5
            and (checks.get("mask_coverage") or 1) < 0.36
        )
        claim = max((r.claim_level for r in self.receipts if r.claim_level.startswith("C")), default="C0")
        # coerce claim rank
        order = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}
        best = "C0"
        for r in self.receipts:
            c = r.claim_level.split("_")[0]
            if order.get(c, 0) > order.get(best, 0):
                best = c
        report = {
            "write_id": WRITE_ID,
            "formal": FORMAL,
            "verdict": "PASS_DIAG_CHAIN" if diag_ok else "FAIL",
            "ACCEPT_FULL_HD": False,
            "production_claim": False,
            "claim_level": best,
            "checks": checks,
            "receipts": [r.to_dict() for r in self.receipts],
            "reason_no_full_hd": [
                "human identity not verified",
                "S7 quantitative ghost/flip suite not full",
                "PATH_B flux not live unless backend_flux=true with adapter",
            ],
            "asof": _now(),
        }
        s7 = out / "s7"
        s7.mkdir(parents=True, exist_ok=True)
        (s7 / "S7_AUDIT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        (out / "FULL_DRIVER_REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        return self._receipt(
            stage="S7", method_id="S7_INDEPENDENT_ACCEPT",
            status="PASS" if diag_ok else "FAIL",
            claim_level=best, edit_permission=False, outputs=report,
            allowed_claims=["s7_diag_chain"],
            forbidden_non_claims=["accept_full_hd_without_c5"],
        )

    def run_full(self, src: Path, empty: Path, out: Path,
                 densify_map: Optional[Dict[str, Path]] = None) -> Dict[str, Any]:
        out.mkdir(parents=True, exist_ok=True)
        self.receipts.clear()
        r0 = self.s0_freeze(src, empty, out / "s0")
        if r0.status not in ("PASS",):
            return {"status": "FAIL", "stage": "S0", "receipts": [r.to_dict() for r in self.receipts]}
        r1 = self.s1_diff_read(out)
        r2 = self.s2_geometry_lock(out)
        r3 = self.s3_permission(out)
        r4 = self.s4_route(out)
        r5 = self.s5_execute_routed(out, densify_map=densify_map)
        r6 = self.s6_return(out)
        r7 = self.s7_accept(out)
        # board
        self._board(out)
        return {
            "status": r7.status,
            "ACCEPT_FULL_HD": False,
            "claim_level": r7.claim_level,
            "routed_method_id": self.state.get("routed_method_id"),
            "n_parts": len(self.state.get("parts", [])),
            "receipts_n": len(self.receipts),
            "out": str(out),
        }

    def _board(self, out: Path) -> None:
        src = cv2.imread(self.state["src"])
        ret = self.state.get("return_img")
        if src is None or ret is None:
            return
        board = np.zeros((820, 1400, 3), np.uint8)
        board[:] = 16
        cv2.putText(board, "01392 SHQ Agent Driver — Registry→Dispatch→Receipt→S7",
                    (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2)
        board[50:320, 16:496] = cv2.resize(src, (480, 270))
        board[50:320, 510:990] = cv2.resize(ret, (480, 270))
        cv2.putText(board, "I0 NEW", (16, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 200), 1)
        cv2.putText(board, "S6 RETURN", (510, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 200), 1)
        y = 350
        for r in self.receipts:
            col = (0, 255, 120) if r.status == "PASS" else (0, 140, 255)
            cv2.putText(board, f"{r.stage} {r.method_id[:40]} [{r.claim_level}] {r.status}",
                        (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1)
            y += 24
        cv2.putText(board, "edit_permission always false | Skill D guard on return | ACCEPT_FULL_HD=false",
                    (16, 780), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 255), 1)
        bdir = out / "boards"
        bdir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(bdir / "00_DRIVER_BOARD.jpg"), board, [cv2.IMWRITE_JPEG_QUALITY, 90])
        cv2.imwrite(str(out / "00_DRIVER_BOARD.jpg"), board, [cv2.IMWRITE_JPEG_QUALITY, 90])


def cmd_selftest() -> int:
    data = load_registry()
    methods = index_methods(data)
    assert "HOLE_SCALELOCK_HF_RESIDUAL" in methods
    assert all(m["edit_permission"] is False for m in data["methods"])
    d = AgentDriver()
    mid = d.route_by_state()
    d.resolve(mid)
    print(json.dumps({
        "selftest": "PASS",
        "write_id": WRITE_ID,
        "formal": FORMAL,
        "n_methods": len(methods),
        "sample_route": mid,
    }, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=FORMAL)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    v = sub.add_parser("validate-registry")
    v.add_argument("--registry", type=Path, default=None)
    r = sub.add_parser("resolve")
    r.add_argument("--method-id", required=True)
    r.add_argument("--registry", type=Path, default=None)
    f = sub.add_parser("run-full")
    f.add_argument("--src", type=Path, required=True)
    f.add_argument("--empty", type=Path, required=True)
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--registry", type=Path, default=None)
    f.add_argument("--densify-map", type=Path, default=None,
                   help="JSON {part_name: image_path} optional Imagine densify")
    args = p.parse_args(argv)

    if args.cmd == "selftest":
        return cmd_selftest()
    if args.cmd == "validate-registry":
        data = load_registry(args.registry)
        print(json.dumps({"status": "PASS", "n": len(data["methods"]), "id": data.get("registry_id")}, indent=2))
        return 0
    if args.cmd == "resolve":
        d = AgentDriver(args.registry)
        m = d.resolve(args.method_id)
        print(json.dumps(m, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "run-full":
        dens = None
        if args.densify_map and args.densify_map.exists():
            dens = {k: Path(v) for k, v in json.loads(args.densify_map.read_text()).items()}
        d = AgentDriver(args.registry)
        result = d.run_full(args.src, args.empty, args.out, densify_map=dens)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("status") == "PASS" else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
