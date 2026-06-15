<!-- source_id: WIKI-resource-guidelines | type: wiki | title: Resource & Caching Guidelines -->
# Resource & Caching Guidelines

Last updated: 2026-01-20 by Priya Nair (SRE)

## In-memory caches
- **Every in-memory cache MUST be bounded** — a maximum entry count or a TTL (time-to-live),
  ideally both. An unbounded cache grows until the process runs out of memory and is **OOMKilled**.
- Use an eviction policy (LRU is the default). Do not back a cache with a plain map/dict that only
  ever grows.
- Caches holding per-request or per-item data (e.g. product lookups) are the most common offenders,
  because the key space is effectively unbounded.

## Memory budgets
- Each service pod has a memory limit. A steadily climbing memory graph after a deploy almost always
  means a new allocation that is never freed (an unbounded cache, a leak, or a growing buffer).
- When diagnosing OOMKills, **correlate the start of the memory climb with the most recent deploy**
  and inspect what that deploy changed.

## Why
- OOMKilled pods restart, dropping in-flight work and causing error spikes. On a Tier-1 service this
  is a customer-facing outage.
