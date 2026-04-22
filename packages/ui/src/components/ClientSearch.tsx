import { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { PageLayout, SearchBox } from './PageLayout';
import { GraphSearchPage } from './GraphSearch';
import { useApiClient } from '../hooks/useApiClient';
import type { Api } from '../generated/api/client.gen';

function ReportCell({ clientId, api }: { clientId: string; api: Api }) {
  const [state, setState] = useState<'idle' | 'loading' | 'error'>('idle');

  const handleClick = () => {
    setState('loading');
    api
      .clientReport({ clientId })
      .then((r) => {
        if (r.status === 'complete' && r.presignedUrl) {
          window.open(r.presignedUrl, '_blank');
        } else {
          alert(`Report status: ${r.status}`);
        }
        setState('idle');
      })
      .catch(() => {
        setState('error');
      });
  };

  if (state === 'loading')
    return <span className="text-xs text-gray-400">Loading…</span>;
  if (state === 'error')
    return <span className="text-xs text-red-400">Failed</span>;
  return (
    <button
      onClick={handleClick}
      className="text-xs text-blue-600 hover:text-blue-700"
    >
      📋 View Report
    </button>
  );
}

interface Client {
  client_id: string;
  customer_name: string;
  segment: string;
  aum: number;
  net_worth: number;
  ytd_perf: number;
  goal_progress: number;
  risk_tolerance: string;
  client_since: string;
  interaction_sentiment: string;
  next_best_action: string | null;
}

type ViewMode = 'list' | 'graph';

export function ClientSearch() {
  const navigate = useNavigate();
  const api = useApiClient();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchQuery2, setSearchQuery2] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [showAll, setShowAll] = useState(false);
  const [sortField, setSortField] = useState<keyof Client | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const initialLimit = 50;

  useEffect(() => {
    fetchClients();
  }, [api]);

  const handleSort = (field: keyof Client) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedClients = [...clients].sort((a, b) => {
    if (!sortField) return 0;
    const aVal = a[sortField];
    const bVal = b[sortField];
    const modifier = sortDirection === 'asc' ? 1 : -1;
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return (aVal - bVal) * modifier;
    }
    return String(aVal).localeCompare(String(bVal)) * modifier;
  });

  // Fetch clients with optional limit
  const fetchClients = async (loadAll = false) => {
    if (!api) return;
    setLoading(true);
    try {
      const data = await api.clients({
        limit: loadAll ? undefined : initialLimit,
        offset: 0,
      });
      console.log('Fetched clients:', data);
      const mapped = (data.clients || []).map((client) => ({
        client_id: client.clientId,
        customer_name: client.customerName,
        net_worth: client.netWorth,
        ytd_perf: client.ytdPerf,
        goal_progress: client.goalProgress,
        risk_tolerance: client.riskTolerance,
        client_since: client.clientSince,
        interaction_sentiment: client.interactionSentiment,
        segment: client.segment,
        aum: client.aum,
        next_best_action: client.nextBestAction ?? null,
      }));
      setClients(mapped);
      if (loadAll) setShowAll(true);
    } catch (error) {
      console.error('Error fetching clients:', error);
    } finally {
      setLoading(false);
    }
  };

  // Natural language search
  const handleNLSearch = async () => {
    console.log('NL Search triggered with query:', searchQuery);
    if (!searchQuery.trim() || !api) return;
    setLoading(true);
    try {
      const result = await api.clientSearch({ query: searchQuery });
      console.log('NL Search result:', result);
      if (result.success && result.data) {
        const mapped = result.data.map((row: any) => ({
          client_id: row.client_id || '',
          customer_name:
            `${row.client_first_name || row.first_name || ''} ${row.client_last_name || row.last_name || ''}`.trim(),
          segment: row.client_segment || row.segment || '',
          risk_tolerance: row.risk_tolerance || '',
          client_since:
            row.client_since ||
            row.client_created_date ||
            row.created_date ||
            '',
          net_worth: row.net_worth || 0,
          ytd_perf: row.ytd_performance || 0,
          goal_progress: row.goal_progress || 0,
          interaction_sentiment: row.interaction_sentiment || '',
          aum: row.aum || 0,
          next_best_action: row.next_best_action ?? null,
        }));
        console.log('Mapped clients:', mapped);
        setClients(mapped);
      } else {
        alert(`Search failed: ${result.error}`);
      }
    } catch (error) {
      console.error('Error searching clients:', error);
      alert(`Search failed: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  // Natural language search for second search box
  const handleNLSearch2 = async () => {
    if (!searchQuery2.trim() || !api) return;
    setLoading(true);
    try {
      const result = await api.clientSearch({ query: searchQuery2 });
      if (result.success && result.data) {
        const mapped = result.data.map((row: any) => ({
          client_id: row.client_id || '',
          customer_name:
            `${row.client_first_name || row.first_name || ''} ${row.client_last_name || row.last_name || ''}`.trim(),
          segment: row.client_segment || row.segment || '',
          risk_tolerance: row.risk_tolerance || '',
          client_since:
            row.client_since ||
            row.client_created_date ||
            row.created_date ||
            '',
          net_worth: row.net_worth || 0,
          ytd_perf: row.ytd_performance || 0,
          goal_progress: row.goal_progress || 0,
          interaction_sentiment: row.interaction_sentiment || '',
          aum: row.aum || 0,
          next_best_action: row.next_best_action ?? null,
        }));
        setClients(mapped);
      } else {
        alert(`Search failed: ${result.error}`);
      }
    } catch (error) {
      console.error('Error searching clients:', error);
      alert(`Search failed: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageLayout
      title="Advisor Dashboard"
      headerContent={
        <SearchBox
          value={searchQuery}
          onChange={setSearchQuery}
          onSearch={handleNLSearch}
        />
      }
    >
      <div className="flex-1 overflow-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold text-gray-900">Client list</h1>

          {/* View Toggle */}
          <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setViewMode('list')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'list'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <svg
                className="w-5 h-5 inline-block mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
              List View
            </button>
            <button
              onClick={() => setViewMode('graph')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'graph'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <svg
                className="w-5 h-5 inline-block mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
              Graph View
            </button>
          </div>
        </div>

        {viewMode === 'list' ? (
          <>
            {/* Natural Language Search */}
            <div className="mb-6">
              <div className="relative">
                <svg
                  className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
                <input
                  type="text"
                  placeholder="Find customer list who has more than 15M, interested in Retirement, and located in NYC"
                  value={searchQuery2}
                  onChange={(e) => setSearchQuery2(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleNLSearch2();
                    }
                  }}
                  className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
            </div>

            {loading ? (
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Customer Name
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Segment
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        AUM
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Net Worth
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        YTD Perf.
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Goal Progress
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Risk Tolerance Level
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Client Since
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Interaction Sentiment
                        <div className="text-[10px] text-blue-600 normal-case">
                          ✨ AI Generated
                        </div>
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Client report
                        <div className="text-[10px] text-blue-600 normal-case">
                          ✨ AI Generated
                        </div>
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Next Best Actions
                        <div className="text-[10px] text-blue-600 normal-case">
                          ✨ AI Generated
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 relative">
                    <tr>
                      <td colSpan={12} className="relative">
                        <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                        <div className="space-y-0">
                          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
                            <div
                              key={i}
                              className="flex gap-4 px-4 py-4 border-b border-gray-100"
                            >
                              <div className="h-4 bg-gray-200 rounded w-32"></div>
                              <div className="h-4 bg-gray-200 rounded w-24"></div>
                              <div className="h-4 bg-gray-200 rounded w-20"></div>
                              <div className="h-4 bg-gray-200 rounded w-24"></div>
                              <div className="h-4 bg-gray-200 rounded w-16"></div>
                              <div className="h-4 bg-gray-200 rounded w-20"></div>
                              <div className="h-4 bg-gray-200 rounded w-28"></div>
                              <div className="h-4 bg-gray-200 rounded w-24"></div>
                              <div className="h-4 bg-gray-200 rounded w-16"></div>
                              <div className="h-4 bg-gray-200 rounded w-16"></div>
                              <div className="h-4 bg-gray-200 rounded w-12"></div>
                              <div className="h-4 bg-gray-200 rounded flex-1"></div>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th
                        onClick={() => handleSort('customer_name')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          Customer Name
                          {sortField === 'customer_name' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('segment')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          Segment
                          {sortField === 'segment' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('aum')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          AUM
                          {sortField === 'aum' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('net_worth')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          Net Worth
                          {sortField === 'net_worth' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('ytd_perf')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          YTD Perf.
                          {sortField === 'ytd_perf' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('goal_progress')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          Goal Progress
                          {sortField === 'goal_progress' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('risk_tolerance')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          Risk Tolerance Level
                          {sortField === 'risk_tolerance' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('client_since')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          Client Since
                          {sortField === 'client_since' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('interaction_sentiment')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-1">
                          Interaction Sentiment
                          {sortField === 'interaction_sentiment' && (
                            <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                        <div className="text-[10px] text-blue-600 normal-case">
                          ✨ AI Generated
                        </div>
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Client report
                        <div className="text-[10px] text-blue-600 normal-case">
                          ✨ AI Generated
                        </div>
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Next Best Actions
                        <div className="text-[10px] text-blue-600 normal-case">
                          ✨ AI Generated
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {sortedClients.map((client, index) => (
                      <tr
                        key={`${client.client_id}-${index}`}
                        className="hover:bg-gray-50"
                      >
                        <td
                          className="px-4 py-4 text-sm text-blue-600 font-medium cursor-pointer hover:underline"
                          onClick={() =>
                            navigate({ to: `/clients/${client.client_id}` })
                          }
                        >
                          {client.customer_name}
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-600">
                          {client.segment}
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-900 font-semibold">
                          ${(client.aum / 1000000).toFixed(1)}M
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-900 font-semibold">
                          ${(client.net_worth / 1000000).toFixed(1)}M
                        </td>
                        <td className="px-4 py-4 text-sm">
                          <span
                            className={`font-semibold ${client.ytd_perf >= 0 ? 'text-green-600' : 'text-red-600'}`}
                          >
                            {client.ytd_perf >= 0 ? '+' : ''}
                            {client.ytd_perf}%
                          </span>
                        </td>
                        <td className="px-4 py-4 text-sm">
                          <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                            {client.goal_progress}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-600">
                          {client.risk_tolerance}
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-600">
                          {client.client_since}
                        </td>
                        <td className="px-4 py-4 text-sm text-green-600 font-semibold">
                          {client.interaction_sentiment}
                        </td>
                        <td className="px-4 py-4 text-sm text-center">
                          <ReportCell clientId={client.client_id} api={api} />
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-600 max-w-xs truncate">
                          {client.next_best_action || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!showAll && clients.length === initialLimit && (
                  <div className="px-6 py-4 flex items-center justify-center border-t">
                    <button
                      onClick={() => fetchClients(true)}
                      className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                      disabled={loading}
                    >
                      Load More Data
                    </button>
                  </div>
                )}
                {clients.length === 0 && !loading && (
                  <div className="text-center py-8 text-gray-500">
                    No clients found
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="bg-white rounded-lg shadow h-[calc(100vh-250px)]">
            <GraphSearchPage />
          </div>
        )}
      </div>
    </PageLayout>
  );
}
