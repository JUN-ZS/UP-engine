# NFE Architecture v0

```
                 ┌──────────────────┐
                 │  K (master lock) │
                 └────────┬─────────┘
                          │ re-anchor every N
┌─────────┐  ΔS_t   ┌─────▼─────┐  still  ┌──────────┐
│ C0.1    ├────────►│ C0.2 I2I  ├────────►│ candidate │
│ Motion  │         │ G next    │         │ F_{t+1}'  │
└─────────┘         └───────────┘         └────┬─────┘
     ▲                    ▲                    │
     │                    │                    ▼
┌────┴────┐         ┌─────┴─────┐       ┌────────────┐
│ C0 State│◄────────┤ C0.4 A/R  │◄──────┤ C0.3 Valid │
│ F_t,…   │  accept │ Retry     │       │ static DDXX│
└────┬────┘         └───────────┘       │ dynamic    │
     │                                   │ identity   │
     │ accepted frames only              └────────────┘
     ▼
┌─────────────────────────────────────┐
│ C1 FrameBank → C2 Metrics → C3 Layout│
│ C4 Encode (24/60) → C5 Report        │
└─────────────────────────────────────┘
```

### Static vs dynamic validation (C0.3)

1. **Static gate:** SIFT/DDXX on background + non-moving set; residual p95 under camera model.
2. **Dynamic gate:** expected Δ for parts in \(\Delta S_t\); residual **too low** on dynamic parts can mean over-locked (motion erased).
3. **Identity gate:** face/armor crop vs \(K\) (optional ECC / hash band).
4. **Global residual / flow:** report only; not sole pass key.

### Generator interface (C0.2)

```
request: {
  f_t_path, f_tm1_path?, k_path,
  delta_s, scene_lock_prompt,
  forbidden: ["i2v", "optical_flow_as_generation"]
}
response: { f_tp1_path, sha256, generator: "i2i", provenance }
```

ComfyUI may host nodes; Python owns state, gates, retry, and provenance.
