# AIFX Desktop

**AIFX Desktop is the reference converter + validator for the AI-First Exchange (AIFX) standard.**

It packages AI-generated media into verifiable containers and enforces provenance and integrity rules through deterministic validation.

> Status: **Active refactor**  
> Structure is being locked first. Implementation follows.

---

## What is AIFX?

**AIFX (AI-First Exchange)** is an open container standard for AI-generated media.

An AIFX package bundles:
- the media asset(s)
- a `manifest.json` with declared authorship and metadata
- cryptographic hashes for integrity verification

AIFX does **not** attempt to prove originality or ownership.  
It records **what a creator declares**, and whether the package has been **tampered with**.

---

## What this repository contains

This repo focuses on the **desktop tooling layer** of AIFX.

### Included
- ✅ AIFM converter (music)
- ✅ AIFM validator (governance + integrity)
- 🧪 Early AIFV groundwork
- 🖥️ Desktop UI (converter + validator)
- 🧱 Core validation and conversion logic
- 📄 Lock specs and architecture docs

### Not included
- ❌ Radio programming metadata (owned by aiRX)
- ❌ Trust scoring or identity verification (future scope)
- ❌ Platform moderation logic

---

## Design principles (locked)

- **SDA only** — Self-Declared Authorship is the only verification tier in v0
- **Validators do not lie** — packages pass or fail deterministically
- **No silent assumptions** — required fields are enforced
- **Structure before features** — governance first, UX second
- **Portability over platforms** — packages outlive any one service

---

## AIFX formats

- **AIFM** — AI-generated music
- **AIFV** — AI-generated video
- **AIFI** — AI-generated images
- **AIFP** — AI-generated projects

Each format follows the same provenance and integrity model.

---

## Current status

This workspace is **intentionally incomplete and unstable**.

You should expect:
- refactors
- breaking changes
- evolving validation rules

What *is* stable:
- core governance philosophy
- validator enforcement model
- SDA-by-design approach

---

## Related projects

- **AIFX Standard** — formal specs and rules
- **aiRX Radio** — AI-first distribution using AIFX packages

(Links will be added as repos stabilize.)

---

## Who this is for

- Developers building AI media tooling
- Platforms that need defensible AI provenance
- Creators who want portable, verifiable AI works
- Researchers studying AI authorship governance

---

## License

Open source. Governance-focused. Human-directed by design.
