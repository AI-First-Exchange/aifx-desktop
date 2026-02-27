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

## 4. Integrity / Hashing (Canonical AIFX)
- Rule: integrity section present
  - check: integrity
  - fail if: manifest.integrity missing
  - error: "manifest.integrity missing"

- Rule: integrity algorithm is sha256
  - check: integrity
  - fail if: integrity.algorithm != "sha256"
  - error: "Unsupported integrity.algorithm: <value>"

- Rule: integrity.hashed_files present and non-empty
  - check: integrity
  - fail if: integrity.hashed_files missing/empty or not an object
  - error: "integrity.hashed_files missing or empty"

- Rule: required file sha256 present
  - check: integrity
  - fail if: any required sha256 missing in integrity.hashed_files
  - error: "Missing sha256 for <relpath>"

- Rule: file bytes match expected sha256
  - check: integrity
  - fail if: any mismatch
  - error: "Hash mismatch for <relpath>: expected <expected>, got <actual>"

- Rule: manifest.json hash entry exists
  - check: integrity
  - fail if: integrity.hashed_files['manifest.json'] missing
  - error: "integrity.hashed_files['manifest.json'] missing"

- Rule: manifest.json sha256 present
  - check: integrity
  - fail if: integrity.hashed_files['manifest.json'].sha256 missing
  - error: "integrity.hashed_files['manifest.json'].sha256 missing"

- Rule: canonical manifest hash matches when mode is canonical_excludes_self
  - check: integrity
  - fail if: mismatch
  - error: "Hash mismatch for manifest.json: expected <expected>, got <actual>"

## 5. Informational (Warnings Only in v0)
- Rule: video facts captured (duration/resolution/fps/codecs)
  - check: info.video_facts_present
  - warn if: missing
  - warning: "info: video facts missing (duration/resolution/fps/codecs) — not required in v0"
