# Canonical workflow and stage contracts

| Stage | Input | Output | Stop condition |
|---|---|---|---|
| INTAKE | user goal + assets | typed asset inventory | role/hash/dimensions unresolved |
| READ | BASE + references | raster facts, human regions, segmentation/VLM proposals | critical geometry is ambiguous |
| REVIEW | proposal boxes + original image | corrected regions + human_verified relations | evidence does not support the claim |
| CONTRACT | READ + requested change | task contract + explicit locks | target overlaps protected region |
| MASK COMPILE | selected editable region IDs + READ report | generation whitelist + exact protected complement | BASE or region-mask hash mismatch |
| ROUTE | contract + runtime state | eligible adapter list + reason | no licensed, validated adapter |
| GENERATE | parent + task mask + geometry locks + context | candidate layer + raw metadata | output lacks provenance |
| REGISTER | candidate + BASE | coordinate transform + residual | alignment error exceeds task limit |
| RECONSTRUCT | registered candidate + task masks | composite candidate | protected pixels changed unexpectedly |
| DETAIL | accepted topology | detail-enhanced candidate | detail pass changes topology/identity |
| VALIDATE | BASE + result + contract | hard-gate report + quality vector | any required hard gate fails |
| ACCEPT | all evidence | immutable accepted output + manifest | evidence package incomplete |

## Permission and evidence rules

- A model-generated mask is a proposal, never an editable permission.
- A model-generated relation is a candidate, never a geometry lock.
- Only a human region annotation with permission=editable can enter a task generation mask.
- Only a human_verified relation with source=human and evidence can enter geometry_locks.
- Every task mask is limited to the selected region IDs. All other source pixels are protected.
- Source image SHA-256 and selected region-mask SHA-256 values are rechecked before packet creation.
- The current relation graph describes image-plane evidence. Metric 3D geometry requires an independently calibrated depth/XYZ source and its own uncertainty.

## Failure routing

- Wrong part count or connectivity: return to structural design / topology stage; do not try to solve with sharpening or upscaling.
- Correct object, wrong placement: return to registration / coordinate mapping.
- Correct geometry, wrong material: use donor/swatch retexture and local compositing.
- Correct result, low-frequency seams: adjust mask and blend; do not regenerate the full frame.
- Face/identity drift: reject candidate; use identity-protected path or a separate face restoration workflow with independent identity gate.
- Detail enhancement changes silhouette: reject detail stage and restore the pre-detail candidate.
- Model relation uncertain or unsupported by evidence: keep candidate or reject; never promote it automatically.

## Master-first temporal rule

Temporal variants must derive from one accepted master. Camera, character identity, prop geometry and world coordinates are explicit locks. Each frame change must be represented as a permitted state transition, not a fresh unconstrained generation.
