# AI-First Exchange (AIFX)

**AI-First Exchange (AIFX)** is an open, governance-first container standard for AI-generated media.

It defines how AI-created works are **packaged, declared, and verified** — focusing on **provenance, integrity, and portability**, not ownership claims or legal adjudication.

> See **VISION.md** for long-term direction and roadmap.

---

## What problem AIFX solves

As AI-generated content becomes ubiquitous and AI answers replace traditional search clicks, creators and platforms need a clear way to answer:

- Who is declaring authorship?
- How was this work generated?
- Has this package been altered since it was created?

AIFX provides a **defensible, machine-verifiable structure** to answer those questions.

---

## What AIFX is

AIFX is a **container format family** that bundles:
- AI-generated media assets
- A structured `manifest.json`
- Declared authorship and creation context
- Cryptographic hashes for integrity verification

AIFX packages are designed to be:
- Portable across platforms
- Verifiable without central authority
- Honest about what they do *and do not* claim

---

## What AIFX is not

- ❌ Not a copyright system
- ❌ Not proof of originality
- ❌ Not an identity verification authority
- ❌ Not a moderation or enforcement platform

AIFX records **Self-Declared Authorship (SDA)** and enforces **structural and integrity rules only**.  
Trust scoring, identity verification, and enforcement belong to downstream platforms.

---

## Verification philosophy (current scope)

- **SDA only** — Self-Declared Authorship is the sole verification tier in v0
- **Validators do not lie** — packages deterministically pass or fail
- **No silent assumptions** — required fields are enforced explicitly
- **Structure before UX** — governance precedes convenience
- **Provenance over platforms** — packages must outlive services

---

## AIFX formats

- **AIFM** — AI-generated music
- **AIFV** — AI-generated video
- **AIFI** — AI-generated images
- **AIFP** — AI-generated projects

All formats share the same provenance and integrity model.

---

## Repositories

- **aifx-desktop**  
  Converter and validator desktop tooling for AIFX packages.

Additional repositories will appear as components stabilize.

---

## Status

AIFX is under **active development**.

Expect:
- refactors
- evolving specifications
- breaking changes

What is stable:
- governance philosophy
- verification boundaries
- integrity enforcement model

---

## Stewardship

AI First Exchange™ (AIFX™) is an open standard stewarded by its original author and community contributors.

Use of the source code or specifications does not grant permission to imply official endorsement or certification beyond what is explicitly documented.

---

## Core principle

> **Declare only what you can prove today.  
> Design for what you can verify tomorrow.**
