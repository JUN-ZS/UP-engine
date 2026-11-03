# NFE ALL 框架栓死表

| 層 | 模組／工具 | 檔 |
|----|------------|-----|
| 公式 | F_{t+1}=G(...) | docs/NEXT_FRAME_ENGINE_CHARTER.md |
| C0 | TemporalState | src/ige/nfe/state.py |
| C0.1 | MotionCompiler | src/ige/nfe/motion.py |
| C0.2 | G=I2I（外部／本機） | pilot accept + STICK prompt |
| C0.3 | TemporalValidator | src/ige/nfe/validate.py |
| C0.3ext | F2F verify + DDXX | tools/siax_next_frame_f2f_verify.py |
| C0.4 | NextFrameLoop | src/ige/nfe/loop.py |
| STICK | evolve attach | src/ige/nfe/stick.py |
| ALL bolt | framework | src/ige/nfe/framework.py |
| C1–C5 | still kit | tools/still_sequence_f2f_kit.py |
| 一鍵 | one_click | tools/nfe_one_click.py · .ps1 |
| DDXX | multiview | src/ige/registration/* |

一鍵：`python tools/nfe_one_click.py --master F0.png --job-id X --out-dir runs/nfe/X`
