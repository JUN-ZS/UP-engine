# Concept architecture: continuously coordinated global-to-subset execution

## 1. One parent contract, many spatial subsets

The graph is not `tile → independent interpretation → stitch`.

It is:

`global image + global rules + geometry/state/history`

→ compile immutable parent contract

→ project the same contract into every TTP crop

→ turn each subset action map into a latent-resolution noise mask

→ execute each crop as a constrained child subset

→ compare overlapping child outputs in global coordinates

→ accept, abstain, or roll back per pixel/region

→ audit global invariants

→ write a next-iteration state proposal without silent promotion.

Every tile task carries the same `contract_id`, `rules_digest`, `policy_revision`, and parent state. Tile-local coordinates are only a projection of the global coordinate frame.

## 2. Four layers of rules

`PRESERVE` is pixel-level immutability. `REFINE` allows appearance improvement within geometry/semantic constraints. `GENERATE` requires an explicit operator-confirmed region. `REJECT` vetoes the candidate and falls back to source.

The global default is not a semantic permission to invent content. Operator spatial rules may deliberately narrow or explicitly authorize a region. Conflicts among overlapping rules resolve to the most restrictive action. A child tile is never allowed to loosen its parent rule. The same parent action map also drives the pre-sampler `noise_mask`: `PRESERVE`/`REJECT` are zero-noise, `REFINE`/`GENERATE` use configured denoise weights. A post-decode pixel gate restores exact source pixels for hard-preserve zones.

## 3. Batch-level conditioning boundary

The supplied source workflow has one shared `CLIPTextEncode` → `FluxGuidance` → `BasicGuider` → `SamplerCustomAdvanced` chain for the latent batch. Candidate B duplicates this conditioning/sampler/decode path; baseline A remains unchanged. The new compiler produces a global prompt which is shared across every B tile. Each tile also receives a local subset prompt profile. If profiles differ, the projector reports multiple execution groups; a single stock sampler batch cannot be said to have applied all of those local prompts.

This is intentionally surfaced instead of faking per-tile conditioning. A future execution adapter must either split compatible subsets into distinct sampler executions or prove a per-sample conditioning mechanism against the exact ComfyUI/Flux nodes in use.

## 4. Overlap is an evidence region, not a blending license

The reconciler computes candidate spread over every pixel covered by multiple tiles. If overlap candidates agree within the configured thresholds, it writes their consensus. If they disagree, it abstains and restores the source pixel. This prevents conflicting generations from being hidden by a feather blend.

The rule is deliberately conservative. It can leave a visible transition between refined and source pixels; therefore overlap conflict is an acceptance blocker when it exceeds the policy threshold, not a claim of seamless quality.

## 5. State/history and reverse diagnosis

The next-iteration file records failed subsets, warnings and operator feedback, but makes no automatic policy changes. The diagnostic categories are:

- rule map inconsistent before sampling → global logic compiler / coordinate projection;
- rule map consistent, output violates action or geometry → conditioning/generator control;
- tile outputs individually acceptable, overlap conflict → shared context/latent or tile execution grouping;
- tiles are acceptable but assembled canvas violates source/outside invariants → reassembly coordinates/write masks;
- result changes when TTP positions change → boundary-dependent model behavior.

The current prototype is able to prove mapping, mask construction, gating, overlap conflict fallback and audit behavior. It cannot yet prove identity preservation by itself; that still requires silhouette/landmark observations and operator-confirmed geometry.

## 6. Tile-level attribution and continuous iteration

Every reconciliation report now includes one diagnostic record per tile: its global `tile_id`, TTP position, overlap pixel count, conflict pixel count, conflict fraction, threshold and failure reasons. A conflict region is attributed to every tile participating in that overlap. The audit copies failed tile IDs into the next iteration state so the next review can target the implicated subsets instead of blindly re-running the whole frame.

The state remains advisory. It carries `parent_contract_id`, `parent_state_id`, iteration number, previous status and warnings, but `operator_approved=false`, `automatic_policy_changes=false`, and `geometry_promotion=false`. Retry selection may be subset-specific; policy authority remains global and requires explicit operator revision.

## 7. What the metamorphic test proves (and does not prove)

The current metamorphic test compiles one parent action map and projects it into two different valid tile grids. For a deterministic global candidate image, reconstructing the slices gives the same full-frame result. This demonstrates that rule projection and coordinate reconciliation are invariant to the chosen grid when the tile candidates are themselves identical slices of one global candidate.

It does not prove that a diffusion model will emit identical pixels when tile boundaries move. That requires actual ComfyUI replay experiments with fixed model, noise/latent strategy, prompt, sampler, sigma schedule and controlled boundary perturbations.
