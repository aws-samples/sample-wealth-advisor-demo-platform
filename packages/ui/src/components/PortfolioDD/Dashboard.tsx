import { useState, useCallback } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { PageLayout } from '../PageLayout';
import { useDDApi } from './useDDApi';
import type { Portfolio, Session } from './types';

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-700',
  complete: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

export function PortfolioDDDashboard() {
  const navigate = useNavigate();
  const api = useDDApi();
  const queryClient = useQueryClient();

  const [showModal, setShowModal] = useState(false);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState('');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  // Cached DD portfolios & sessions: returning to the page shows the cached
  // lists instantly (stale-while-revalidate) instead of refetching on mount.
  const portfoliosQuery = useQuery<Portfolio[]>({
    queryKey: ['dd', 'portfolios'],
    queryFn: () => api.listPortfolios(),
  });
  const sessionsQuery = useQuery<Session[]>({
    queryKey: ['dd', 'sessions'],
    queryFn: () => api.listSessions(),
  });
  const portfolios = portfoliosQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];

  const handleStartReview = useCallback(async () => {
    if (!selectedPortfolioId) return;
    setStarting(true);
    setError('');
    try {
      const session = await api.startReview(selectedPortfolioId);
      queryClient.setQueryData<Session[]>(['dd', 'sessions'], (prev) => [
        session,
        ...(prev ?? []),
      ]);
      setShowModal(false);
      navigate({
        to: '/due-diligence/$reviewId',
        params: { reviewId: session.session_id },
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start review');
    } finally {
      setStarting(false);
    }
  }, [selectedPortfolioId, api, navigate, queryClient]);

  const sortedSessions = [...sessions].sort(
    (a, b) =>
      new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
  );

  const inProgressCount = sessions.filter(
    (s) => s.status === 'in_progress',
  ).length;
  const completedCount = sessions.filter((s) => s.status === 'complete').length;
  const hitlCount = sessions.filter((s) => s.hitl_required).length;

  return (
    <PageLayout
      title="Portfolio Due Diligence"
      headerContent={
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          + New Review
        </button>
      }
    >
      {/* Metrics strip */}
      <div className="grid grid-cols-3 gap-4">
        {[
          {
            label: 'In Progress',
            value: inProgressCount,
            color: 'text-blue-600',
          },
          {
            label: 'Completed',
            value: completedCount,
            color: 'text-green-600',
          },
          { label: 'HITL Required', value: hitlCount, color: 'text-amber-600' },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="bg-white rounded-xl border border-gray-200 p-5"
          >
            <p className="text-sm text-gray-500">{label}</p>
            <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Sessions table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">Recent Reviews</h2>
        </div>
        {sessions.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-400">
            No reviews yet. Click &ldquo;+ New Review&rdquo; to start one.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-gray-100">
                <th className="px-6 py-3">Portfolio</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Score</th>
                <th className="px-6 py-3">Recommendation</th>
                <th className="px-6 py-3">Started</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sortedSessions.map((s) => (
                <tr
                  key={s.session_id}
                  className="hover:bg-gray-50 transition-colors"
                >
                  <td className="px-6 py-4 font-medium text-gray-900">
                    {s.portfolio_name}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[s.status] ?? ''}`}
                    >
                      {s.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {s.overall_score != null ? (
                      <span className="font-semibold">
                        {Number(s.overall_score).toFixed(1)}
                        <span className="text-gray-400">/10</span>
                      </span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {s.recommendation ? (
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          s.recommendation === 'APPROVE'
                            ? 'bg-green-100 text-green-700'
                            : s.recommendation === 'REJECT'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-amber-100 text-amber-700'
                        }`}
                      >
                        {s.recommendation}
                      </span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-gray-500">
                    {new Date(s.started_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() =>
                        navigate({
                          to: '/due-diligence/$reviewId',
                          params: { reviewId: s.session_id },
                        })
                      }
                      className="text-blue-600 hover:text-blue-700 text-xs font-medium"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Start Review modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Start New Due Diligence Review
            </h3>
            <label className="block text-sm text-gray-600 mb-1">
              Select Portfolio
            </label>
            <select
              value={selectedPortfolioId}
              onChange={(e) => setSelectedPortfolioId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none mb-4"
            >
              <option value="">-- choose a portfolio --</option>
              {portfolios.map((p) => (
                <option key={p.portfolio_id} value={p.portfolio_id}>
                  {p.name}
                </option>
              ))}
            </select>
            {error && <p className="text-red-500 text-sm mb-3">{error}</p>}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowModal(false);
                  setError('');
                }}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleStartReview}
                disabled={!selectedPortfolioId || starting}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {starting ? 'Starting…' : 'Start Review'}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  );
}
