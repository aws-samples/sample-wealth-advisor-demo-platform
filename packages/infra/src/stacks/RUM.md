# CloudWatch RUM (Real User Monitoring)

CloudWatch RUM captures real-time client-side telemetry from the Wealth Management Portal — page views, JavaScript errors, HTTP request performance, and Web Vitals — giving advisors and operators visibility into the actual end-user experience.

## What It Does

- **Error tracking** — captures unhandled exceptions and console errors with full stack traces
- **Performance monitoring** — collects Core Web Vitals (LCP, FID, CLS), page load times, and resource timing
- **HTTP telemetry** — records API call latency, status codes, and failure rates for every fetch/XHR request
- **Session replay context** — correlates events to user sessions with optional X-Ray trace propagation
- **Page view analytics** — tracks navigation patterns across the portal (dashboard, client details, search, etc.)

## Architecture

```
Browser (aws-rum-web SDK)
  │
  ├─ Collects telemetry events (errors, performance, HTTP, page views)
  ├─ Obtains temporary credentials via Cognito Identity Pool (unauthenticated)
  └─ Dispatches batched events to CloudWatch RUM dataplane
       │
       └─ CloudWatch RUM App Monitor
            ├─ Dashboard (latency, errors, sessions, Web Vitals)
            └─ Optional: CloudWatch Logs for raw event storage
```

## How It's Configured

RUM is fully automated through CDK — no manual setup required.

### Infrastructure (CDK)

The `ApplicationStack` provisions three resources:

1. **RUM App Monitor** (`CfnAppMonitor`) — configured with the CloudFront domain, Cognito Identity Pool, and a guest IAM role for the RUM service
2. **RUM Guest Role** — IAM role assumed by the RUM service, granted `AmazonCloudWatchRUMFullAccess`
3. **Cognito Identity Pool** — allows unauthenticated (guest) identities so the browser SDK can obtain temporary credentials without requiring user login. The unauthenticated role is granted `rum:PutRumEvents` scoped to the app monitor

The app monitor ID, identity pool ID, and region are written to `runtime-config.json` (deployed to S3 alongside the UI bundle) so the browser SDK picks them up at load time.

### UI (Browser SDK)

The `aws-rum-web` SDK is initialized in `packages/ui/src/rum.ts`:

1. On page load, the app fetches `/runtime-config.json`
2. If `rumConfig` is present (contains `appMonitorId`, `identityPoolId`, `region`), the SDK initializes
3. Telemetry collection starts automatically — no per-page instrumentation needed
4. Page view tracking is wired to the TanStack Router `onLoad` event in `main.tsx`

For local development, RUM can be enabled by setting environment variables:

```
VITE_RUM_APP_MONITOR_ID=<from CloudWatch RUM console>
VITE_RUM_IDENTITY_POOL_ID=<from Cognito console>
VITE_RUM_REGION=<deployment region>
```

If none are set, RUM is silently skipped — it does not block the application.

## How It Helps

### For Operators
- Identify slow API endpoints impacting real users (not just synthetic tests)
- Detect JavaScript errors before users report them
- Monitor deployment impact on Core Web Vitals

### For Advisors / Product
- Understand which portal features are most used (page view frequency)
- Identify UX friction points (high error rates on specific pages)
- Track performance across different client browsers and devices

### For Developers
- Correlate frontend errors with backend traces via X-Ray integration
- Debug production issues with session-level event timelines
- Measure the real-world impact of performance optimizations

## Files

| File | Purpose |
|------|---------|
| `packages/infra/src/stacks/application-stack.ts` | Provisions RUM app monitor, guest role, and Cognito unauth grant |
| `packages/infra/src/stacks/rum-stack.ts` | Standalone RUM stack (alternative deployment) |
| `packages/common/constructs/src/core/user-identity.ts` | Cognito Identity Pool with unauthenticated access enabled |
| `packages/ui/src/rum.ts` | Browser SDK initialization and configuration |
| `packages/ui/src/main.tsx` | Page view tracking via router subscription |
