#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHQ Audit Force · write 01473
偷步 / 跑偏 / 出錯審查力 — machine-check reports.

  python3 shq_audit_force.py selftest
  python3 shq_audit_force.py matrix
  python3 shq_audit_force.py audit --report REPORT.json
  python3 shq_audit_force.py audit --summary SUMMARY.json
  python3 shq_audit_force.py stamp  --report REPORT.json --out REPORT_STAMPED.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

WRITE_ID = "01473"
FORMAL = "SHQ_STEAL_DRIFT_AUDIT_FORCE_V1"
ACCEPT_FULL_HD = False

# claim → minimum AF
CLAIM_AF = {
    "C0": 0,
    "C1": 1,
    "C2": 2,
    "C3": 3,
    "C4": 3,
    "C5": 4,
}

TRUE_EMPTY_MARKERS = (
    "true_diff",
    "imagine_remove",
    "chu_bei",
    "chu_tou",
    "true_remove",
    "same_camera_empty",
)
PROXY_EMPTY_MARKERS = (
    "proxy",
    "telea",
    "grabcut",
    "inpaint",
)


def af_rank(s: Optional[str]) -> int:
    if not s:
        return 0
    s = str(s).upper()
    if s.startswith("AF") and s[2:].isdigit():
        return int(s[2:])
    if s.isdigit():
        return int(s)
    return 0


def claim_rank(s: Optional[str]) -> str:
    if not s:
        return "C0"
    s = str(s).upper()
    if s.startswith("C") and len(s) >= 2 and s[1].isdigit():
        return f"C{s[1]}"
    return "C0"


def audit_report(doc: Dict[str, Any], path: str = "") -> Dict[str, Any]:
    """Core auditor: emit steal/drift flags, E_codes, allowed claim, AF estimate."""
    steal: List[str] = []
    drift: List[str] = []
    e_codes: List[str] = []
    notes: List[str] = []

    # --- AF field ---
    af_raw = doc.get("audit_force")
    if af_raw is None:
        e_codes.append("E-AUDIT-00")
        notes.append("missing audit_force → AF0")
        af = 0
    else:
        af = af_rank(af_raw)

    claim = claim_rank(doc.get("claim_level") or doc.get("claim"))
    need = CLAIM_AF.get(claim, 0)
    if af < need:
        e_codes.append("E-AUDIT-01")
        drift.append("CLAIM_OVER_AF")
        e_codes.append("E-DRIFT-04")
        notes.append(f"claim {claim} needs AF{need}, have AF{af}")

    # --- empty_mode honesty ---
    empty = str(doc.get("empty_mode") or doc.get("protocol", {}).get("empty_mode") or "").lower()
    if empty:
        is_proxy = any(m in empty for m in PROXY_EMPTY_MARKERS)
        claims_true = any(m in empty for m in ("true_remove", "true_same", "imagine_only")) and not is_proxy
        # if labels say true but also telea
        if "true" in empty and any(m in empty for m in ("telea", "proxy", "grabcut")):
            steal.append("PROXY_AS_TRUE")
            e_codes.append("E-STEAL-02")
            drift.append("EMPTY_MODE_LIE")
            e_codes.append("E-DRIFT-02")
        elif is_proxy:
            notes.append(f"honest proxy empty_mode={empty}")
        elif claims_true or any(m in empty for m in TRUE_EMPTY_MARKERS):
            notes.append(f"true-ish empty_mode={empty}")
    else:
        # if report claims PASS on return methods without empty_mode
        if doc.get("status") in ("PASS", "PASS_C2", "SUCCESS") or doc.get("B_status") == "PASS_B":
            if "n_pass" in doc or "PASS_C2" in str(doc.get("counts", {})):
                notes.append("no empty_mode field (warn)")

    # --- outside basis ---
    basis = str(doc.get("outside_basis") or "").lower()
    if doc.get("outside") == 0 or doc.get("outside_frozen_hole") == 0:
        if basis and "frozen" not in basis and "method" in basis:
            steal.append("SELF_MASK_PASS")
            e_codes.append("E-STEAL-03")
        if not basis and doc.get("write_id") == "01433":
            steal.append("SELF_MASK_PASS")
            e_codes.append("E-STEAL-03")

    # --- 01433 special kill ---
    formal = str(doc.get("formal") or "")
    wid = str(doc.get("write_id") or "")
    if wid == "01433" or "UNIQUE_SRC" in formal or "RESET_EACH_RETURN" in formal:
        steal.append("RANK_WITHOUT_CONTROL")
        e_codes.append("E-STEAL-04")
        notes.append("01433-style confounded ranking killed by 01472/01473")

    # --- STICK vs preset drift hints ---
    stick = str(doc.get("STICK") or doc.get("stick") or doc.get("stick_hint") or "")
    preset = str(doc.get("preset") or doc.get("gold_preset") or "")
    expected = {
        "hyr": "HUAN_YA_REN",
        "jzh": "JI_ZHA",
        "xnv2": "XIN_NV",
    }
    if preset in expected and stick and expected[preset] not in stick.upper().replace("STICK_", ""):
        # stick might be STICK_HUAN_YA_REN
        if expected[preset] not in stick.upper():
            drift.append("STICK_MISLABEL")
            e_codes.append("E-DRIFT-01")
            notes.append(f"preset={preset} stick={stick}")

    # --- method name honesty if receipts present ---
    receipts = doc.get("receipts") or []
    fake_neural = 0
    for r in receipts:
        mid = str(r.get("method_id") or "")
        impl = str(r.get("impl") or "")
        if "NEURAL" in mid.upper() and impl and impl not in ("neural", "nn", "torch"):
            if impl in ("dens_u", "hardpaste", "copy_peep"):
                fake_neural += 1
    if fake_neural:
        drift.append("METHOD_NAME_LIE")
        e_codes.append("E-DRIFT-03")

    # --- required vs executed steps ---
    req = doc.get("required_steps") or []
    exe = doc.get("executed_steps") or []
    if req and exe is not None:
        missing = [s for s in req if s not in exe]
        if missing and _looks_like_pass(doc):
            steal.append("SKIP_REQUIRED_STEP")
            e_codes.append("E-STEAL-01")
            notes.append(f"missing steps {missing}")

    # --- layer substitute ---
    if doc.get("layer") == "A" and str(doc.get("claim_level", "")).upper() in ("C4", "C5"):
        drift.append("LAYER_SUBSTITUTE")
        e_codes.append("E-DRIFT-06")

    # --- E codes presence on failure ---
    if not _looks_like_pass(doc) and not e_codes and not doc.get("E_codes"):
        e_codes.append("E-AUDIT-02")

    # --- ACCEPT_FULL_HD gate ---
    if doc.get("ACCEPT_FULL_HD") is True and af < 4:
        e_codes.append("E-AUDIT-01")
        steal.append("SKIP_REQUIRED_STEP")
        e_codes.append("E-STEAL-01")
        notes.append("ACCEPT_FULL_HD requires AF4")

    # de-dup
    steal = sorted(set(steal))
    drift = sorted(set(drift))
    e_codes = sorted(set(e_codes))

    # effective AF after issues
    af_eff = af
    if "E-AUDIT-00" in e_codes:
        af_eff = 0
    if steal:
        claim_allowed = "C0"
        status = "FAIL_STEAL"
    elif drift:
        claim_allowed = "C1" if claim_rank(claim) > "C1" or True else claim
        # if only soft drift
        claim_allowed = _min_claim(claim, "C1")
        status = "WARN_DRIFT" if not steal else "FAIL_STEAL"
    else:
        claim_allowed = _max_claim_for_af(af_eff)
        claim_allowed = _min_claim(claim, claim_allowed)
        status = "PASS_AUDIT"

    if steal:
        status = "FAIL_STEAL"
        claim_allowed = "C0"

    return {
        "write_id": WRITE_ID,
        "formal": FORMAL,
        "source": path,
        "status": status,
        "audit_force_declared": af_raw,
        "audit_force_effective": f"AF{af_eff}",
        "claim_declared": claim,
        "claim_allowed": claim_allowed,
        "steal_flags": steal,
        "drift_flags": drift,
        "E_codes": e_codes,
        "notes": notes,
        "ACCEPT_FULL_HD": ACCEPT_FULL_HD,
        "rule": "STEAL→C0 ban SUCCESS; DRIFT→≤C1; AF gates claim",
    }


def _looks_like_pass(doc: Dict[str, Any]) -> bool:
    if doc.get("status") in ("PASS", "PASS_C2", "PASS_A", "PASS_B", "SUCCESS", "PASS_AUDIT"):
        return True
    if doc.get("B_status") == "PASS_B":
        return True
    if doc.get("selftest") == "PASS":
        return True
    if isinstance(doc.get("n_pass"), int) and doc["n_pass"] > 0:
        return True
    counts = doc.get("counts") or {}
    if counts.get("PASS_C2", 0) > 0:
        return True
    return False


def _min_claim(a: str, b: str) -> str:
    order = ["C0", "C1", "C2", "C3", "C4", "C5"]
    return order[min(order.index(claim_rank(a)), order.index(claim_rank(b)))]


def _max_claim_for_af(af: int) -> str:
    # AF0→C0, AF1→C1, AF2→C2, AF3→C4, AF4→C5
    if af <= 0:
        return "C0"
    if af == 1:
        return "C1"
    if af == 2:
        return "C2"
    if af == 3:
        return "C4"
    return "C5"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_audit(args: argparse.Namespace) -> int:
    paths: List[Path] = []
    if args.report:
        paths.append(Path(args.report))
    if args.summary:
        paths.append(Path(args.summary))
    if args.dir:
        paths.extend(sorted(Path(args.dir).glob("**/*REPORT*.json")))
        paths.extend(sorted(Path(args.dir).glob("**/SUMMARY.json")))
    if not paths:
        print("need --report / --summary / --dir", file=sys.stderr)
        return 2
    results = []
    worst = 0
    for p in paths:
        if not p.exists():
            print(f"missing {p}", file=sys.stderr)
            worst = max(worst, 2)
            continue
        doc = load_json(p)
        r = audit_report(doc, str(p))
        results.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        if r["status"] == "FAIL_STEAL":
            worst = max(worst, 1)
    if args.out and results:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return worst


def cmd_stamp(args: argparse.Namespace) -> int:
    p = Path(args.report)
    doc = load_json(p)
    r = audit_report(doc, str(p))
    doc["audit_stamp"] = r
    # fill required fields if missing
    doc.setdefault("audit_force", r["audit_force_effective"])
    doc.setdefault("steal_flags", r["steal_flags"])
    doc.setdefault("drift_flags", r["drift_flags"])
    doc.setdefault("E_codes", r["E_codes"])
    doc["claim_level"] = r["claim_allowed"]
    out = Path(args.out or p.with_name(p.stem + "_STAMPED.json"))
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stamped": str(out), "status": r["status"], "claim_allowed": r["claim_allowed"]}, ensure_ascii=False))
    return 0 if r["status"] != "FAIL_STEAL" else 1


def cmd_matrix(_: argparse.Namespace) -> int:
    rows = []
    for c, af in CLAIM_AF.items():
        rows.append({"claim": c, "min_audit_force": f"AF{af}", "ACCEPT_FULL_HD": c == "C5"})
    print(json.dumps({"write_id": WRITE_ID, "matrix": rows, "rule": "STEAL→C0; DRIFT≤C1"}, ensure_ascii=False, indent=2))
    return 0


def cmd_selftest(_: argparse.Namespace) -> int:
    cases = []
    # 1 clean AF2 C2
    d1 = {
        "claim_level": "C2",
        "audit_force": "AF2",
        "empty_mode": "proxy_grabcut_telea",
        "outside_basis": "frozen_M_hole",
        "status": "PASS_A",
        "STICK": "STICK_HUAN_YA_REN",
        "preset": "hyr",
    }
    r1 = audit_report(d1, "clean")
    cases.append(("clean_proxy", r1["status"] == "PASS_AUDIT" and not r1["steal_flags"], r1))

    # 2 proxy labeled true
    d2 = {
        "claim_level": "C2",
        "audit_force": "AF2",
        "empty_mode": "true_remove_telea_proxy",
        "status": "PASS",
    }
    r2 = audit_report(d2, "lie")
    cases.append(("proxy_as_true", "E-STEAL-02" in r2["E_codes"], r2))

    # 3 01433 kill
    d3 = {"write_id": "01433", "formal": "SHQ_RESET_EACH_RETURN_UNIQUE_SRC_01433", "counts": {"PASS_C2": 19}, "claim_level": "C2"}
    r3 = audit_report(d3, "01433")
    cases.append(("01433_kill", r3["status"] == "FAIL_STEAL" and "E-STEAL-04" in r3["E_codes"], r3))

    # 4 missing AF
    d4 = {"claim_level": "C5", "status": "SUCCESS", "ACCEPT_FULL_HD": True}
    r4 = audit_report(d4, "noaf")
    cases.append(("no_af_c5", r4["status"] == "FAIL_STEAL" and "E-AUDIT-00" in r4["E_codes"], r4))

    # 5 claim over AF
    d5 = {"claim_level": "C5", "audit_force": "AF2", "empty_mode": "true_diff_chu_tou"}
    r5 = audit_report(d5, "over")
    cases.append(("claim_over_af", "E-DRIFT-04" in r5["E_codes"] or "E-AUDIT-01" in r5["E_codes"], r5))

    # 6 real gold summary path if exists
    gold = Path("/workspace/artifacts/SETS/PROJ_SHQ_KILL01433_HARNESS_ABC_01472/runs/gold_ingest/xnv2/SUMMARY.json")
    if gold.exists():
        doc = load_json(gold)
        doc.setdefault("audit_force", "AF2")
        doc.setdefault("claim_level", "C2")
        doc.setdefault("outside_basis", "frozen_M_hole")
        r6 = audit_report(doc, str(gold))
        cases.append(("xnv2_summary", r6["status"] in ("PASS_AUDIT", "WARN_DRIFT"), r6))

    ok = all(c[1] for c in cases)
    out = {
        "selftest": "PASS" if ok else "FAIL",
        "write_id": WRITE_ID,
        "cases": [{"name": n, "ok": o, "status": r["status"], "E": r["E_codes"]} for n, o, r in cases],
        "ACCEPT_FULL_HD": False,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    Path("/workspace/artifacts/SETS/PROJ_SHQ_AUDIT_FORCE_01473/gold/SELFTEST.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="SHQ Audit Force 01473")
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("selftest").set_defaults(func=cmd_selftest)
    sp.add_parser("matrix").set_defaults(func=cmd_matrix)

    p = sp.add_parser("audit")
    p.add_argument("--report", default=None)
    p.add_argument("--summary", default=None)
    p.add_argument("--dir", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_audit)

    p = sp.add_parser("stamp")
    p.add_argument("--report", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_stamp)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
