# Hub notes — IGE_SHQ Modular Methods Toolkit v2.0

**Status:** research-only. **Not** wired into `src/ige` production.

**What it is:** 22 categorized standalone methods (`M01`–`M22`) in `methods/cat01`…`cat05`, plus 3 end-to-end recipes (`R01`–`R03`) in `recipes/`, with unified CLI/SDK `invoke_method.py` and batch runner `try_all_methods_one_by_one.py`.

**Zip:** `IGE_SHQ_Modular_Methods_Toolkit_v2.0.zip`

## Hub smoke (this PR)

| Check | Result |
|-------|--------|
| `python3 invoke_method.py --list` | exit **0** (22 methods + 3 recipes) |
| `python3 invoke_method.py --list-parts` | exit **0** (P01–P18) |
| `python3 invoke_method.py --info M12` | exit **0** |
| `python3 invoke_method.py --run M01 --part P08` | **PASS** · exit **0** |

Attached evidence (user-provided, preserved):

- `docs/TRY_ALL_METHODS_RECEIPT_22of22_3of3_PASS.json` — 22/22 methods + 3/3 recipes PASS receipt
- `outputs/SHQ_MODULAR_METHODS_CATALOG_BOARD.png` — catalog board

## Quick invoke

```bash
python3 invoke_method.py --list
python3 invoke_method.py --list-parts
python3 invoke_method.py --info M12
python3 invoke_method.py --run M12 --part P08
python3 invoke_method.py --category cat04 --part P08
python3 invoke_method.py --recipe R01 --part P08
python3 try_all_methods_one_by_one.py --part P08
```

Guide: [`SHQ_MODULAR_METHODS_GUIDE.md`](./SHQ_MODULAR_METHODS_GUIDE.md).  
Related layered package: [`../ige_shq_github_verifiable_package_v1.0/`](../ige_shq_github_verifiable_package_v1.0/).
