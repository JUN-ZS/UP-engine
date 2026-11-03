# NFE True 60fps · I2I per frame (not FRAMEBACK)

## Rule
\[
F_{t+1}=G_{i2i}(F_t,F_{t-1},K,\Delta S_t=\mathrm{1/60s},C_t)
\]
then TemporalValidator (+ optional DDXX soft) · Accept/Reject · Encode fps=60.

**Forbidden as G:** I2V, Farneback/minterpolate as generation.

## Cost
| Target | I2I steps |
|--------|-----------|
| 1s @60 | 60 |
| 15s @60 | 900 |
| Pilot N11 | 11 (~0.18s) |

## CLI
```bash
# after agent fills accepted/F*.png
python tools/nfe_true_60fps_i2i_pilot.py gate --job-dir runs/nfe/true60_i2i_17373
python tools/nfe_true_60fps_i2i_pilot.py encode --job-dir runs/nfe/true60_i2i_17373 --fps 60
```
