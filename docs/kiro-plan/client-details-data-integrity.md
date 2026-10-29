# Client Details Data Integrity Fixes

## Background

The client details page (`/clients/CL00001`) renders two empty panels: **Target Asset Allocation** ("No allocation data available") and **Portfolio Market Themes** (blank). Commit `79b8c15` was intended to fix both, but the panels are still empty.

Investigation found three independent problems. Only the first is fixed by the existing commit; the other two are unfixed and one of them cannot be fixed by application code at all.

### Issue 1: The API Lambda is running pre-fix code

Commit `79b8c15` fixed both Athena incompatibilities correctly, but was never deployed. `ApiRouterHandler` was last modified `2026-08-06T08:10:42Z`; the commit landed at `11:50Z`.

Invoking the deployed `ApiRouterHandler` directly for `CL00001` returns:

```
/clients/{id}/asset-allocation
  SCHEMA_NOT_FOUND: line 1:31: Schema 'default' does not exist

/clients/{id}/themes
  TYPE_MISMATCH: line 8:60: Cannot apply operator: timestamp(6) <= varchar(26)
```

Both are the old code paths. `advisor_master` is not in `_qualify_tables`, so it stays unqualified and resolves to schema `default`. The `varchar(26)` is the length of `isoformat()`; the fix uses a 19-char `strftime` plus a `TIMESTAMP` cast.

The new allocation SQL was verified against Athena and does return data:

```
PF000076  CL00001  30% Equity, 60% Fixed Income, 10% Alternatives
```

This issue needs a deploy, not a code change.

### Issue 2: Glue CSV loader corrupts seed data (the reason themes stay broken)

`load_data_to_s3table.py:45` reads every seed CSV with Spark defaults:

```python
source_df = spark.read.csv(SOURCE_PATH, header=True, inferSchema=False)
```

No `quote`, `escape`, or `multiLine` options. The seed CSVs use RFC 4180 doubled-quote escaping (`themes.csv` alone contains 87,056 `""` sequences) and some contain newlines inside quoted fields. Spark's defaults mis-handle both, producing two distinct corruption modes:

**Field shifting** (`themes`) — row count matches the CSV exactly (5,850), so rows are not split; values slide leftward into later columns. Of 5,856 rows, only **8 have a valid ticker**. The `ticker` column holds fragments of `score_breakdown`:

```
ticker = ' ""recency_score"": 19.81'
ticker = ' ""keyword_score"": 0.0}"'
```

Reproduced exactly: splitting the raw line on commas and zipping against the header yields the same wrong values the table contains, confirming quote-unaware parsing.

**Row splitting** (`articles`) — `articles.csv` has 2,537 logical rows across 3,313 physical lines. The table contains **3,250 rows**, so quoted newlines are being treated as record terminators.

The source CSVs are clean. A correct parser reads `themes.csv` as 5,850 rows × 18 columns with 5,579 valid tickers.

This affects **every table loaded by this job**, not just themes. Tables whose text fields contain no commas, quotes, or newlines (`clients`, `securities`, `research`, `client_reports`) happen to survive.

Runtime-written theme rows are unaffected — the 6 rows newer than the seed load are well-formed. Corruption is entirely from the Glue load.

### Issue 3: Parameter sanitizer strips colons from timestamps

`athena_base_repository.py:46`:

```python
safe_value = re.sub(r"[^\w\s\-._]", "", value)
# '2026-08-05 22:34:39' -> '2026-08-05 223439'
```

Athena rejects the result: `INVALID_LITERAL: '2026-08-05 223439' is not a valid TIMESTAMP literal`.

The themes path uses a *different* sanitizer in `common_market_events/redshift.py:53` whose allowlist includes `:`, so themes are unaffected today. This is a latent bug: any timestamp parameter passed through `portfolio_data_access` will be silently corrupted. The two divergent sanitizers are themselves the underlying problem.

## Fixes

### Fix 1: Make the Glue loader quote- and newline-aware

In `load_data_to_s3table.py`, read CSVs with explicit RFC 4180 options:

```python
source_df = spark.read.csv(
    SOURCE_PATH,
    header=True,
    inferSchema=False,
    quote='"',
    escape='"',
    multiLine=True,
)
```

`escape='"'` handles doubled-quote escaping; `multiLine=True` handles newlines inside quoted fields.

Note `multiLine=True` disables input splitting, so each CSV is read by a single task. Acceptable here — the largest seed file is ~6.6 MB.

### Fix 2: Add a load-time row-count assertion

The corruption ran undetected because the job reports success regardless of parse quality. After reading the source, compare the parsed row count against the expected count and fail loudly on mismatch rather than silently inserting garbage.

Cheapest reliable signal: the job already computes `row_count`. Add a `--EXPECTED_ROWS` argument (or a sidecar manifest of per-table counts) and fail the job when the parsed count differs. This turns a silent data-quality failure into a deploy-time error.

### Fix 3: Unify the two Athena parameter sanitizers

Two independent implementations of the same logic have already diverged and caused one live bug:

| Location | Allowlist |
|---|---|
| `athena_base_repository.py:46` | `[^\w\s\-._]` — strips `:` |
| `common_market_events/redshift.py:53` | `[^\w\s\-._:/+]` — keeps `:` |

Add `:` to the `athena_base_repository` allowlist to fix the immediate defect, then extract a single shared helper so both call sites use one implementation.

Note both sanitizers build SQL by string interpolation. Stripping characters is a fragile substitute for real parameter binding; Athena supports proper parameterized queries via `ExecutionParameters`. Migrating to real binding is the correct long-term fix and is called out as follow-up rather than folded into this change.

### Fix 4: Reload the corrupted tables

Code fixes alone leave the bad rows in place. After Fix 1 lands, re-upload the Glue script and re-run the load jobs. The job already does `DELETE FROM` before insert, so a re-run replaces the corrupt rows.

The 6 runtime-written theme rows are newer than the seed data and would be deleted by the reload. They are regenerable general themes, so this is acceptable — but worth confirming before running.

Also fix the duplicated upload path while here: `deploy-s3tables-data.sh:63` uploads to `s3://BUCKET/financial_advisor/`, while Terraform (`bucket.tf:19-21`) uploads to the bucket root and the Glue job reads `SOURCE_PATH = s3://BUCKET/{table}.csv` (root). The script's copy is written to a prefix the job never reads — two sources of truth, one of them dead.

## Expected outcome after all fixes

| Panel | After deploy (Fix 1–3) | After reload (Fix 4) |
|---|---|---|
| Target Asset Allocation | Renders — data verified present | unchanged |
| Portfolio Market Themes | Still wrong | Renders |

Two caveats on themes that persist after the reload:

- **Staleness.** The newest portfolio theme is `2026-04-10`, well outside the handler's 48-hour window, so it falls back to the stale path and the UI shows its stale warning. Theme regeneration is a separate concern from this fix.
- **Failure mode changes shape.** The corrupt ticker strings are truthy, so `ClientDetails.tsx` will not skip them. Once the query stops erroring, an un-reloaded table renders garbage stock cards instead of an empty panel. Fix 4 is what actually resolves the panel — Fixes 1–3 alone make the failure more visible, not less.

## Issue 4: Page load takes 7–9 seconds (separate from correctness)

Distinct from the empty panels — this is why the data is *slow*, not why it is *wrong*. Measured against the deployed `ApiRouterHandler`:

| Endpoint | Cold | Warm |
|---|---|---|
| asset-allocation | 9.0s | 5.3s |
| themes | 8.4s | 6.9–8.3s |
| aum | 6.9s | — |
| holdings | 7.1s | — |
| transactions | 6.6s | — |

`ClientDetails.tsx:212-218` already fires these in parallel, so page load is gated by the slowest endpoint, not the sum.

### Root cause: memory-starved Lambda (fixed)

Every invocation reported:

```
Duration: 4175 ms   Memory Size: 128 MB   Max Memory Used: 127 MB
```

127 MB of 128 MB, consistently. Lambda scales CPU linearly with memory, so at 128 MB the function had roughly a tenth of a vCPU and was thrashing at its ceiling.

Decisive evidence: the *failing* allocation request still took 4.2s despite erroring out in Athena and doing almost no work — so that time was interpreter and boto3 overhead, not query time. The raw Athena query measured ~2.0s (1.7s engine + 0.3s planning). Of a 5.3s warm request, only ~2s was the query.

`api.ts` set no `memorySize`, so it silently inherited the 128 MB default while every other API construct in the repo already used 512 MB. Fixed by setting `memorySize: 512`, matching that convention.

### Remaining floor after the memory fix

- **~2s per Athena query.** Fixed planning/startup cost. Athena is a warehouse engine, not a low-latency store. Irreducible without caching or a different store.
- **Themes issues 2 queries serially** (`portfolio_themes_handler.py:79,86`), plus a third on the stale fallback — which is why it is the slowest endpoint.
- **Cold starts** add ~2–4s.

## Fix 5: Cache query results after initial load

Even with adequate CPU, the ~2s Athena floor applies to every request, and this data is near-static — seed tables change only on reload, and themes regenerate on a schedule (currently ~4 months stale). Re-querying Athena on every page view pays a warehouse-latency cost for data that has not changed.

Recommended approach, in ascending order of effort. Stages 1 and 2 are independently valuable; stop at whichever gives acceptable latency.

### Stage 1: Client-side caching via TanStack Query (cheapest, no infra)

The repo already depends on TanStack Query, and `reportQuery` in `ClientDetails.tsx:221` already uses it — but the six client-details fetches bypass it, using hand-rolled `useEffect` + `useState` instead. That means no caching, no deduplication, and a full refetch on every mount and revisit.

Migrate those six fetches to `useQuery` with a `staleTime` reflecting how static the data is (minutes for holdings/transactions, longer for allocation/themes). Benefits:

- Revisiting a client is served from cache — effectively instant.
- In-flight duplicate requests are deduplicated automatically.
- Removes ~120 lines of manual loading/error bookkeeping.

This does not help a first-ever cold load, but it eliminates repeat cost, which is the common navigation pattern.

### Stage 2: Server-side caching in the Lambda

Two complementary layers:

**Warm-container memoization.** Cache results in a module-level dict with a TTL. Trivial to add and genuinely effective for near-static reference data, but only helps while a container stays warm and is per-container, so hit rate degrades as concurrency spreads requests across containers. Best treated as an optimization, not the primary mechanism.

**Shared cache for cross-invocation hits.** For a cache that survives cold starts and is shared across containers, use DynamoDB with a TTL attribute keyed on `client_id` + endpoint. Preferred over ElastiCache here: no VPC requirement, no idle cost, and this access pattern is a simple keyed lookup. Read latency is single-digit milliseconds versus ~2s for Athena.

Because the underlying data changes only on a known event, prefer **explicit invalidation over short TTLs** — have the Glue reload and theme-generation jobs clear or bump affected cache entries. That allows a long TTL without serving stale data, which short TTLs cannot achieve.

### Stage 3: Precompute if latency is still unacceptable

If sub-second first-load is required, move from caching to precomputation: have the existing scheduled jobs write query-ready rows to DynamoDB, and have the API read only from there. This removes Athena from the request path entirely, at the cost of a materialization step. Only worth doing if Stage 1–2 latency proves insufficient — noted for completeness, not recommended up front.

### Sequencing note

Do not build caching until Fix 4 (the data reload) is done. Caching corrupt results just makes bad data harder to dislodge, and cache entries created before the reload would need invalidating anyway.

## Files Changed

| File | Change |
|------|--------|
| `packages/common/constructs/src/app/apis/api.ts` | **Done** — set `memorySize: 512` on `ApiRouterHandler` (was defaulting to 128 MB) |
| `data-platform/iac/roots/datalakes/financial-advisor-s3-glue-s3/load_data_to_s3table.py` | Add `quote`/`escape`/`multiLine` CSV options; add row-count assertion |
| `packages/portfolio_data_access/.../repositories/athena_base_repository.py` | Add `:` to sanitizer allowlist; use shared helper |
| `packages/common_market_events/.../redshift.py` | Use shared sanitizer helper |
| `scripts/deploy-s3tables-data.sh` | Fix upload path to match the prefix the Glue job reads |
| `data-platform/iac/.../glue.tf` | Pass `--EXPECTED_ROWS` (if manifest approach chosen) |
| `packages/ui/src/components/ClientDetails.tsx` | Stage 1 caching — migrate 6 manual fetches to `useQuery` |

## Operational steps (not code)

1. Deploy the API Lambda — resolves Target Asset Allocation and applies the memory fix.
2. Re-upload the Glue script and re-run load jobs for `themes` and `articles` (all tables preferred, since the bug was table-agnostic).
3. Re-verify ticker quality: `count_if(regexp_like(ticker,'^[A-Z]{1,5}$'))` should be ~5,579, not 8.
4. Re-time the endpoints after deploy to quantify the memory gain before investing in caching.

## Follow-up (out of scope)

- Migrate Athena calls to real `ExecutionParameters` binding instead of string interpolation.
- Add a data-quality check to CI so column-shift corruption cannot reach the table silently again.
- Investigate portfolio theme regeneration freshness (newest is ~4 months old).
- Audit other Lambdas for missing `memorySize` — `api.ts` silently inherited the 128 MB default while sibling constructs set 512 MB, so the same omission may exist elsewhere.
