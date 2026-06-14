<!-- source_id: WIKI-adr-orders-db | type: wiki | title: ADR-007 Orders Database: Postgres over DynamoDB -->
# ADR-007: Orders Database — Postgres over DynamoDB

Status: **Accepted** (2025-11-08) · Author: Aisha Khan · Reviewers: Marcus Chen, Elena Rodriguez

## Context
We needed a primary datastore for the `orders` domain (orders, line items, payments linkage). The
two finalists were **PostgreSQL** and **DynamoDB**.

## Decision
We chose **PostgreSQL**.

## Rationale
1. **Multi-item transactional integrity.** A single order writes an `orders` row plus N
   `order_items` plus a `payments` link atomically. We need real ACID transactions across these.
   At evaluation time DynamoDB's transaction support was limited (item/size caps) and awkward for
   this access pattern.
2. **Relational reporting.** Finance and analytics run ad-hoc relational joins (orders × items ×
   refunds). This is native in Postgres; in DynamoDB it would require a secondary analytics pipeline.
3. **Team familiarity.** Both Checkout and Payments teams already operate Postgres; no new on-call
   skill set required.

## Rejected: DynamoDB
- Pros considered: effortless horizontal scale, low ops overhead.
- Rejected because: weak multi-item transactional story for our pattern, and our write volume
  (~300 orders/sec peak) is comfortably within a single well-tuned Postgres primary + read replicas.

## Consequences
- We accept manual sharding/scaling work later if volume 10x's.
- The `orders` table is hot and large — see Database Migration Guidelines for the resulting
  constraints on indexing.
