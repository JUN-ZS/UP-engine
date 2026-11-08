# Extraction provenance — Gemini share `47yxULPlPy0W`

## Identity

| Field | Value |
|-------|-------|
| Short URL | https://share.gemini.google/47yxULPlPy0W |
| Canonical share | https://gemini.google.com/share/970343afbbef |
| Share id | `970343afbbef` |
| Title | 物件導向幾何約束升頻架構 |
| Model (reported) | 3.5 Flash-Lite |
| Turns | 15 |
| Extracted (box local) | 2026-11-07 Asia/Hong_Kong |

## Method (keyless)

1. Resolve short URL `share.gemini.google/47yxULPlPy0W` → share id `970343afbbef`.
2. Fetch public share page HTML.
3. Call Gemini `batchexecute` RPC with method key **`ujx1Bf`** (keyless public share payload; no user OAuth).
4. Parse nested JSON stream into turns + file-tag artifacts.
5. Decode / recover three Python artifacts into `artifacts/`.
6. Write cleaned transcript `Gemini-完整對話.md` and structured `messages_clean.json` (local only).

Raw multi-MB blobs (`payload.json`, `raw_ujx1Bf.txt`, retry dumps) are **not** committed to this repo (disk + noise). Integrity is pinned by SHA-256 below.

## SHA-256 (local extract on box)

```
ed3d8e4796245f6a88b6cae61e18665ca7955f9272aa729537ec1f765109b145  raw_ujx1Bf.txt
19e0de42445f93784f5adde63ab684fe6eb4bb3a14591f20119ec4393382752e  payload.json
6c6423fadf7d8f9ff42fbf19c57436ac56cc4f186d02df8cff7d3178185b5662  Gemini-完整對話.md
c87d014b6102844b857a1339fb02746220328bd580c4b69ba11209098fb63adb  artifacts/shq_v2_self_consistent_engine.py
3358f7b9dd7023012390f0fa8460ce124b3ab26231a1eca5bd6b9022ad8f5517  artifacts/shq_object_extractor.py
8c5ffe2fa69ef184ef805eccb69191b6eaa719b5e2dd323ba8648e07de85486c  artifacts/shq_recursive_layer_return.py
```

## What was committed here

- `Gemini-完整對話.md` — cleaned full transcript (this folder).
- Research copies of the three `.py` artifacts → `research/shq_v9/` (see that README).
- Program guidance derived from the conversation → `docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`.

Binary images from Gemini file-tags were **not** embedded.
