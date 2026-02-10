# AIFX / aiRX MCP Access Policy (v0.1)

## Purpose
MCP tools provide a controlled interface for agents/clients to query AIFX provenance validation and aiRX station state.

## Trust Boundaries
- **AIFX repo** (`~/Desktop/Projects/AIFX-local/aifx`): source code + validators.
- **aiRX runtime** (`~/airx`): ingestion queues, quarantine records, nowplaying, logs.
- MCP server is the contract layer. Clients NEVER read filesystem directly.

## Tiers
### Tier 1 — Read-only + Dry-run (default)
Allowed:
- Read manifests
- Verify checksums
- Inspect ingestion queues
- Read now playing
Disallowed:
- Moving files between queues
- Approving/releasing content
- Deleting anything
- Editing metadata
- Network calls

Tools in Tier 1:
- aifx.validate_package
- aifx.inspect_manifest
- aifx.verify_checksums
- airx.now_playing
- airx.ingest_status
- airx.quarantine_list

### Tier 2 — Controlled mutation (future)
Only after human approval and audit hardening.
Examples:
- airx.quarantine_release (move item quarantine → inbox/accepted)
- airx.quarantine_reject (quarantine → rejected)
- airx.set_now_playing (write nowplaying.json)

### Tier 3 — Admin / destructive (future)
Requires multi-factor gating + explicit human-in-the-loop:
- delete quarantine items
- purge queues
- rotate keys
- modify policies

## Who can access MCP and why
### Local Developer (You: JaiSimon1)
- Full Tier 1 access.
- Tier 2 tools only when developing ingestion/review UI.

### Internal AI Agents (Zeek-assisted workflows)
- Tier 1 only.
- Purpose: diagnostics, status reporting, validation dry-runs, generating reports.

### Future External Tools / Community
- Tier 1 subset only (read-only) via hosted MCP gateway.
- No filesystem paths returned; only logical IDs.

## Audit Requirements
- All tool calls are appended to MCP_AUDIT_LOG.
- For Tier 2+, audit must include:
  - request id
  - actor identity
  - human approval flag (true/false)
  - before/after state hash

## Secrets & Config
- `.env` is local-only and never committed.
- Production config via secure secrets store (later).

## Non-negotiables
- No generated output enters aiRX broadcast unless it passes the same ingestion checks and is re-wrapped into AIFM.
- Tier 2+ operations must be reversible or quarantined.

