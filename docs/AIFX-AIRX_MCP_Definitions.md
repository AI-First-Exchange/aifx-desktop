First 6 MCP tools (AIFX + aiRX)
These are designed to give you immediate operational leverage without exposing any “write/publish/approve” powers yet.
1) aifx.validate_package
Goal: Dry-run validation of an AIFM/AIFX package (verdict + reasons) Args
	•	package_path: str (local path)
	•	profile: str = "airx_radio" (which rule profile to apply) Returns
	•	verdict: "PASS"|"FAIL"|"WARN"
	•	reasons: list[str]
	•	checks: dict (per-check status + notes)
Tier: Owner + Internal AI (read-only)

2) aifx.inspect_manifest
Goal: Parse + normalize manifest, surface warnings, show key fields Args
	•	package_path: str Returns
	•	manifest: dict
	•	warnings: list[str]
Tier: Owner + Internal AI (read-only)

3) aifx.verify_checksums
Goal: Verify checksums (manifest vs actual) and/or compute file hashes Args
	•	package_path: str Returns
	•	ok: bool
	•	files: list[{path, expected, actual, match}]
Tier: Owner + Internal AI (read-only)

4) airx.now_playing
Goal: Get current track metadata (what’s live right now) Args
	•	none (optional later: source="icecast|jsonfile|http") Returns
	•	track: dict (title/artist/album/id/timestamps if available)
Tier: Owner + Internal AI (read-only)

5) airx.ingest_status
Goal: Operational snapshot of pipeline (counts in inbox/quarantine/accepted) Args
	•	none Returns
	•	paths: dict
	•	counts: dict
	•	recent: dict (optional small sample)
Tier: Owner + Internal AI (read-only)

6) airx.quarantine_list
Goal: List quarantined submissions + reasons (for triage) Args
	•	limit: int = 25 Returns
	•	items: list[{id, filename, reason, ts}]
Tier: Owner + Internal AI (read-only)
