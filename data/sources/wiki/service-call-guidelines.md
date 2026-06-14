<!-- source_id: WIKI-service-calls | type: wiki | title: Service Call Guidelines (Hot Path) -->
# Service Call Guidelines (Hot Path)

Last updated: 2026-04-02 by Elena Rodriguez (Payments)

## The hot-path rule
- Any call to an external or dependent service **inside a request hot path** (checkout, payment
  authorization, login) **MUST** be either:
  1. **asynchronous** (fire-and-forget or queued), or
  2. **synchronous with a strict timeout (<200ms) AND a fallback** path.
- **Never block the payment authorization path on a non-critical service.** Fraud scoring,
  analytics, and notifications are non-critical to authorizing a payment and must not be able to
  add latency to it.

## Timeouts & fallbacks
- Default client timeout for hot-path calls: **150ms**.
- On timeout, log + emit a metric + take the fallback (e.g. allow the payment and flag for async
  review). Failing open vs. closed is a per-call decision documented in the service README.

## Why
- The payment path's latency budget is **300ms p99**. A single uncapped downstream call can blow
  the entire budget when that dependency is slow under load.
