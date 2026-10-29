import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from '@tanstack/react-router';
import { PageLayout } from '../PageLayout';
import { useDDApi } from './useDDApi';
import type { DDReport } from './types';

const RAG_BADGE: Record<string, string> = {
  green: 'bg-green-100 text-green-700 border-green-200',
  amber: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  red: 'bg-red-100 text-red-700 border-red-200',
  grey: 'bg-gray-100 text-gray-500 border-gray-200',
};

const REC_STYLE: Record<string, string> = {
  APPROVE: 'bg-green-50 border-green-300 text-green-800',
  APPROVE_WITH_CONDITIONS: 'bg-amber-50 border-amber-300 text-amber-800',
  REJECT: 'bg-red-50 border-red-300 text-red-800',
};

const CATEGORY_LABELS: Record<string, string> = {
  investment_process: 'Investment Process',
  risk_operations: 'Risk & Operations',
  compliance_esg: 'Compliance & ESG',
  commercial: 'Commercial',
};

function ScoreBar({ score, max = 10 }: { score: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (score / max) * 100));
  const color =
    score >= 7 ? 'bg-green-500' : score >= 4 ? 'bg-amber-400' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-semibold w-12 text-right">
        {score.toFixed(1)}
      </span>
    </div>
  );
}

export function ReportViewer() {
  const { reviewId } = useParams({ from: '/due-diligence/$reviewId/report' });
  const navigate = useNavigate();
  const api = useDDApi();

  // Cached report: revisiting serves the cached report instantly instead of
  // re-fetching and showing "Loading report…" on every mount.
  const reportQuery = useQuery<DDReport>({
    queryKey: ['dd', 'report', reviewId],
    queryFn: () => api.getReport(reviewId),
    retry: false,
  });
  const report = reportQuery.data ?? null;
  const loading = reportQuery.isLoading;
  const error = reportQuery.isError
    ? reportQuery.error instanceof Error
      ? reportQuery.error.message
      : 'Failed to load report'
    : '';

  if (loading) {
    return (
      <PageLayout title="Report">
        <div className="text-center py-16 text-gray-400">Loading report…</div>
      </PageLayout>
    );
  }

  if (error || !report) {
    return (
      <PageLayout title="Report">
        <div className="text-center py-16 text-red-500">
          {error || 'Report not found'}
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Due Diligence Report"
      headerContent={
        <div className="flex gap-3">
          <button
            onClick={() =>
              navigate({ to: '/due-diligence/$reviewId', params: { reviewId } })
            }
            className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Back to Review
          </button>
          <button
            onClick={() => window.print()}
            className="px-4 py-2 text-sm bg-gray-800 text-white rounded-lg hover:bg-gray-900"
          >
            Print / Export
          </button>
        </div>
      }
    >
      {/* Overall recommendation banner */}
      <div
        className={`rounded-xl border-2 p-6 ${REC_STYLE[report.recommendation] ?? ''}`}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider opacity-70 mb-1">
              Recommendation
            </p>
            <p className="text-2xl font-bold">
              {report.recommendation.replace(/_/g, ' ')}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs font-medium uppercase tracking-wider opacity-70 mb-1">
              Overall Score
            </p>
            <p className="text-4xl font-bold">
              {report.overall_score.toFixed(1)}
              <span className="text-lg font-normal opacity-60">/10</span>
            </p>
          </div>
        </div>
        {report.hitl_required && (
          <div className="mt-4 flex items-center gap-2 text-amber-700 bg-amber-100 rounded-lg px-3 py-2 text-sm">
            <span className="font-medium">Human review required:</span>
            <span>{report.hitl_reasons.join('; ')}</span>
          </div>
        )}
      </div>

      {/* Executive summary */}
      {report.narrative && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-800 mb-3">
            Executive Summary
          </h2>
          <p className="text-gray-700 leading-relaxed whitespace-pre-line text-sm">
            {report.narrative}
          </p>
        </div>
      )}

      {/* Category scorecard */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Category Scorecard</h2>
        <div className="space-y-3">
          {report.category_summaries.map((cat) => (
            <div key={cat.category} className="flex items-center gap-4">
              <div className="w-44 text-sm text-gray-600 flex-shrink-0">
                {CATEGORY_LABELS[cat.category] ?? cat.category}
                <span className="ml-1 text-xs text-gray-400">
                  ({Math.round(cat.weight * 100)}%)
                </span>
              </div>
              <div className="flex-1">
                <ScoreBar score={cat.weighted_score / cat.weight} />
              </div>
              <span
                className={`px-2 py-0.5 rounded border text-xs font-medium w-16 text-center flex-shrink-0 ${RAG_BADGE[cat.rag_status] ?? ''}`}
              >
                {cat.rag_status.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Criteria detail */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-800 mb-4">
          Criteria Assessment
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-gray-100">
                <th className="pb-3 pr-4">Criterion</th>
                <th className="pb-3 pr-4 w-48">Score</th>
                <th className="pb-3 pr-4 w-20">RAG</th>
                <th className="pb-3">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {report.assessments.map((a) => (
                <tr key={a.criterion_id}>
                  <td className="py-3 pr-4 font-mono text-xs text-gray-500 align-top">
                    {a.criterion_id}
                  </td>
                  <td className="py-3 pr-4 align-top">
                    {a.score != null ? (
                      <ScoreBar score={a.score} />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="py-3 pr-4 align-top">
                    <span
                      className={`px-2 py-0.5 rounded border text-xs font-medium ${RAG_BADGE[a.rag_status] ?? ''}`}
                    >
                      {a.rag_status.toUpperCase()}
                    </span>
                    {a.hitl_required && (
                      <span className="ml-1 text-amber-500 text-xs">HITL</span>
                    )}
                  </td>
                  <td className="py-3 text-gray-600 text-xs leading-relaxed align-top">
                    {a.summary}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-gray-400 text-right">
        Generated {new Date(report.generated_at).toLocaleString()} | Report ID:{' '}
        {report.report_id}
      </p>
    </PageLayout>
  );
}
