<!-- source_id: WIKI-migrations | type: wiki | title: Database Migration Guidelines -->
# Database Migration Guidelines

Last updated: 2026-02-11 by Aisha Khan (Platform)

These rules are **mandatory** for any migration touching a production database.

## Index creation
- **All index creation on large tables MUST use `CREATE INDEX CONCURRENTLY`.** A plain
  `CREATE INDEX` takes an `ACCESS EXCLUSIVE`-style lock that blocks writes for the entire build,
  which on a hot table will stall the service.
- "Large table" = any table over **1 million rows**. Currently: `orders`, `payments`, `users`,
  `order_tags`.
- `CREATE INDEX CONCURRENTLY` cannot run inside a transaction block — run it as a standalone
  migration step.

## Deploys
- Migrations run **during** the deploy, before the new app version takes traffic. A migration that
  locks a hot table therefore stalls live traffic. Treat any migration on a Tier-1 table as a
  potential outage and review it for locking.
- Always estimate migration duration on a staging copy of production-sized data.

## Rollback
- Every migration must ship with a reverse migration.
- If a deploy causes elevated error rates on a Tier-1 service, the on-call **rolls back first,
  investigates second**.
