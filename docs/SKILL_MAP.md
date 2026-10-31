# Legacy skill mapping (conceptual, not imported code)

This table maps old techniques to engine roles. Names are retained as source vocabulary, not assumed to be validated algorithms.

| Legacy skill / concept | New engine layer | Intended responsibility | Cannot substitute for |
|---|---|---|---|
| MSR | perception + task planner | read whole image, choose region and refinement scale | pixel validator |
| OTL0 | topology contract | part count, shape, connectivity locks | material/detail pass |
| RML | prompt compiler | concise invariant fingerprints | structured contract |
| ZYF / ETZ / SCD | donor preparation | isolate, correct and lock garment donors | final compositor |
| TEX4 | reconstruction workflow | garment geometry / hand-interaction / coordinate restoration | universal image model |
| ghost interaction board | perception / occlusion graph | distinguish cloth from hands, props and head | pixel-level acceptance alone |
| RRT | correction workflow | derive a corrected patch from a known action state | arbitrary whole-frame regeneration |
| P_G | coordinate/material mapping | map material to original garment coordinates | topology repair |
| OBA | layered object assembly | accumulate parts against a neutral working canvas | direct editing of immutable BASE |
| SWP / SPM / SIAX / S1HL | detail enhancement | multi-scale texture/detail recovery | wrong object structure |
| GOU / V5 / GCS / ECC / WHOLE | registration + compositor | align, mask, blend and preserve BASE | identity/topology validation |
| N2R / WNK | material/noise analysis | separate real specular from artifacts | generation or geometry |
| DAMD / HTFC | temporal workflow | controlled keyframe/state transitions | single-image detail restoration |

Import rule: reimplement or wrap a skill only after its inputs, outputs, invariants, failure states, and benchmark are defined. Documentation alone does not make a skill executable.
