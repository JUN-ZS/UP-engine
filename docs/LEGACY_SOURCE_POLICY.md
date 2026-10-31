# Legacy source policy

Reference repository: `https://github.com/JUN-ZS/ai-image-gen-logic-review`

Policy:

- This repository is a new project with an independent Git history.
- No legacy source files, images, generated artifacts, branches, or PRs are modified by this project.
- No bulk copy or subtree import is permitted by default.
- Legacy rules are first mapped as concepts in `docs/SKILL_MAP.md`; individual material is imported only through a reviewed, traceable migration PR.
- Each imported rule must record its original path, source commit, license/provenance, new contract, and test evidence.
- Old artifacts are treated as fixtures only when their rights/provenance and expected invariants are known. Otherwise they remain external references.
- The source repo remains useful as an archive and historical evidence store, not as a runtime dependency.

Initial source context (recorded at project creation): the source repository contains prompt/geometry audit utilities and a large body of image artifacts and skill documentation. The new project deliberately starts with schemas and interfaces rather than copying the artifact-heavy branch wholesale.
