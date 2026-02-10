Purpose:
Define clear ownership, boundaries, and scope for AIFX Suite v1.
Prevent scope creep, burnout, and coupling to aiRX.

1. AIFX Core — What It Owns
The AIFX Core is format-agnostic and policy-neutral.
It MUST handle:
	•	Manifest schema (shared across all AIFX formats)
	•	Hashing & integrity verification
	•	Packaging into AIFX containers
	•	Inspecting & validating AIFX files
	•	Clean export of original media
	•	Verification tiers (SDA / VC / PVA as labels, not enforcement)
It MUST NOT:
	•	Curate or distribute content
	•	Enforce moderation or policy
	•	Require accounts or login
	•	Act as DRM or detection tech
	•	Depend on aiRX services
	•	Generate AI content

2. Adapters — What They Own
Adapters are thin, format-specific translators.
Each adapter (AIFM, AIFI, AIFV, AIFP):
	•	Validates input media
	•	Extracts technical metadata
	•	Normalizes files into staging area
	•	Produces a format-specific manifest fragment
Adapters MUST:
	•	Be deterministic
	•	Fail early with clear errors
	•	Return structured results to the core
Adapters MUST NOT:
	•	Decide verification tier rules
	•	Perform signing or crypto
	•	Enforce policy
	•	Interpret authorship truth
	•	Know about aiRX

3. UI Layer — What It Owns
The UI is a human convenience layer, not logic.
UI MUST:
	•	Collect user input (creator name, tool used, mode, notes)
	•	Offer Simple Mode by default
	•	Hide advanced options unless requested
	•	Display inspection & verification results clearly
UI MUST NOT:
	•	Implement business logic
	•	Decide verification outcomes
	•	Modify manifest semantics
	•	Require technical knowledge (CLI, keys, config)

4. CLI — Role & Scope
The CLI is an engine interface, not the product.
CLI MUST:
	•	Expose core actions (pack, inspect, verify, export)
	•	Be callable by the desktop app (Tauri)
	•	Remain optional for end users
CLI MUST NOT:
	•	Be required for normal creators
	•	Leak internal complexity into UX

5. Relationship to aiRX
	•	aiRX consumes AIFX containers
	•	aiRX does not define AIFX rules
	•	aiRX is a reference deployment, not an authority
	•	AIFX must function fully without aiRX present
AIFX decisions cannot be blocked by aiRX needs.

6. V1 Explicitly OUT OF SCOPE
The following are NOT part of AIFX v1:
	•	Native mobile apps (iOS / Android)
	•	App store distribution
	•	Cloud accounts or sync
	•	Marketplaces
	•	DRM or watermarking
	•	AI generation tools
	•	Moderation systems
	•	Reputation or trust scores
	•	Cryptographic identity enforcement

7. Design Principles (Non-Negotiable)
	•	Offline-first
	•	Free to use
	•	Hardware-agnostic
	•	Platform-neutral
	•	Human-readable by default
	•	Optional adoption, never enforced

8. Success Definition for V1
AIFX v1 is successful if:
	•	A non-technical creator can package content without a terminal
	•	A third party can inspect & verify without special access
	•	aiRX can ingest AIFX files without custom logic
	•	Trust is earned through clarity, not enforcement
