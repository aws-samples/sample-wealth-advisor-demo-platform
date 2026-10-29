import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from '@tanstack/react-router';
import { useAuth } from 'react-oidc-context';
import { PageLayout } from '../PageLayout';
import { useDDApi } from './useDDApi';
import type {
  DDReport,
  Session,
  ProgressEvent,
  HITLFlag,
  CriterionAssessment,
} from './types';

const RAG_COLORS: Record<string, string> = {
  green: 'bg-green-100 text-green-700',
  amber: 'bg-amber-100 text-amber-700',
  red: 'bg-red-100 text-red-700',
  grey: 'bg-gray-100 text-gray-600',
};

const RAG_BAR: Record<string, string> = {
  green: 'bg-green-500',
  amber: 'bg-amber-400',
  red: 'bg-red-500',
  grey: 'bg-gray-300',
};

type Tab = 'overview' | 'criteria' | 'report' | 'sources' | 'log';

interface SourceDoc {
  name: string;
  key: string;
  type: string;
  pages?: number;
}

export function ReviewDetail() {
  const { reviewId } = useParams({ from: '/due-diligence/$reviewId' });
  const auth = useAuth();
  const api = useDDApi();

  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [expandedCriteria, setExpandedCriteria] = useState<Set<string>>(
    new Set(),
  );
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolveNotes, setResolveNotes] = useState('');
  const [loadingDocKey, setLoadingDocKey] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  // Cached, live-polling review data. While the review runs, the session and
  // event feed poll every 3s; once complete/failed the polling stops. Because
  // the data lives in the query cache, returning to a review renders instantly
  // from cache instead of blanking to a loading state while it re-fetches.
  const sessionQuery = useQuery<Session>({
    queryKey: ['dd', 'session', reviewId],
    queryFn: () => api.getSession(reviewId),
    enabled: !!reviewId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'complete' || s === 'failed' ? false : 3000;
    },
  });
  const session = sessionQuery.data ?? null;
  const isRunning =
    !session || (session.status !== 'complete' && session.status !== 'failed');

  const eventsQuery = useQuery<ProgressEvent[]>({
    queryKey: ['dd', 'events', reviewId],
    queryFn: () => api.getEvents(reviewId),
    enabled: !!reviewId,
    refetchInterval: isRunning ? 3000 : false,
  });
  const events = eventsQuery.data ?? [];

  const sourceDocsQuery = useQuery<SourceDoc[]>({
    queryKey: ['dd', 'sourceDocs', session?.portfolio_id],
    queryFn: () => api.listSourceDocuments(session?.portfolio_id ?? ''),
    enabled: !!session?.portfolio_id,
  });
  const sourceDocs = sourceDocsQuery.data ?? [];

  const flagsQuery = useQuery<HITLFlag[]>({
    queryKey: ['dd', 'flags', reviewId],
    queryFn: () => api.listFlags(reviewId),
    enabled: session?.status === 'complete',
  });
  const flags = flagsQuery.data ?? [];

  // Report can lag session completion; retry a few times before giving up.
  const reportQuery = useQuery<DDReport>({
    queryKey: ['dd', 'report', reviewId],
    queryFn: () => api.getReport(reviewId),
    enabled: session?.status === 'complete',
    retry: 3,
    retryDelay: 2000,
  });
  const report = reportQuery.data ?? null;

  useEffect(() => {
    feedRef.current?.scrollTo({
      top: feedRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [events]);

  const handleResolve = async (flagId: string, resolution: string) => {
    await api.resolveFlag(reviewId, flagId, resolution, resolveNotes);
    queryClient.setQueryData<HITLFlag[]>(['dd', 'flags', reviewId], (prev) =>
      (prev ?? []).map((f) =>
        f.flag_id === flagId
          ? {
              ...f,
              status: resolution as HITLFlag['status'],
              reviewer_notes: resolveNotes,
            }
          : f,
      ),
    );
    setResolvingId(null);
    setResolveNotes('');
  };

  const toggleCriterion = (id: string) => {
    setExpandedCriteria((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const tabs: { key: Tab; label: string; badge?: number }[] = [
    { key: 'overview', label: 'Overview' },
    {
      key: 'criteria',
      label: 'Criteria',
      badge: report?.assessments?.filter((a) => a.hitl_required).length,
    },
    { key: 'report', label: 'Report' },
    { key: 'sources', label: 'Sources', badge: sourceDocs.length || undefined },
    { key: 'log', label: 'Agent Log' },
  ];

  const ScoreBar = ({ score, max = 10 }: { score: number; max?: number }) => (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${score >= 7 ? 'bg-green-500' : score >= 4 ? 'bg-amber-400' : 'bg-red-500'}`}
          style={{ width: `${(score / max) * 100}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-600 w-8">
        {Number(score).toFixed(1)}
      </span>
    </div>
  );

  return (
    <PageLayout title={session?.portfolio_name ?? 'Due Diligence Review'}>
      {/* Header bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span
            className={`px-2.5 py-1 rounded-full text-xs font-medium ${
              session?.status === 'complete'
                ? 'bg-green-100 text-green-700'
                : session?.status === 'in_progress'
                  ? 'bg-blue-100 text-blue-700'
                  : session?.status === 'failed'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-100 text-gray-600'
            }`}
          >
            {session?.status ?? 'pending'}
          </span>
          {session?.overall_score != null && (
            <span className="text-lg font-bold text-gray-900">
              {Number(session.overall_score).toFixed(1)}/10
            </span>
          )}
          {session?.recommendation && (
            <span
              className={`px-2.5 py-1 rounded text-xs font-bold ${
                session.recommendation === 'APPROVE'
                  ? 'bg-green-100 text-green-700'
                  : session.recommendation === 'REJECT'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-amber-100 text-amber-700'
              }`}
            >
              {session.recommendation}
            </span>
          )}
        </div>
        {session?.started_at && (
          <span className="text-xs text-gray-500">
            Started: {new Date(session.started_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 bg-white rounded-t-xl mt-4">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
            {tab.badge != null && tab.badge > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] bg-amber-100 text-amber-700">
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="bg-white rounded-b-xl border border-t-0 border-gray-200 p-6 min-h-[500px]">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {report?.category_summaries && (
              <div>
                <h3 className="font-semibold text-gray-800 mb-3">
                  Category Scorecard
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  {report.category_summaries.map((cat) => (
                    <div
                      key={cat.category}
                      className="border border-gray-100 rounded-lg p-4"
                    >
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-gray-700 capitalize">
                          {cat.category.replace(/_/g, ' ')}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${RAG_COLORS[cat.rag_status]}`}
                        >
                          {cat.rag_status.toUpperCase()}
                        </span>
                      </div>
                      <ScoreBar score={cat.weighted_score} />
                      <p className="text-[10px] text-gray-400 mt-1">
                        Weight: {(cat.weight * 100).toFixed(0)}%
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {report?.narrative && (
              <div>
                <h3 className="font-semibold text-gray-800 mb-2">
                  Executive Summary
                </h3>
                <p className="text-sm text-gray-600 whitespace-pre-line leading-relaxed">
                  {report.narrative}
                </p>
              </div>
            )}

            {!report && session?.status === 'in_progress' && (
              <div className="text-center py-12 text-gray-400">
                <p className="text-lg">Analysis in progress...</p>
                <p className="text-sm mt-1">
                  The AI pipeline is evaluating this portfolio.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Criteria Details Tab */}
        {activeTab === 'criteria' && (
          <div className="space-y-3">
            {report?.assessments?.map((a: CriterionAssessment) => (
              <div
                key={a.criterion_id}
                className={`border rounded-lg overflow-hidden ${a.hitl_required ? 'border-amber-200' : 'border-gray-100'}`}
              >
                <button
                  onClick={() => toggleCriterion(a.criterion_id)}
                  className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50"
                >
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${RAG_BAR[a.rag_status]}`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">
                        {a.criterion_name || a.criterion_id}
                      </span>
                      {a.hitl_required && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700">
                          REVIEW
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">
                      {a.category?.replace(/_/g, ' ')} &middot; Weight:{' '}
                      {((a.weight ?? 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-32">
                    {a.score != null && <ScoreBar score={a.score} />}
                  </div>
                  <span className="text-gray-400 text-xs">
                    {expandedCriteria.has(a.criterion_id) ? '▲' : '▼'}
                  </span>
                </button>

                {expandedCriteria.has(a.criterion_id) && (
                  <div className="px-4 pb-4 pt-0 space-y-3 border-t border-gray-50 bg-gray-50/50">
                    {a.confidence != null && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">
                          Confidence:
                        </span>
                        <div className="w-20 h-1.5 bg-gray-200 rounded-full">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{
                              width: `${(a.confidence ?? 0) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">
                          {((a.confidence ?? 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}

                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        AI Rationale
                      </p>
                      <p className="text-sm text-gray-700">
                        {a.rationale || a.summary}
                      </p>
                    </div>

                    {a.evidence && a.evidence.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">
                          Evidence Sources
                        </p>
                        <ul className="space-y-1">
                          {a.evidence.map((e, i) => (
                            <li
                              key={i}
                              className="text-xs text-gray-600 bg-white rounded p-2 border border-gray-100"
                            >
                              {e}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {a.hitl_required && (
                      <div className="bg-amber-50 rounded-lg p-3 border border-amber-100">
                        <p className="text-xs font-medium text-amber-700 mb-2">
                          Human Review Required
                        </p>
                        {(() => {
                          const flag =
                            flags.find(
                              (f) =>
                                f.criterion_id === a.criterion_id ||
                                f.reason.includes(a.criterion_id),
                            ) ??
                            (flags.length > 0 && a.hitl_required
                              ? flags.find((f) => f.status === 'pending')
                              : undefined);
                          if (!flag) return null;
                          if (flag.status !== 'pending')
                            return (
                              <span
                                className={`px-2 py-0.5 rounded text-xs font-medium ${
                                  flag.status === 'approved'
                                    ? 'bg-green-100 text-green-700'
                                    : flag.status === 'rejected'
                                      ? 'bg-red-100 text-red-700'
                                      : 'bg-amber-100 text-amber-700'
                                }`}
                              >
                                {flag.status}
                              </span>
                            );
                          if (resolvingId === flag.flag_id)
                            return (
                              <div className="space-y-2">
                                <textarea
                                  className="w-full text-xs border border-gray-200 rounded p-2 resize-none"
                                  rows={2}
                                  placeholder="Reviewer notes..."
                                  value={resolveNotes}
                                  onChange={(e) =>
                                    setResolveNotes(e.target.value)
                                  }
                                />
                                <div className="flex gap-2">
                                  <button
                                    onClick={() =>
                                      handleResolve(flag.flag_id, 'approved')
                                    }
                                    className="flex-1 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700"
                                  >
                                    Approve
                                  </button>
                                  <button
                                    onClick={() =>
                                      handleResolve(flag.flag_id, 'rejected')
                                    }
                                    className="flex-1 py-1.5 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                                  >
                                    Reject
                                  </button>
                                  <button
                                    onClick={() =>
                                      handleResolve(flag.flag_id, 'escalated')
                                    }
                                    className="flex-1 py-1.5 text-xs bg-amber-500 text-white rounded hover:bg-amber-600"
                                  >
                                    Escalate
                                  </button>
                                </div>
                              </div>
                            );
                          return (
                            <button
                              onClick={() => setResolvingId(flag.flag_id)}
                              className="text-xs text-blue-600 hover:underline"
                            >
                              Make Decision
                            </button>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )) ?? (
              <p className="text-center text-gray-400 py-8">
                {session?.status === 'in_progress'
                  ? 'Assessment in progress...'
                  : 'No criteria data available'}
              </p>
            )}
          </div>
        )}

        {/* Report Tab */}
        {activeTab === 'report' && (
          <div className="space-y-6">
            {report ? (
              <>
                <div className="flex justify-end gap-2 mb-4">
                  <button
                    onClick={async () => {
                      const token = auth.user?.id_token;
                      const r = await fetch(api.getReportHtmlUrl(reviewId), {
                        headers: token
                          ? { Authorization: `Bearer ${token}` }
                          : {},
                      });
                      if (!r.ok) return;
                      const html = await r.text();
                      const w = window.open('', '_blank');
                      if (w) {
                        w.document.write(html);
                        w.document.close();
                      }
                    }}
                    className="px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Open Full Report
                  </button>
                  <button
                    onClick={async () => {
                      const token = auth.user?.id_token;
                      const r = await fetch(api.getReportHtmlUrl(reviewId), {
                        headers: token
                          ? { Authorization: `Bearer ${token}` }
                          : {},
                      });
                      if (!r.ok) return;
                      const html = await r.text();
                      const w = window.open('', '_blank');
                      if (w) {
                        w.document.write(html);
                        w.document.close();
                        setTimeout(() => w.print(), 500);
                      }
                    }}
                    className="px-3 py-1.5 text-xs font-medium bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                  >
                    Download PDF
                  </button>
                </div>
                <div
                  className={`p-4 rounded-lg border ${
                    report.recommendation === 'APPROVE'
                      ? 'bg-green-50 border-green-200'
                      : report.recommendation === 'REJECT'
                        ? 'bg-red-50 border-red-200'
                        : 'bg-amber-50 border-amber-200'
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="text-lg font-bold">
                      {report.recommendation}
                    </span>
                    <span className="text-2xl font-bold">
                      {Number(report.overall_score).toFixed(1)}/10
                    </span>
                  </div>
                  {report.hitl_required && (
                    <p className="text-xs mt-2 text-amber-700">
                      Human review required: {report.hitl_reasons?.join('; ')}
                    </p>
                  )}
                </div>

                {report.narrative && (
                  <div>
                    <h3 className="font-semibold text-gray-800 mb-2">
                      Executive Summary
                    </h3>
                    <p className="text-sm text-gray-600 whitespace-pre-line leading-relaxed">
                      {report.narrative}
                    </p>
                  </div>
                )}

                <div>
                  <h3 className="font-semibold text-gray-800 mb-3">
                    Assessment Details
                  </h3>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-gray-500 uppercase border-b">
                        <th className="pb-2">Criterion</th>
                        <th className="pb-2">Score</th>
                        <th className="pb-2">Status</th>
                        <th className="pb-2">Summary</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {report.assessments?.map((a) => (
                        <tr key={a.criterion_id}>
                          <td className="py-2 font-medium text-gray-700">
                            {a.criterion_name || a.criterion_id}
                          </td>
                          <td className="py-2 w-24">
                            {a.score != null && <ScoreBar score={a.score} />}
                          </td>
                          <td className="py-2">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${RAG_COLORS[a.rag_status]}`}
                            >
                              {a.rag_status}
                            </span>
                          </td>
                          <td className="py-2 text-xs text-gray-500 max-w-xs truncate">
                            {a.summary}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="text-center text-gray-400 py-12">
                {session?.status === 'complete'
                  ? 'Loading report...'
                  : 'Report will be available once analysis completes'}
              </p>
            )}
          </div>
        )}

        {/* Sources Tab */}
        {activeTab === 'sources' && (
          <div className="space-y-4">
            <p className="text-sm text-gray-500">
              Documents analyzed during the due diligence process.
            </p>
            {sourceDocs.length === 0 ? (
              <p className="text-center text-gray-400 py-8">
                No source documents available for this portfolio.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {sourceDocs.map((doc) => (
                  <div
                    key={doc.key}
                    className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-red-50 rounded-lg flex items-center justify-center">
                        <span className="text-red-600 text-xs font-bold">
                          PDF
                        </span>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {doc.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {doc.type}
                          {doc.pages ? ` · ${doc.pages} pages` : ''}
                        </p>
                      </div>
                    </div>
                    <button
                      className="text-xs text-blue-600 hover:text-blue-800 hover:underline font-medium disabled:opacity-50"
                      disabled={loadingDocKey === doc.key}
                      onClick={async () => {
                        if (!session?.portfolio_id) return;
                        setLoadingDocKey(doc.key);
                        const url = await api.getDocumentUrl(
                          session.portfolio_id,
                          doc.key,
                        );
                        setLoadingDocKey(null);
                        if (url) {
                          window.open(url, '_blank');
                        }
                      }}
                    >
                      {loadingDocKey === doc.key
                        ? 'Opening...'
                        : 'Source document ↗'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Agent Log Tab */}
        {activeTab === 'log' && (
          <div
            ref={feedRef}
            className="max-h-[500px] overflow-y-auto space-y-1 font-mono text-xs"
          >
            {events.length === 0 && (
              <p className="text-gray-400 text-center py-8">
                Waiting for pipeline to start...
              </p>
            )}
            {events.map((ev, i) => (
              <div key={i} className="flex gap-2 items-start py-0.5">
                <span
                  className={`font-medium ${
                    ev.event_type === 'error'
                      ? 'text-red-500'
                      : ev.event_type === 'report_ready'
                        ? 'text-green-600'
                        : ev.event_type === 'hitl_flag'
                          ? 'text-amber-600'
                          : 'text-gray-500'
                  }`}
                >
                  [{ev.event_type}]
                </span>
                <span className="text-gray-600">{ev.message}</span>
                {ev.score != null && (
                  <span className="text-gray-400">
                    score: {Number(ev.score).toFixed(1)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </PageLayout>
  );
}
