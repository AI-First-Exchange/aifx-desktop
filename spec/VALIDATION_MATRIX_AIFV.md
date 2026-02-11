# Validation Matrix (AIFV v0)

Status: LOCK CANDIDATE (v0.1)
Format: Rule -> Check Key -> PASS/FAIL Condition -> Error Message (on FAIL)

## 1. Container Safety
- Rule: No symlinks
  - check: security.no_symlinks
  - fail if: any zip entry is a symlink
  - error: "security: symlinks are not allowed"

- Rule: No unsafe paths (zip-slip)
  - check: security.safe_paths
  - fail if: any entry is absolute or contains '..' or escapes root
  - error: "security: unsafe path detected (possible zip-slip)"

## 2. Required Files
- Rule: manifest.json exists
  - check: files.manifest_present
  - fail if: manifest.json missing
  - error: "manifest.json missing (required)"

- Rule: assets/thumb.jpg exists
  - check: files.thumbnail_present
  - fail if: assets/thumb.jpg missing
  - error: "assets/thumb.jpg missing (required)"

- Rule: exactly one primary video exists
  - check: files.primary_video_single
  - fail if: primary video count != 1
  - error (0): "primary video missing (expected exactly one file matching assets/video.*)"
  - error (>1): "multiple primary videos found (expected exactly one file matching assets/video.*)"

## 3. Manifest Governance
- Rule: work.title non-empty
  - check: manifest.work.title
  - fail if: missing/empty
  - error: "work.title missing (required)"

- Rule: creator.name non-empty
  - check: manifest.creator.name
  - fail if: missing/empty
  - error: "creator.name missing (required)"

- Rule: creator.contact non-empty
  - check: manifest.creator.contact
  - fail if: missing/empty
  - error: "creator.contact missing (required)"

- Rule: mode non-empty
  - check: manifest.mode
  - fail if: missing/empty
  - error: "mode missing (required)"

- Rule: ai_generated must be true
  - check: manifest.ai_generated
  - fail if: missing or not true
  - error: "ai_generated must be true (required)"

- Rule: verification_tier must be SDA
  - check: manifest.verification_tier
  - fail if: != "SDA"
  - error: "verification_tier must be 'SDA' (required)"

- Rule: declaration non-empty
  - check: manifest.declaration
  - fail if: missing/empty
  - error: "declaration missing (required)"

## 4. Integrity / Hashing
- Rule: hashes present for required files
  - check: integrity.hashes_present
  - fail if: any required hash missing
  - error: "integrity: missing hash for required file"

- Rule: hashes match file bytes
  - check: integrity.hashes_match
  - fail if: any hash mismatch
  - error: "integrity: hash mismatch (package may be tampered)"

## 5. Informational (Warnings Only in v0)
- Rule: video facts captured (duration/resolution/fps/codecs)
  - check: info.video_facts_present
  - warn if: missing
  - warning: "info: video facts missing (duration/resolution/fps/codecs) — not required in v0"
