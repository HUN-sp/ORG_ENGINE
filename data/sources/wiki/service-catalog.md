<!-- source_id: WIKI-service-catalog | type: wiki | title: Service Catalog & Ownership -->
# Service Catalog & Ownership

Last updated: 2026-05-20 by Priya Nair (SRE)

| Service | Language | Owner | Team | On-call | Tier |
|---|---|---|---|---|---|
| checkout-svc | Go | Marcus Chen | Checkout | Checkout rotation | Tier 1 (critical) |
| payments-gateway | Java | Elena Rodriguez | Payments | Payments rotation | Tier 1 (critical) |
| inventory-svc | Python | Sam Okoro | Catalog | Catalog rotation | Tier 2 |
| notification-worker | Python | Sam Okoro | Catalog | Catalog rotation | Tier 3 |
| auth-service | Node.js | Aisha Khan | Platform | Platform rotation | Tier 1 (critical) |

## Notes
- **Tier 1** services are in the checkout critical path. Any incident on a Tier 1 service pages the
  on-call SRE lead (currently **Priya Nair**) in addition to the service owner.
- For questions about **inventory sync** issues, contact **Sam Okoro** (Catalog team). The
  inventory-svc consumes the `stock-updates` Kafka topic; stuck syncs are usually consumer lag.
- The **orders database** (Postgres) is shared by checkout-svc and payments-gateway and is
  administered by the Platform team (**Aisha Khan**). See ADR-007 for why it's Postgres.
- Engineering Manager for all teams: **Tom Becker**.
