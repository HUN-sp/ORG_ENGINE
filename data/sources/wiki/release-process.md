<!-- source_id: WIKI-release-process | type: wiki | title: Release & Deploy Process -->
# Release & Deploy Process

Last updated: 2026-03-15 by Priya Nair (SRE)

## Release cadence
- Minor releases (e.g. v4.2.0 → v4.3.0) ship roughly every two weeks on a **Wednesday**.
- Patch releases (e.g. v4.2.0 → v4.2.1) ship as needed.

## Pipeline stages
1. Merge to `main` → CI runs unit + integration tests.
2. Tag a release candidate → deploy to **staging**.
3. Run smoke + load tests on staging.
4. **Production deploy**: run DB migrations → roll out new app version → health checks → done.
5. If health checks fail or error rate exceeds **5%** on a Tier-1 service, the deploy auto-pauses
   and pages on-call.

## Blocking a release
- A release is **blocked** if any P1 ticket is open against the release epic, or if integration
  tests are flaky/failing on a Tier-1 service.
- The release epic ticket (e.g. NW-1150 for v4.3.0) lists blockers in its "Blocked by" field.

## Roll back
- On-call rolls back to the previous tag first, then opens an incident postmortem ticket.
