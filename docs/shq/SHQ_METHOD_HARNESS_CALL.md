# CALL · 01472 Harness ABC · 10 秒

```bash
python3 shq_method_harness_abc.py selftest
python3 shq_method_harness_abc.py kill-note
python3 shq_method_harness_abc.py init-scene --out $RUN --preset synth_cliff
python3 shq_method_harness_abc.py run-A --scene $RUN --out $RUN/A
python3 shq_method_harness_abc.py run-B --scene $RUN --out $RUN/B
```

**禁:** 引用 01433 RANK · 用 Telea EMPTY 冒充真除 · 方法自改 hole 算 outside  
**必:** 凍結 SceneBundle · peep 互斥 · A/B/C 不互替  
**ACCEPT_FULL_HD=false**

## Gold ingest（①② 後）

```bash
python3 shq_method_harness_abc.py list-gold
python3 shq_method_harness_abc.py ingest-gold --preset hyr --out runs/hyr_scene
python3 shq_method_harness_abc.py run-gold --preset hyr --out runs/hyr_AB
python3 shq_method_harness_abc.py run-gold --preset jzh --out runs/jzh_AB
python3 shq_method_harness_abc.py run-gold --preset xnv2 --out runs/xnv2_AB
```

| preset | 金 | empty_mode |
|--------|-----|------------|
| hyr | 換涯人 01439 | proxy GrabCut+Telea（非真除） |
| jzh | 機炸回 01441 | proxy GrabCut+Telea |
| xnv2 | 新女畫V2 01464 | **true_diff** L0 vs chu_tou（外力除头） |

`gold/resolved/` 從 `imagine_images` 複製。ACCEPT_FULL_HD=false。

## 審查（01473）
每次 run-gold 後：`python3 shq_audit_force.py audit --summary SUMMARY.json`
SUMMARY 應含 audit_force / empty_mode / claim_level。
