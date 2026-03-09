# Codex Contribution Guide (AIFX Desktop)

This file defines how Codex (or any AI assistant) should operate in this repository.

Codex must read `spec/AIFX_CANON_LOCK.md` before generating plans or code.

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

Codex must end planning responses with:

"Canon preserved."

---

## GUI Rules (AIFX Desktop)

The UI is implemented in **PySide6**.

Primary GUI file:

app.py

UI styling is implemented using **Qt stylesheets** inside `self.setStyleSheet()`.

Agents modifying the UI must follow these constraints:

- Preserve the existing **dark glass aesthetic**
- Maintain **macOS and Windows compatibility**
- Prefer **small stylesheet patches** rather than UI rewrites
- Do NOT replace the stylesheet system
- Do NOT introduce new GUI frameworks

### UI Fix Protocol

When addressing UI issues:

1. Identify the minimal fix.
2. Modify only the relevant stylesheet section.
3. Do not refactor layout code.
4. Do not change widget hierarchy.

Large-scale UI redesigns are **out of scope** unless explicitly requested.

---

## Windows Compatibility

Windows builds must support:

- Python 3.11+
- PySide6
- PyInstaller packaging

Common issues:

- Dark theme text contrast
- Qt plugin bundling
- missing runtime dependencies

Agents should prefer **stylesheet fixes** before modifying logic.

---

## AIFX Desktop Philosophy

AIFX Desktop is designed to be:

- deterministic
- offline-first
- minimal dependency
- reproducible

Agents must preserve these properties.