# Canonical workflow and stage contracts

| Stage | Input | Output | Stop condition |
|---|---|---|---|
| INTAKE | user goal + assets | typed asset inventory | role/hash/dimensions unresolved |
| READ | BASE + references | scene graph, regions, masks, confidence | critical geometry is ambiguous |
| CONTRACT | READ + requested change | task contract + locks | target overlaps a protected region |
| ROUTE | contract + runtime state | eligible adapter list + reason | no licensed, validated adapter |
| GENERATE | parent + generation mask + context | candidate layer + raw metadata | output lacks provenance |
| REGISTER | candidate + BASE | coordinate transform + residual | alignment error exceeds task limit |
| RECONSTRUCT | registered candidate + masks | composite candidate | protected pixels changed unexpectedly |
| DETAIL | accepted topology | detail-enhanced candidate | detail pass changes topology/identity |
| VALIDATE | BASE + result + contract | hard-gate report + quality vector | any required hard gate fails |
| ACCEPT | all evidence | immutable accepted output + manifest | evidence package incomplete |

## Failure routing

- Wrong part count or connectivity: return to structural design / topology stage; do not try to solve with sharpening or upscaling.
- Correct object, wrong placement: return to registration / coordinate mapping.
- Correct geometry, wrong material: use donor/swatch retexture and local compositing.
- Correct result, low-frequency seams: adjust mask and blend; do not regenerate the full frame.
- Face/identity drift: reject candidate; use identity-protected path or a separate face restoration workflow with independent identity gate.
- Detail enhancement changes silhouette: reject detail stage and restore the pre-detail candidate.

## Master-first temporal rule

Temporal variants must derive from one accepted master. Camera, character identity, prop geometry and world coordinates are explicit locks. Each frame change must be represented as a permitted state transition, not a fresh unconstrained generation.
