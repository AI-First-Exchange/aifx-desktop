# AIFX Governance Checklist (SDA by Design)

Status: LOCK CANDIDATE (v0.1)
Purpose: Prevent trust inflation and ensure AIFX outputs remain defensible.

## A. Truth Boundaries (What AIFX IS)
AIFX provides:
- Declared authorship (Self-Declared Authorship)
- Integrity verification (tamper detection via hashes)
- A consistent, inspectable container structure

## B. Non-Claims (What AIFX is NOT)
AIFX does NOT:
- verify identity
- prove originality
- adjudicate copyright
- detect training data usage
- certify human creation
- guarantee legality of content

## C. SDA Rules (Hard)
- `verification_tier` MUST be exactly "SDA"
- No UI or converter option to claim higher tiers in v0
- No language in docs implying verification beyond integrity + declared authorship

## D. Human Anchor (Hard)
- `creator.name` REQUIRED (non-empty)
- `creator.contact` REQUIRED (non-empty; email minimum)
Rationale: A reachable point of accountability at packaging time.

## E. Required Work Identity (Hard)
- `work.title` REQUIRED (non-empty)
Rationale: Every package must have explicit identity.

## F. Declaration (Hard)
- `declaration` REQUIRED (non-empty)
Rationale: Authorship is asserted clearly, not implied.

## G. Integrity (Hard)
- SHA-256 hashes required for all packaged assets + manifest
- Validator must fail on mismatch
- No "cosmetic PASS" allowed

## H. Security (Hard)
- No symlinks
- No path traversal / unsafe filenames
- No remote references required to render/validate
- Packaging-only stance in v0 (no transcoding)

## I. Separation of Powers (Design Rule)
- Converter: produces packages
- Validator: enforces rules and integrity
- Player: displays content (read-only), does not mutate packages

## J. Release Discipline
Before releasing a standard/tool version:
- regression tests include tamper cases
- validator fails deterministically on governance violations
- docs include a "What AIFX does NOT do" section
