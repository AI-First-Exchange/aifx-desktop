# AIFX Canon Lock (v0)

This document defines non-negotiable architectural rules for AIFX.

All AI assistants (Claude, ChatGPT, etc.) must read this before contributing.

---

## Core Philosophy

> Declare only what you can prove today.  
> Design for what you can verify tomorrow.

AIFX is a deterministic AI provenance packaging framework.

---

## Self-Declared Authorship (SDA)

- Only standardized declaration: **AIFX-SDA-001**
- No custom declaration text allowed
- Converters auto-insert declaration
- CLI does NOT accept `--declaration`
- Attestation optional (initials + template_id + timestamp)

No identity verification layer in v0.
No PVA. No VC.

---

## Integrity Model

- Hash algorithm: SHA256
- `manifest_hash_mode = canonical_excludes_self`
- Hash mismatch = FAIL
- Deterministic packaging only
- No silent corrections
- No auto-repair

---

## Scope Discipline (v0)

- Structure + integrity enforcement only
- No governance expansion
- No verification tiers beyond SDA
- No identity claims

---

## Application Separation

### AIFX Desktop
- Converter + Validator
- Enforces structure + integrity
- Displays PASS / FAIL

### AIFX Player
- Separate standalone application
- Read-only viewer + playback tool
- Does NOT perform integrity validation
- Does NOT display PASS/FAIL verdicts
- Does NOT modify packages
- Only minimal container sanity checks:
  - Safe open
  - Manifest exists
  - Primary media exists

---

## AIFX Player Developer Mode

- CLI-only (e.g., `--dev`)
- No GUI toggle
- Default behavior: open AIFX packages only
- Raw media allowed only when launched with `--dev`
- Read-only
- No validation
- No package mutation

---

Any proposed change that modifies:
- Declaration
- Integrity
- Scope
- Validation semantics

Must be explicitly approved.