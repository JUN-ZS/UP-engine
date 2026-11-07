# SHQ C5 Gold+CI (write 01395)

**claim_level C5** · **ACCEPT_FULL_HD=true** only when all gates pass.

## Gates
- diag geometry: ncc≥0.99, phase<0.5, outside_diff=0, leak=0
- Skill D: elev_remap=false, peep-α paste
- empty samepose: bg_ncc≥0.90, freeframe=false (bg-aware)
- n_parts≥2, coverage<0.40
- no horizontal flip + L/R order
- ghost laplacian outside < 2.5
- densify adapter + size densify policy
- edit_permission all false
- anti-tautology, registry validate
- gold fixture replay

## Fixture
`research/shq_v9/gold/GOLD_FIXTURE.json`

## Notes
- Telea same-pose empty allowed when Imagine freeframe blocked
- dual-mecha S1 may force grabcut if DIFF L-split fails
- identity_proxy_LR (not face human ID)
