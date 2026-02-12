# AIFV v0 Lock Spec (AIFX)

Status: LOCK CANDIDATE (v0.1)
Scope: Packaging + integrity + declared provenance for AI-generated video.
Non-goals: Identity verification, originality proof, DRM, watermarking, transcoding.

## 1. File Extension
- Container file extension: `.aifv`

## 2. Container Format
- `.aifv` MUST be a ZIP container.
- The container MUST NOT contain symlinks.
- The container MUST NOT contain paths that escape the container root (no `../`, no absolute paths).
- The container MUST NOT reference remote resources (no URLs required to render or validate).

## 3. Required Top-Level Structure
AIFV v0 MUST contain:

- `manifest.json`
- `assets/`
  - one primary video file (see 4.1)
  - `thumb.jpg` (required embedded thumbnail)

Recommended (optional):
- `declaration.txt` (human-readable declaration text; manifest remains source of truth)

## 4. Assets Rules

### 4.1 Primary Video
- Exactly ONE primary video file MUST exist in `assets/`.
- Allowed filename pattern: `assets/video.*` (extension may vary).
- Validator MUST FAIL if:
  - zero primary videos exist
  - more than one primary video exists
- v0 does not mandate codecs/containers; converter MUST NOT transcode in v0.

### 4.2 Thumbnail
- `assets/thumb.jpg` is REQUIRED.
- Thumbnail MUST be embedded inside the `.aifv` (no sidecar `.aifi` in v0).
- Validator MUST FAIL if missing.

## 5. Manifest Requirements (manifest.json)

### 5.1 Required Fields (AIFX Core)
Manifest MUST include (minimum):

- `work.title` (string, non-empty)
- `creator.name` (string, non-empty)
- `creator.contact` (string, non-empty; email minimum)
- `mode` (string; e.g., "AI-Generated" / "AI-Assisted" – taxonomy is implementation-defined but must be non-empty)
- `ai_generated` (boolean; MUST be true for AIFV v0)
- `verification_tier` (string; MUST be "SDA")
- `declaration` (string, non-empty; human authorship statement)

### 5.2 Integrity / Hashes (Canonical AIFX)
- Manifest MUST include integrity metadata at `manifest.integrity`:

  - `integrity.algorithm`: MUST be `"sha256"`
  - `integrity.manifest_hash_mode`: MUST be `"canonical_excludes_self"`
  - `integrity.hashed_files`: object mapping `relpath -> { "sha256": "<hex>" }`

- `integrity.hashed_files` MUST include entries for:
  - the primary video file (e.g., `assets/video.mp4`)
  - `assets/thumb.jpg`
  - `manifest.json`

- Hash algorithm:
  - SHA-256 over the raw file bytes as stored in the container.

#### Canonical manifest hashing
When `integrity.manifest_hash_mode == "canonical_excludes_self"`:
- The `manifest.json` hash MUST be computed on the canonical JSON bytes of the manifest **excluding** the `integrity.hashed_files["manifest.json"]` entry to avoid circular dependency.

Validator behavior:
- MUST FAIL if integrity is missing, malformed, missing required hashes, or any hash mismatches.

### 5.3 Video Facts (Captured, Not Enforced)
Converter SHOULD capture video facts in manifest when available:
- duration
- resolution (width, height)
- fps
- container/codec metadata

Validator SHOULD treat these as informational (warnings only) unless v0.2+ promotes them to required/enforced.

## 6. Security Rules (Non-Negotiable)
Validator MUST FAIL if:
- any entry is a symlink
- any entry path is unsafe (absolute paths, `..`, drive roots, etc.)
- any required file missing
- more than one primary video
- integrity hash mismatch (tamper detected)
- manifest missing required identity/governance fields

## 7. Converter Stance (v0)
- Packaging-only.
- No transcoding.
- No network calls.
- Generates `manifest.json`, embeds thumbnail, computes hashes.
- Always sets `verification_tier` to "SDA".

## 8. Validator Output Contract
Validator MUST produce:
- explicit PASS/FAIL
- a checks map (rule -> boolean)
- errors list (deterministic messages)
- warnings list (non-fatal)
