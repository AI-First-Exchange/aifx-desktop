# Claude Contribution Guide (AIFX Desktop)

This file defines how Claude (or any AI assistant) should operate in this repository.

Claude must read `spec/AIFX_CANON_LOCK.md` before generating plans or code.

---

## Operating Rules

1. Do NOT modify governance or declaration text.
2. Do NOT alter integrity model.
3. Do NOT expand scope beyond v0 unless explicitly instructed.
4. Do NOT introduce verification tiers (PVA/VC).
5. Do NOT introduce silent repair behavior.

---

## Planning Protocol

When asked to produce a plan:

- Produce a complete structured blueprint.
- Avoid generic advice.
- Avoid unnecessary overengineering.
- Prefer simple, reproducible solutions.
- Prioritize Apple Silicon compatibility (arm64).
- Assume unsigned build first unless signing is explicitly requested.

---

## Code Generation Rules

When generating code:

- Provide file-by-file blocks.
- Do not rewrite entire files unless necessary.
- Prefer minimal surgical modifications.
- Preserve deterministic behavior.
- Avoid dynamic imports unless required.
- Avoid adding new dependencies unless justified.

---

## Packaging Rules

- Prefer PyInstaller for macOS standalone builds.
- Ensure Qt plugin bundling is handled explicitly.
- Avoid embedding unnecessary native binaries.
- No ffmpeg bundling unless explicitly requested.

---

## Player-Specific Rules

AIFX Player:
- Read-only
- No integrity validation
- No PASS/FAIL UI
- CLI-only developer mode (`--dev`)

---

Claude must end planning responses with:

"Canon preserved."