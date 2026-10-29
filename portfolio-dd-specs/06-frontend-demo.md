Now I have a thorough picture of the codebase. Let me write the full spec.

---

# Spec 06: Frontend & Demo Scenario — Portfolio Due Diligence

**Version:** 1.0  
**Date:** 2026-07-13  
**Stack:** React 19, TypeScript, TanStack Router (file-based), TanStack Query v5, Tailwind CSS 4, shadcn/ui new-york

---

## 1. Overview

This spec defines the three new routes, all supporting components, TypeScript interfaces, SSE event schema, mock data, and the complete 15-minute demo walkthrough for the Portfolio Due Diligence (Portfolio DD) feature.

The feature surfaces a multi-agent ODD/IDD workflow to an end user (a research analyst or compliance officer) through three views: a queue dashboard, a live review detail page, and a final report approval screen.

---

## 2. Route File Structure

```
packages/ui/src/routes/
  portfolio-dd/
    index.tsx                   # /portfolio-dd  — dashboard
    $reviewId/
      index.tsx                 # /portfolio-dd/$reviewId  — review detail
      report.tsx                # /portfolio-dd/$reviewId/report  — report viewer
  # existing routes unchanged
  clients/
    index.tsx
    $clientId.tsx
    $clientId/
      report.tsx
  graph-search.tsx
  index.tsx
  __root.tsx
```

TanStack Router will generate an updated `routeTree.gen.ts` automatically (via `@tanstack/router-vite-plugin`) on the next dev server start or build.

---

## 3. TypeScript Interfaces

### 3.1 Domain Types

```typescript
// packages/ui/src/types/portfolio-dd.ts

export type ReviewStatus =
  | 'queued'
  | 'in_progress'
  | 'awaiting_human'
  | 'generating_report'
  | 'complete'
  | 'rejected';

export type ReviewType = 'ODD' | 'IDD' | 'Annual_Review' | 'ESG_Screen';

export type CriteriaRating =
  | 'Pass'
  | 'Pass_With_Conditions'
  | 'Requires_Review'
  | 'Fail'
  | 'Pending';

export interface PortfolioReview {
  reviewId: string;
  portfolioName: string;
  portfolioId: string;
  managerName: string;
  reviewType: ReviewType;
  status: ReviewStatus;
  startedAt: string;         // ISO-8601
  completedAt?: string;
  progressPct: number;       // 0-100
  assignedTo?: string;
  hitlFlagCount: number;
  criteriaComplete: number;  // out of 12
}

export interface AssessmentCriterion {
  criterionId: string;
  name: string;
  category: 'Governance' | 'Operations' | 'Risk' | 'Performance' | 'ESG';
  rating: CriteriaRating;
  confidencePct: number;     // 0-100
  evidenceCount: number;
  summary?: string;
  humanOverride?: string;
  overriddenBy?: string;
  overriddenAt?: string;
}

export interface HitlFlag {
  flagId: string;
  reviewId: string;
  criterionId: string;
  criterionName: string;
  flagReason: string;
  riskLevel: 'high' | 'medium' | 'low';
  aiAssessment: string;
  evidenceExcerpts: EvidenceExcerpt[];
  status: 'pending' | 'accepted' | 'overridden' | 'escalated';
  resolvedBy?: string;
  resolvedAt?: string;
  resolutionNote?: string;
}

export interface EvidenceExcerpt {
  sourceId: string;
  sourceTitle: string;
  sourceDateIso: string;
  excerpt: string;
  pageRef?: string;
}

export interface AgentActivityEvent {
  eventId: string;
  agentName: string;
  eventType:
    | 'task_start'
    | 'tool_call'
    | 'tool_result'
    | 'criteria_assessed'
    | 'hitl_flag'
    | 'report_section'
    | 'complete';
  message: string;
  criterionId?: string;
  timestamp: string;
  durationMs?: number;
}

export interface DDReport {
  reviewId: string;
  generatedAt: string;
  approvalStatus: 'draft' | 'approved' | 'changes_requested' | 'rejected';
  markdownContent: string;
  citations: Citation[];
  approvedBy?: string;
  approverNote?: string;
  humanOverrides: HumanOverride[];
}

export interface Citation {
  citationId: string;         // matches [1], [2] in markdown
  sourceTitle: string;
  sourceType: 'DDQ' | 'Audited_Financials' | 'Regulatory_Filing' | 'News' | 'Internal_Note';
  excerpt: string;
  pageRef?: string;
  date: string;
}

export interface HumanOverride {
  criterionId: string;
  criterionName: string;
  aiRating: CriteriaRating;
  humanRating: CriteriaRating;
  rationale: string;
  overriddenBy: string;
}

export interface QueueMetrics {
  activeReviews: number;
  awaitingHuman: number;
  completedThisMonth: number;
  avgCompletionMinutes: number;
  manualEquivalentWeeks: number;  // for "time saved" display
}
```

### 3.2 API Response Envelopes

```typescript
// Extends the existing API pattern from packages/ui/src/hooks/useApi.tsx

export interface ListReviewsResponse {
  reviews: PortfolioReview[];
  total: number;
}

export interface ReviewDetailResponse {
  review: PortfolioReview;
  criteria: AssessmentCriterion[];
  hitlFlags: HitlFlag[];
  recentActivity: AgentActivityEvent[];
}

export interface StartReviewRequest {
  portfolioId: string;
  reviewType: ReviewType;
  requestedBy: string;
}

export interface StartReviewResponse {
  reviewId: string;
  status: ReviewStatus;
  estimatedMinutes: number;
}

export interface ResolveHitlFlagRequest {
  flagId: string;
  action: 'accept' | 'override';
  overrideRating?: CriteriaRating;
  note?: string;
}

export interface ApproveReportRequest {
  reviewId: string;
  action: 'approve' | 'request_changes' | 'reject';
  note?: string;
}
```

---

## 4. SSE Event Schema

The streaming endpoint is `GET /portfolio-dd/{reviewId}/stream` (or `POST` to AgentCore in production). The event format follows the existing pattern from `ImprovedChatWidget.tsx` exactly — `event:` line followed by `data:` JSON line.

### 4.1 Event Types

```
event: agent_start
data: { "agentName": "Supervisor", "task": "Decomposing ODD for AMP Growth Fund", "timestamp": "2026-07-13T10:00:01Z" }

event: agent_end
data: { "agentName": "Supervisor", "timestamp": "2026-07-13T10:00:02Z" }

event: tool_call
data: { "agentName": "EvidenceGatherer", "tool": "search_documents", "args": { "query": "AMP Growth Fund DDQ 2025", "criterionId": "crit-01" }, "timestamp": "..." }

event: tool_result
data: { "agentName": "EvidenceGatherer", "tool": "search_documents", "resultSummary": "Found 3 documents", "durationMs": 1240, "timestamp": "..." }

event: criteria_assessed
data: { "criterionId": "crit-01", "criterionName": "Ownership & Governance Structure", "rating": "Pass", "confidencePct": 92, "evidenceCount": 4, "summary": "Clear governance structure with independent board majority.", "timestamp": "..." }

event: hitl_flag
data: { "flagId": "flag-01", "criterionId": "crit-05", "criterionName": "Key Person Risk", "flagReason": "Portfolio manager accounts for >80% of assets under active management with no succession plan documented.", "riskLevel": "high", "timestamp": "..." }

event: progress
data: { "criteriaComplete": 7, "totalCriteria": 12, "progressPct": 58, "status": "in_progress", "timestamp": "..." }

event: report_start
data: { "message": "Generating executive summary...", "timestamp": "..." }

event: report_section
data: { "section": "Executive Summary", "progressPct": 80, "timestamp": "..." }

event: complete
data: { "reviewId": "rev-amp-001", "status": "complete", "progressPct": 100, "reportReady": true, "timestamp": "..." }

event: error
data: { "message": "Evidence retrieval failed for Regulatory Compliance criteria. Retrying...", "timestamp": "..." }
```

### 4.2 SSE Hook

```typescript
// packages/ui/src/hooks/useReviewStream.ts

import { useEffect, useRef, useCallback } from 'react';
import { AgentActivityEvent } from '../types/portfolio-dd';

interface UseReviewStreamOptions {
  reviewId: string;
  apiUrl: string;
  accessToken?: string;
  enabled: boolean;
  onEvent: (event: AgentActivityEvent) => void;
  onComplete: () => void;
}

export function useReviewStream({
  reviewId,
  apiUrl,
  accessToken,
  enabled,
  onEvent,
  onComplete,
}: UseReviewStreamOptions): { isStreaming: boolean; error: string | null } {
  // Implementation mirrors ImprovedChatWidget SSE reader pattern:
  // fetch() with response.body.getReader(), line-by-line parsing of
  // "event: <type>\ndata: <json>" blocks.
  //
  // See packages/ui/src/components/ImprovedChatWidget.tsx lines 582-658
  // for the canonical pattern to replicate here.
}
```

---

## 5. Route Implementations

### 5.1 `/portfolio-dd` — Dashboard Route File

**File:** `packages/ui/src/routes/portfolio-dd/index.tsx`

```typescript
import { createFileRoute } from '@tanstack/react-router';
import { DDDashboard } from '../../components/PortfolioDD/DDDashboard';

export const Route = createFileRoute('/portfolio-dd')({
  component: DDDashboard,
});
```

### 5.2 `/portfolio-dd/$reviewId` — Review Detail Route File

**File:** `packages/ui/src/routes/portfolio-dd/$reviewId/index.tsx`

```typescript
import { createFileRoute } from '@tanstack/react-router';
import { ReviewDetail } from '../../../components/PortfolioDD/ReviewDetail';

export const Route = createFileRoute('/portfolio-dd/$reviewId/')({
  component: ReviewDetail,
});
```

### 5.3 `/portfolio-dd/$reviewId/report` — Report Viewer Route File

**File:** `packages/ui/src/routes/portfolio-dd/$reviewId/report.tsx`

```typescript
import { createFileRoute } from '@tanstack/react-router';
import { ReportViewer } from '../../../../components/PortfolioDD/ReportViewer';

export const Route = createFileRoute('/portfolio-dd/$reviewId/report')({
  component: ReportViewer,
});
```

---

## 6. Component Hierarchy

```
src/components/PortfolioDD/
  index.ts                          # barrel export

  DDDashboard.tsx                   # route component for /portfolio-dd
    QueueMetricsRow.tsx             # 4-stat tiles
    PortfolioTable.tsx              # sortable reviews table
    StartReviewModal.tsx            # Dialog + Select + Button

  ReviewDetail.tsx                  # route component for /portfolio-dd/$reviewId
    ReviewStatusHeader.tsx          # breadcrumb, status badge, progress %
    AssessmentMatrix.tsx            # left panel — 12-criteria table
      CriterionRow.tsx              # rating Badge + confidence Progress + evidence count
    AgentActivityFeed.tsx           # right panel — live SSE event log
      ActivityEventCard.tsx         # single event row
    HitlFlagsPanel.tsx              # bottom panel — expandable flag cards
      HitlFlagCard.tsx              # evidence accordion + accept/override controls

  ReportViewer.tsx                  # route component for /portfolio-dd/$reviewId/report
    ReportMarkdown.tsx              # ReactMarkdown + citation tooltip injection
    CitationTooltip.tsx             # Tooltip wrapping [n] reference spans
    ApprovalToolbar.tsx             # sticky bottom bar — approve/reject/changes
    OverrideDiffPanel.tsx           # side-by-side diff for human overrides
```

---

## 7. UI Components Specification

### 7.1 DDDashboard (`/portfolio-dd`)

#### QueueMetricsRow

Four `Card` components (shadcn/ui `Card`, `CardContent`) in a responsive 4-column grid.

| Metric | Value | shadcn component |
|---|---|---|
| Active Reviews | count badge | `Card` + large text |
| Awaiting Human Review | count with amber dot | `Card` + `Badge` variant `warning` |
| Completed This Month | count | `Card` |
| Time Saved Est. | "X weeks" | `Card` + green text |

```
<div className="grid grid-cols-4 gap-4 mb-6">
  <MetricCard label="Active Reviews" value={metrics.activeReviews} />
  <MetricCard label="Awaiting Human Review" value={metrics.awaitingHuman} accent="amber" />
  <MetricCard label="Completed This Month" value={metrics.completedThisMonth} />
  <MetricCard label="Time Saved Est." value={`${metrics.manualEquivalentWeeks}w`} accent="green" />
</div>
```

#### PortfolioTable

shadcn/ui `Table`, `TableHeader`, `TableRow`, `TableHead`, `TableBody`, `TableCell`.

Columns:

| Column | Content | Notes |
|---|---|---|
| Portfolio | Bold name + portfolio ID in muted text | `Link` to `/$reviewId` |
| Manager | Manager name | Plain text |
| Review Type | `Badge` (ODD = blue, IDD = purple, Annual = gray, ESG = green) | shadcn `Badge` |
| Status | Colored `Badge` | see status badge map below |
| Started | Relative time (e.g., "2 hours ago") | `date-fns` `formatDistanceToNow` |
| Progress | shadcn/ui `Progress` component (0-100) | Only shown for in_progress |
| Action | `Button` variant `ghost` or `Link` | "View" or "Review" |

Status badge color map:
- `queued` → secondary/gray
- `in_progress` → blue (default)
- `awaiting_human` → amber/warning
- `generating_report` → purple
- `complete` → green (success)
- `rejected` → red (destructive)

#### StartReviewModal

`Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter`.

Inside: a `Select` for portfolio (searchable via `Combobox` pattern from shadcn/ui), a `Select` for review type, a `Button` to trigger the API call. On success navigate to `/portfolio-dd/$newReviewId`.

---

### 7.2 ReviewDetail (`/portfolio-dd/$reviewId`)

#### ReviewStatusHeader

- Breadcrumb: `PortfolioDD > AMP Growth Fund > ODD Review`
- Portfolio name (h1), manager name, review type `Badge`
- Overall progress bar (full-width `Progress`) with percentage label
- Status `Badge` (large)

#### AssessmentMatrix (Left Panel — 60% width)

shadcn/ui `Table` with 12 fixed rows, one per criterion. Rows populate as SSE `criteria_assessed` events arrive — previously-pending rows show skeleton animation via `Skeleton` component.

Columns:

| Column | Content | shadcn component |
|---|---|---|
| # | Criterion number | muted text |
| Criterion | Name + category label | bold name, `Badge` for category |
| Rating | Color-coded `Badge` | Pass=green, PassWithConditions=yellow, RequiresReview=amber, Fail=red, Pending=gray |
| Confidence | Thin `Progress` bar + percentage | `Progress` h-1.5 |
| Evidence | Count pill | `Badge` variant outline |
| Override | Pencil icon if human-overridden | `Button` icon ghost |

#### AgentActivityFeed (Right Panel — 40% width)

Scrollable div (`overflow-y-auto`, max-height fills viewport) with events appended at bottom as SSE arrives. Auto-scroll behavior mirrors `messagesEndRef` pattern from `ImprovedChatWidget.tsx`.

Each `ActivityEventCard` shows:
- Colored left border per event type (agent_start=indigo, tool_call=blue, criteria_assessed=green, hitl_flag=red, complete=emerald)
- Agent name (`Badge` outline small)
- Message text
- Relative timestamp

A "Live" indicator dot (pulsing red `animate-pulse` circle) in the panel header while `isStreaming` is true.

#### HitlFlagsPanel (Bottom Panel, collapsible)

`Collapsible` (shadcn/ui) with header showing count badge. Inside: a vertical list of `HitlFlagCard` components.

Each `HitlFlagCard`:
- `Card` with left border color per risk level (high=red, medium=amber, low=yellow)
- Header: criterion name, risk level `Badge`, flag reason summary
- Expandable accordion (`Collapsible` nested) with:
  - Evidence excerpts (blockquote-style divs with source title + date)
  - AI assessment text in muted italic
- Footer actions (status `pending` only):
  - `Button` default "Accept AI Assessment"
  - `Button` variant `outline` "Override..." → opens inline form with `Select` for new rating + `Textarea` for rationale

---

### 7.3 ReportViewer (`/portfolio-dd/$reviewId/report`)

#### ReportMarkdown

Uses the existing `ReactMarkdown` + `remarkGfm` pattern (identical to `ImprovedChatWidget.tsx` lines 997-1090). Add one additional custom component for citation injection:

The citation regex `\[(\d+)\]` is matched inside text nodes before rendering. Each match is replaced with a `CitationTooltip` wrapping the `[n]` span.

#### CitationTooltip

`TooltipProvider`, `Tooltip`, `TooltipTrigger`, `TooltipContent` (shadcn/ui). The trigger is the `[n]` superscript span. The content shows:

```
Source: {citation.sourceTitle}
Type: {citation.sourceType}
Date: {citation.date}
---
"{citation.excerpt}"
{citation.pageRef && `Page: ${citation.pageRef}`}
```

#### ApprovalToolbar

Sticky bottom bar (`sticky bottom-0 bg-white border-t`):

Left side: download button (`Button` variant `outline` with printer icon, calls `window.print()`).

Right side (three buttons):
- `Button` variant `destructive` — "Reject" → opens inline confirmation with `Textarea` for note
- `Button` variant `outline` — "Request Changes" → opens `Textarea` for note inline
- `Button` default — "Approve Report" → shows confirmation `AlertDialog`

On approval action: `POST /portfolio-dd/{reviewId}/report/approve` via mutation. On success navigate back to `/portfolio-dd/$reviewId`.

#### OverrideDiffPanel

Shown only if `report.humanOverrides.length > 0`. A collapsible `Card` at the top of the report page listing each override as a two-column side-by-side:
- Left column (red background muted): AI rating + reasoning
- Right column (green background muted): Human rating + rationale + overridden-by name

---

## 8. TanStack Query Integration

```typescript
// packages/ui/src/hooks/usePortfolioDD.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type {
  ListReviewsResponse,
  ReviewDetailResponse,
  QueueMetrics,
  DDReport,
  StartReviewRequest,
  StartReviewResponse,
  ResolveHitlFlagRequest,
  ApproveReportRequest,
} from '../types/portfolio-dd';

// Query keys
export const ddKeys = {
  all: ['portfolio-dd'] as const,
  metrics: () => [...ddKeys.all, 'metrics'] as const,
  reviews: () => [...ddKeys.all, 'reviews'] as const,
  review: (id: string) => [...ddKeys.all, 'review', id] as const,
  report: (id: string) => [...ddKeys.all, 'report', id] as const,
};

// Queue metrics (poll every 30s on dashboard)
export function useQueueMetrics(apiUrl: string) {
  return useQuery<QueueMetrics>({
    queryKey: ddKeys.metrics(),
    queryFn: () => fetch(`${apiUrl}/portfolio-dd/metrics`).then(r => r.json()),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

// Reviews list (poll every 15s)
export function useReviews(apiUrl: string) {
  return useQuery<ListReviewsResponse>({
    queryKey: ddKeys.reviews(),
    queryFn: () => fetch(`${apiUrl}/portfolio-dd/reviews`).then(r => r.json()),
    refetchInterval: 15_000,
  });
}

// Review detail (poll every 5s while in_progress or awaiting_human)
export function useReviewDetail(apiUrl: string, reviewId: string) {
  return useQuery<ReviewDetailResponse>({
    queryKey: ddKeys.review(reviewId),
    queryFn: () =>
      fetch(`${apiUrl}/portfolio-dd/reviews/${reviewId}`).then(r => r.json()),
    refetchInterval: (query) => {
      const status = query.state.data?.review?.status;
      if (status === 'in_progress' || status === 'awaiting_human') return 5_000;
      if (status === 'generating_report') return 3_000;
      return false;
    },
  });
}

// Report
export function useDDReport(apiUrl: string, reviewId: string) {
  return useQuery<DDReport>({
    queryKey: ddKeys.report(reviewId),
    queryFn: () =>
      fetch(`${apiUrl}/portfolio-dd/reviews/${reviewId}/report`).then(r => r.json()),
  });
}

// Mutations
export function useStartReview(apiUrl: string) {
  const qc = useQueryClient();
  return useMutation<StartReviewResponse, Error, StartReviewRequest>({
    mutationFn: (req) =>
      fetch(`${apiUrl}/portfolio-dd/reviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      }).then(r => r.json()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ddKeys.reviews() });
      qc.invalidateQueries({ queryKey: ddKeys.metrics() });
    },
  });
}

export function useResolveHitlFlag(apiUrl: string, reviewId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, ResolveHitlFlagRequest>({
    mutationFn: (req) =>
      fetch(`${apiUrl}/portfolio-dd/reviews/${reviewId}/flags/${req.flagId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      }).then(r => r.json()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ddKeys.review(reviewId) });
    },
  });
}

export function useApproveReport(apiUrl: string, reviewId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, ApproveReportRequest>({
    mutationFn: (req) =>
      fetch(`${apiUrl}/portfolio-dd/reviews/${reviewId}/report/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      }).then(r => r.json()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ddKeys.review(reviewId) });
      qc.invalidateQueries({ queryKey: ddKeys.report(reviewId) });
      qc.invalidateQueries({ queryKey: ddKeys.metrics() });
    },
  });
}
```

---

## 9. Mock Data for Demo

```typescript
// packages/ui/src/components/PortfolioDD/__mocks__/mockData.ts

import type {
  PortfolioReview,
  QueueMetrics,
  AssessmentCriterion,
  HitlFlag,
  AgentActivityEvent,
  DDReport,
} from '../../../types/portfolio-dd';

export const MOCK_METRICS: QueueMetrics = {
  activeReviews: 3,
  awaitingHuman: 1,
  completedThisMonth: 14,
  avgCompletionMinutes: 12,
  manualEquivalentWeeks: 8,
};

export const MOCK_REVIEWS: PortfolioReview[] = [
  {
    reviewId: 'rev-amp-001',
    portfolioName: 'AMP Growth Fund',
    portfolioId: 'AMP-GF-2024',
    managerName: 'Meridian Capital Partners',
    reviewType: 'ODD',
    status: 'in_progress',
    startedAt: new Date(Date.now() - 7 * 60 * 1000).toISOString(),
    progressPct: 58,
    hitlFlagCount: 0,
    criteriaComplete: 7,
  },
  {
    reviewId: 'rev-bri-002',
    portfolioName: 'Bridgewater Core Alpha',
    portfolioId: 'BWC-ALPHA-23',
    managerName: 'Bridgewater Associates',
    reviewType: 'Annual_Review',
    status: 'awaiting_human',
    startedAt: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    progressPct: 92,
    hitlFlagCount: 2,
    criteriaComplete: 11,
  },
  {
    reviewId: 'rev-hg-003',
    portfolioName: 'HG Emerging Markets',
    portfolioId: 'HG-EM-2025',
    managerName: 'Hillhouse Capital',
    reviewType: 'IDD',
    status: 'complete',
    startedAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    completedAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000 + 11 * 60 * 1000).toISOString(),
    progressPct: 100,
    hitlFlagCount: 0,
    criteriaComplete: 12,
  },
  {
    reviewId: 'rev-cg-004',
    portfolioName: 'Canyon Value Fund III',
    portfolioId: 'CANY-V3-2024',
    managerName: 'Canyon Capital Advisors',
    reviewType: 'ESG_Screen',
    status: 'queued',
    startedAt: new Date().toISOString(),
    progressPct: 0,
    hitlFlagCount: 0,
    criteriaComplete: 0,
  },
];

export const MOCK_CRITERIA: AssessmentCriterion[] = [
  { criterionId: 'crit-01', name: 'Ownership & Governance Structure', category: 'Governance', rating: 'Pass', confidencePct: 94, evidenceCount: 5, summary: 'Clear structure with independent board majority and documented succession plan.' },
  { criterionId: 'crit-02', name: 'Regulatory Compliance & Licensing', category: 'Governance', rating: 'Pass', confidencePct: 98, evidenceCount: 3, summary: 'Fully registered with SEC and FINRA. No open enforcement actions.' },
  { criterionId: 'crit-03', name: 'AUM & Asset Flows', category: 'Operations', rating: 'Pass_With_Conditions', confidencePct: 81, evidenceCount: 4, summary: 'AUM grew 22% YoY. Notable concentration in top 3 institutional clients (68% of AUM).' },
  { criterionId: 'crit-04', name: 'Investment Process & Mandate Adherence', category: 'Performance', rating: 'Pass', confidencePct: 91, evidenceCount: 6, summary: 'Strategy consistently applied. No material style drift detected over 5-year window.' },
  { criterionId: 'crit-05', name: 'Key Person Risk', category: 'Risk', rating: 'Requires_Review', confidencePct: 67, evidenceCount: 2, summary: 'Lead PM accounts for >80% of active portfolio decisions. No succession plan documented.' },
  { criterionId: 'crit-06', name: 'Operational Infrastructure & Technology', category: 'Operations', rating: 'Pass', confidencePct: 89, evidenceCount: 3, summary: 'Modern OMS/PMS stack. SOC 2 Type II certified. Business continuity plan last tested Q1 2026.' },
  { criterionId: 'crit-07', name: 'Risk Management Framework', category: 'Risk', rating: 'Pass', confidencePct: 88, evidenceCount: 4, summary: 'Independent risk oversight function. VaR limits documented and enforced.' },
  { criterionId: 'crit-08', name: 'Performance Attribution & Track Record', category: 'Performance', rating: 'Pass', confidencePct: 96, evidenceCount: 7, summary: 'GIPS-compliant composites. 5-year alpha of 1.8% net of fees vs benchmark.' },
  { criterionId: 'crit-09', name: 'Fee Structure & Transparency', category: 'Governance', rating: 'Pass', confidencePct: 99, evidenceCount: 2, summary: 'Standard 2/20. Full transparency on side pockets. No undisclosed conflicts.' },
  { criterionId: 'crit-10', name: 'Counterparty & Custodian Arrangements', category: 'Operations', rating: 'Pass', confidencePct: 93, evidenceCount: 3, summary: 'Prime brokerage with Goldman Sachs. Independent custodian (BNY Mellon).' },
  { criterionId: 'crit-11', name: 'ESG Policy & Implementation', category: 'ESG', rating: 'Pass_With_Conditions', confidencePct: 72, evidenceCount: 3, summary: 'PRI signatory since 2022. ESG scoring applied to 85% of portfolio. No net-zero commitment yet.' },
  { criterionId: 'crit-12', name: 'Audit & Financial Controls', category: 'Governance', rating: 'Pass', confidencePct: 97, evidenceCount: 4, summary: 'Annual audit by Big 4 firm. Clean opinion for 5 consecutive years.' },
];

export const MOCK_HITL_FLAG: HitlFlag = {
  flagId: 'flag-01',
  reviewId: 'rev-amp-001',
  criterionId: 'crit-05',
  criterionName: 'Key Person Risk',
  flagReason: 'Lead portfolio manager concentration exceeds 80% threshold. No documented succession plan or deputy PM identified in most recent DDQ or Form ADV.',
  riskLevel: 'high',
  aiAssessment: 'Based on the available evidence, this represents a material operational risk. The fund\'s investment process is highly dependent on Sarah Chen (CIO/Lead PM). The 2025 DDQ does not identify a successor and the most recent Form ADV Part 2A does not disclose any deputy PM arrangement. I recommend flagging as "Requires Review" and requesting an updated DDQ with specific succession planning disclosure.',
  evidenceExcerpts: [
    {
      sourceId: 'src-01',
      sourceTitle: 'AMP Growth Fund DDQ 2025',
      sourceDateIso: '2025-11-15',
      excerpt: 'The fund\'s investment strategy is led exclusively by Sarah Chen, CIO, who retains sole decision-making authority over all portfolio construction and risk management activities.',
      pageRef: 'p. 14, Section 3.2',
    },
    {
      sourceId: 'src-02',
      sourceTitle: 'Form ADV Part 2A — Meridian Capital Partners',
      sourceDateIso: '2026-03-01',
      excerpt: 'Meridian Capital\'s investment management activities are directed by Sarah Chen. The firm employs 3 junior analysts who support research but do not have portfolio management authority.',
      pageRef: 'p. 8',
    },
  ],
  status: 'pending',
};

// Simulated streaming event sequence for demo playback
export const MOCK_SSE_SEQUENCE: AgentActivityEvent[] = [
  { eventId: 'e01', agentName: 'Supervisor', eventType: 'task_start', message: 'Received ODD request for AMP Growth Fund. Decomposing into 12 assessment criteria across 5 domains.', timestamp: '+0s' },
  { eventId: 'e02', agentName: 'EvidenceGatherer', eventType: 'task_start', message: 'Retrieving documents from knowledge base: DDQ 2025, Form ADV, audited financials (3Y), news feed.', timestamp: '+2s' },
  { eventId: 'e03', agentName: 'EvidenceGatherer', eventType: 'tool_call', message: 'Calling search_documents(query="AMP Growth Fund governance structure", sources=["DDQ","FormADV"])', timestamp: '+3s' },
  { eventId: 'e04', agentName: 'EvidenceGatherer', eventType: 'tool_result', message: 'Retrieved 5 relevant excerpts. Highest relevance: DDQ 2025 Section 1 (score 0.94).', timestamp: '+4s', durationMs: 1240 },
  { eventId: 'e05', agentName: 'CriteriaAnalyst', eventType: 'criteria_assessed', message: 'Criterion 1: Ownership & Governance — PASS (confidence 94%). Independent board majority confirmed.', criterionId: 'crit-01', timestamp: '+5s' },
  { eventId: 'e06', agentName: 'CriteriaAnalyst', eventType: 'criteria_assessed', message: 'Criterion 2: Regulatory Compliance — PASS (confidence 98%). SEC/FINRA registration current, no enforcement actions.', criterionId: 'crit-02', timestamp: '+7s' },
  { eventId: 'e07', agentName: 'EvidenceGatherer', eventType: 'tool_call', message: 'Calling fetch_performance_data(fund="AMP-GF-2024", period="5Y", benchmark="MSCI World")', timestamp: '+8s' },
  { eventId: 'e08', agentName: 'CriteriaAnalyst', eventType: 'criteria_assessed', message: 'Criterion 3: AUM & Asset Flows — PASS WITH CONDITIONS. Client concentration 68% in top 3.', criterionId: 'crit-03', timestamp: '+12s' },
  { eventId: 'e09', agentName: 'CriteriaAnalyst', eventType: 'criteria_assessed', message: 'Criterion 4: Investment Process — PASS (confidence 91%). No style drift detected.', criterionId: 'crit-04', timestamp: '+15s' },
  { eventId: 'e10', agentName: 'CriteriaAnalyst', eventType: 'hitl_flag', message: 'HITL FLAG: Criterion 5 Key Person Risk — Lead PM concentration >80%, no succession plan. Escalating to human review.', criterionId: 'crit-05', timestamp: '+18s' },
  { eventId: 'e11', agentName: 'Supervisor', eventType: 'task_start', message: 'Pausing assessment of Criterion 5. Continuing with remaining criteria in parallel.', timestamp: '+19s' },
  { eventId: 'e12', agentName: 'CriteriaAnalyst', eventType: 'criteria_assessed', message: 'Criterion 6: Operations & Technology — PASS. SOC 2 Type II, BCP tested Q1 2026.', criterionId: 'crit-06', timestamp: '+22s' },
  { eventId: 'e13', agentName: 'CriteriaAnalyst', eventType: 'criteria_assessed', message: 'Criterion 7: Risk Management — PASS. Independent risk function, VaR limits enforced.', criterionId: 'crit-07', timestamp: '+25s' },
  { eventId: 'e14', agentName: 'CriteriaAnalyst', eventType: 'criteria_assessed', message: 'Criterion 8: Performance Track Record — PASS (confidence 96%). GIPS-compliant, 1.8% net alpha.', criterionId: 'crit-08', timestamp: '+28s' },
];

export const MOCK_REPORT_MARKDOWN = `# Operational Due Diligence Report
## AMP Growth Fund — Meridian Capital Partners

**Review Type:** ODD  **Completed:** July 13, 2026  **Analyst (AI):** DD Agent v2.1

---

## Executive Summary

The AMP Growth Fund managed by Meridian Capital Partners has been assessed across 12 operational due diligence criteria. The fund demonstrates strong governance, regulatory compliance, and performance track record. **One material finding** requires human review: concentration of investment authority in the Lead Portfolio Manager without a documented succession plan [1][2].

Overall assessment: **Conditional Pass** — subject to resolution of Key Person Risk (Criterion 5).

---

## Governance

### Ownership & Governance Structure — PASS

Meridian Capital Partners is wholly owned by Sarah Chen (65%) and David Park (35%). The Advisory Board comprises 5 members, of whom 3 are independent. Board meeting minutes confirm quarterly governance reviews [3].

### Regulatory Compliance — PASS

The firm holds current SEC RIA registration (CRD# 281934) and all required FINRA licenses. No open enforcement actions, investigations, or regulatory sanctions were identified in the review period [4].

### Fee Structure & Transparency — PASS

Standard management fee of 2% AUM and performance fee of 20% above an 8% hurdle rate. Side pocket arrangements are fully disclosed to LPs. No undisclosed conflicts of interest were identified [5].

---

## Risk

### Key Person Risk — REQUIRES HUMAN REVIEW

> **HUMAN REVIEW REQUIRED:** This criterion has been flagged for analyst review. See HITL flags section.

AI Preliminary Assessment: Based on DDQ 2025 Section 3.2 [1] and Form ADV Part 2A [2], investment decision-making authority is concentrated exclusively with Sarah Chen, CIO. No deputy PM or succession plan is documented. This represents a material operational risk under the fund's own stated risk framework.

---

## Citations

[1] AMP Growth Fund DDQ 2025, Meridian Capital Partners, November 2025 — Section 3.2, Key Personnel

[2] Form ADV Part 2A, Meridian Capital Partners, March 2026 — Item 9, Disciplinary Information; Item 10, Other Financial Industry Activities

[3] Advisory Board Charter, Meridian Capital Partners, January 2024

[4] SEC IAPD Search, Meridian Capital Partners CRD# 281934, retrieved July 2026

[5] LPA Summary, AMP Growth Fund Series A, January 2023 — Schedule of Fees
`;

export const MOCK_REPORT: DDReport = {
  reviewId: 'rev-amp-001',
  generatedAt: new Date().toISOString(),
  approvalStatus: 'draft',
  markdownContent: MOCK_REPORT_MARKDOWN,
  citations: [
    { citationId: '1', sourceTitle: 'AMP Growth Fund DDQ 2025', sourceType: 'DDQ', excerpt: 'The fund\'s investment strategy is led exclusively by Sarah Chen, CIO, who retains sole decision-making authority...', pageRef: 'p. 14, Section 3.2', date: '2025-11-15' },
    { citationId: '2', sourceTitle: 'Form ADV Part 2A — Meridian Capital Partners', sourceType: 'Regulatory_Filing', excerpt: 'Meridian Capital\'s investment management activities are directed by Sarah Chen...', pageRef: 'p. 8', date: '2026-03-01' },
    { citationId: '3', sourceTitle: 'Advisory Board Charter', sourceType: 'Internal_Note', excerpt: 'The Advisory Board shall convene quarterly. Three of five members shall be independent directors...', date: '2024-01-10' },
    { citationId: '4', sourceTitle: 'SEC IAPD — Meridian Capital Partners', sourceType: 'Regulatory_Filing', excerpt: 'CRD# 281934. Registration status: Active. No disciplinary disclosures.', date: '2026-07-13' },
    { citationId: '5', sourceTitle: 'LPA Summary, AMP Growth Fund Series A', sourceType: 'Internal_Note', excerpt: 'Management Fee: 2.0% per annum of NAV. Performance Allocation: 20% above 8% preferred return...', pageRef: 'Schedule of Fees', date: '2023-01-15' },
  ],
  humanOverrides: [],
};

export const AVAILABLE_PORTFOLIOS = [
  { id: 'AMP-GF-2024', name: 'AMP Growth Fund', manager: 'Meridian Capital Partners' },
  { id: 'BWC-ALPHA-23', name: 'Bridgewater Core Alpha', manager: 'Bridgewater Associates' },
  { id: 'HG-EM-2025', name: 'HG Emerging Markets', manager: 'Hillhouse Capital' },
  { id: 'CANY-V3-2024', name: 'Canyon Value Fund III', manager: 'Canyon Capital Advisors' },
  { id: 'TPG-RF-2024', name: 'TPG Real Assets Fund', manager: 'TPG Capital' },
  { id: 'AQR-MM-2023', name: 'AQR Multi-Strategy', manager: 'AQR Capital Management' },
];
```

---

## 10. Sidebar Navigation Addition

Add a new entry to `packages/ui/src/components/app-sidebar.tsx` (or equivalent nav component):

```typescript
{
  title: 'Portfolio DD',
  url: '/portfolio-dd',
  icon: ClipboardCheckIcon,   // from lucide-react
}
```

---

## 11. Demo Script — 15-Minute Walkthrough

### Pre-demo setup checklist

1. Reset mock state: clear `localStorage.dd_reviews` and re-seed with `MOCK_REVIEWS` snapshot.
2. Confirm dev server at `http://localhost:4200` with mock API at `http://localhost:9000`.
3. Have browser dev tools closed. Open Chrome with zoom at 90%.
4. Queue demo at `/portfolio-dd` — AMP Growth Fund showing `in_progress` with 0% so the full run is visible.

---

### 0:00 — Context (stay on slide, no app)

**Talking points:**

"Today wealth managers and allocators run up to 600 portfolio reviews per year. The typical ODD takes a research team 3-4 weeks from document collection through final report. That involves reading hundreds of pages of DDQs, ADVs, audits, and news — then writing a structured 20-page report from scratch. We have two senior researchers. The math doesn't work. What you're about to see is how Amazon Bedrock multi-agent collaboration compresses that workflow to minutes."

---

### 1:00 — Dashboard tour (`/portfolio-dd`)

**Click:** Navigate to `/portfolio-dd` in the sidebar under "Portfolio DD."

**Talking points:**

"This is the DD command center. The queue metrics row at the top tells us we have 3 active reviews, 1 waiting for a human decision, and we've completed 14 reviews this month — saving an estimated 8 researcher-weeks. Below that is the portfolio table. Each row is a live review with a status badge and a progress bar. You can see Bridgewater Core Alpha is 92% done and paused at 'Awaiting Human Review' — we'll come back to that. Canyon Value Fund is queued up next."

---

### 2:00 — Start new review for AMP Growth Fund

**Click:** "Start New Review" button (top right of the portfolio table).

**Talking points:**

"Let's trigger a fresh Operational Due Diligence for AMP Growth Fund, a growth-equity fund run by Meridian Capital. We select the portfolio from the dropdown, choose review type ODD, and hit Start Review."

**Action:** Select "AMP Growth Fund" from the Combobox. Select "ODD" from review type dropdown. Click "Start Review."

**Expected behavior:** Modal closes, new row appears in table with status badge "In Progress" and progress bar at 0%. Navigate button "View" in the Action column. Brief "Review started" toast notification.

**Click:** "View" on the new AMP Growth Fund row.

---

### 3:00 — Live agent activity feed begins

**On screen:** `/portfolio-dd/rev-amp-001` — Review detail page.

**Talking points:**

"We're now watching the review happen in real time. On the right side is the agent activity feed. Think of this as a glass-box view into what the AI is doing — you can see every step, every tool call, every document retrieved. No black box."

**Watch the feed populate (SSE events streaming):**

- Supervisor decomposes the review into 12 criteria across 5 domains
- EvidenceGatherer calls `search_documents` for governance structure docs
- EvidenceGatherer returns: "Retrieved 5 relevant excerpts, highest relevance: DDQ 2025 Section 1 (score 0.94)"

**Talking points:**

"The Supervisor agent broke the ODD into 12 criteria and dispatched sub-agents to gather evidence for each one. The Evidence Gatherer is querying the knowledge base — this includes the DDQ, Form ADV, three years of audited financials, and external news sources. It's scoring each document for relevance before passing it to the Criteria Analyst."

---

### 5:00 — Assessment matrix populating

**On screen:** Left panel — criteria rows turning green one by one.

**Talking points:**

"On the left side, the Assessment Matrix is filling in live. Each of the 12 criteria gets a rating badge — green for Pass, amber for Requires Review, red for Fail — along with a confidence percentage and evidence count. Let's watch criteria 1 through 4 come through."

**Point at:** Criterion 1 (Governance Structure) — Pass, confidence 94%, 5 documents.

"94% confidence on governance structure. The agent found clear evidence of independent board majority and a clean ownership structure in the DDQ."

**Point at:** Criterion 3 (AUM & Asset Flows) — Pass With Conditions, confidence 81%.

"This one came back as 'Pass With Conditions.' The fund grew 22% in AUM, which is positive — but 68% of assets are concentrated in three institutional clients. That's worth noting in the report but not a blocking issue. The agent flagged it with lower confidence and a nuanced summary."

---

### 8:00 — HITL flag appears

**On screen:** Activity feed shows red event card: "HITL FLAG: Criterion 5 Key Person Risk — escalating to human review." The HITL Flags panel at the bottom expands automatically and shows a red-bordered card.

**Talking points:**

"Here's where it gets interesting. The agent hit criterion 5 — Key Person Risk — and instead of just logging a rating, it flagged it for human review. Why? Because the DDQ explicitly states that the Lead Portfolio Manager, Sarah Chen, holds sole decision-making authority over the entire fund, and there's no succession plan documented anywhere in the evidence. The agent knows this is material. It's not going to make that call unilaterally."

---

### 9:00 — Researcher reviews the flag and evidence

**Click:** The HitlFlagCard expands the evidence accordion.

**Talking points:**

"As the researcher, I can see exactly what the AI found. Here are the two excerpts it pulled — one from the DDQ, one from the Form ADV. Both confirm the concentration. The agent also wrote its preliminary assessment: it recommends rating this as 'Requires Review' and requesting an updated DDQ."

**Read excerpt aloud:** "The fund's investment strategy is led exclusively by Sarah Chen, CIO, who retains sole decision-making authority over all portfolio construction and risk management activities."

"I've reviewed this. I agree with the AI. This is a real risk — single point of failure at the investment committee level. But it's not a dealbreaker for our client's risk tolerance given the fund's track record."

**Click:** "Accept AI Assessment" button on the flag card.

**Expected behavior:** Flag status updates to "Accepted," badge changes from amber to green, flag card collapses. Activity feed adds event: "Supervisor: Criterion 5 flag resolved by analyst. Resuming report generation."

---

### 10:00 — Report generation begins

**On screen:** Status header progress bar moves from ~75% to 90%. A new activity event appears: "ReportWriter: Generating executive summary..."

**Talking points:**

"With all 12 criteria assessed — 11 by the AI, 1 confirmed by a human — the Supervisor agent has enough signal to start drafting the report. This isn't a template fill-in; the Report Writer agent synthesizes the evidence excerpts and assessments into structured markdown with inline citations."

**Watch:** Progress bar moving to 100%. Status badge changes from "In Progress" to "Complete."

---

### 12:00 — Open the report

**Click:** "View Report" button that appears in the status header once complete, or navigate to `/portfolio-dd/rev-amp-001/report`.

**On screen:** Full markdown report rendered with headings, sections, citation badges.

**Talking points:**

"The full ODD report. Executive summary at the top — conditional pass, subject to the key person risk finding. Then detailed sections for each domain: Governance, Risk, Operations, Performance, ESG. Let me show you citations."

---

### 12:30 — Citation hover demo

**Hover over** `[1]` inline citation in the Key Person Risk section.

**Expected behavior:** Tooltip appears showing source title "AMP Growth Fund DDQ 2025," date, and the exact excerpt the agent used to support that finding.

**Talking points:**

"Every factual claim in this report is linked to a source document. Hover over any citation number and you get the exact excerpt the agent used. This makes the report fully auditable — you can trace every sentence back to its evidence. No hallucinated facts, no missing citations."

---

### 13:30 — Approve the report

**Scroll to bottom:** Sticky approval toolbar.

**Talking points:**

"As the reviewing analyst, I'm satisfied. The report accurately reflects the evidence. Key Person Risk is correctly called out. I'll approve it."

**Click:** "Approve Report" button.

**Expected behavior:** AlertDialog appears — "Confirm approval of AMP Growth Fund ODD Report?" with optional notes field. Click "Confirm."

Toast: "Report approved successfully."

Navigate back to `/portfolio-dd` — review row now shows "Complete" badge.

---

### 13:45 — Download PDF

**Navigate back to report, click** "Download PDF" button in the toolbar.

**Expected behavior:** `window.print()` triggers browser print dialog with the report content. (In production this would call a PDF generation Lambda.)

**Talking points:**

"One click to download. In production, this calls a Lambda function that runs the markdown through a headless Chromium PDF renderer and returns a signed S3 URL. For the demo today, it just triggers the browser print dialog."

---

### 14:00 — Metrics update

**Navigate to** `/portfolio-dd`.

**Point at** queue metrics row.

**Talking points:**

"Back on the dashboard, the metrics have updated. Completed This Month is now 15. Time Saved Est. went up. The number I want you to focus on: manually, this review would have taken one of our researchers 4 weeks. Document collection alone is 3-5 business days. The AI completed it — with human verification of the one high-risk finding — in 12 minutes. That's a 99% reduction in elapsed calendar time. Same quality, full audit trail, researcher time spent only where human judgment actually matters."

---

### 14:30 — Architectural callout (optional if time permits)

**Talking points:**

"Under the hood, this is three Amazon Bedrock agents coordinated by a Supervisor. The Supervisor uses Claude 3.5 Sonnet. Sub-agents use specialized tool definitions — one for document retrieval from a Knowledge Base, one for structured criteria analysis, one for report writing. The HITL logic is a rule in the Supervisor's prompt: if confidence is below 75% or if a specific risk pattern is detected, raise a flag instead of assigning a rating. The frontend receives all of this via SSE streaming — the same pattern already used in the Advisor Chat widget. No new infrastructure required."

---

### 15:00 — Q&A

Suggested questions to prepare for:

**Q: What happens if the AI gets a criterion wrong?**  
A: The system supports two resolution paths: Accept (agree with AI) or Override (set a different rating with a mandatory rationale). Both are recorded in the report's Human Overrides section with the reviewer's name, timestamp, and reasoning. The override diff view in the report shows the original AI rating side-by-side with the human decision.

**Q: How does it handle documents it can't parse?**  
A: The Evidence Gatherer tracks retrieval failures and reports them as low-confidence findings with "insufficient evidence" flags. These automatically trigger HITL review rather than assigning a rating on incomplete data.

**Q: What's the data privacy story?**  
A: All document retrieval happens within the customer's AWS account. DDQs and ADVs are stored in an S3-backed Knowledge Base with VPC endpoints. No fund documents leave the customer's AWS boundary.

---

## 12. Dependency Notes

The following npm packages are required beyond what is currently installed. Verify each in `packages/ui/package.json` before implementation:

| Package | Purpose | Status to verify |
|---|---|---|
| `react-markdown` | Report rendering | Already used in `ImprovedChatWidget.tsx` |
| `remark-gfm` | GFM tables in markdown | Already used in `ImprovedChatWidget.tsx` |
| `date-fns` | `formatDistanceToNow` for table timestamps | Check if already in deps |
| `lucide-react` | Icons (ClipboardCheck, etc.) | Check if already in deps |

shadcn/ui components to add if not already registered in `components.json`:

```
npx shadcn@latest add badge
npx shadcn@latest add progress
npx shadcn@latest add dialog
npx shadcn@latest add select
npx shadcn@latest add table
npx shadcn@latest add tooltip
npx shadcn@latest add alert-dialog
npx shadcn@latest add collapsible
npx shadcn@latest add card
npx shadcn@latest add skeleton
npx shadcn@latest add textarea
```

All commands should be run from the repo root since `components.json` is at `/Users/jenntip/Repositories/sample-wealth-advisor-demo-platform/components.json`.

---

## 13. API Endpoint Summary

The backend spec (Spec 05) should implement these endpoints consumed by this frontend:

| Method | Path | Used by |
|---|---|---|
| `GET` | `/portfolio-dd/metrics` | `useQueueMetrics` |
| `GET` | `/portfolio-dd/reviews` | `useReviews` |
| `POST` | `/portfolio-dd/reviews` | `useStartReview` |
| `GET` | `/portfolio-dd/reviews/:reviewId` | `useReviewDetail` |
| `GET` | `/portfolio-dd/reviews/:reviewId/stream` | `useReviewStream` (SSE) |
| `GET` | `/portfolio-dd/reviews/:reviewId/report` | `useDDReport` |
| `POST` | `/portfolio-dd/reviews/:reviewId/flags/:flagId/resolve` | `useResolveHitlFlag` |
| `POST` | `/portfolio-dd/reviews/:reviewId/report/approve` | `useApproveReport` |

For local development, all endpoints should be implemented as mock handlers in a dedicated MSW (Mock Service Worker) file at `packages/ui/src/mocks/portfolioDD.handlers.ts`, using `MOCK_REVIEWS`, `MOCK_METRICS`, `MOCK_CRITERIA`, `MOCK_HITL_FLAG`, and `MOCK_REPORT` from section 9 above.
