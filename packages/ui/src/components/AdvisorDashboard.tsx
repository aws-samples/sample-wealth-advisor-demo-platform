import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { PageLayout, SearchBox } from './PageLayout';
import { useApiClient } from '../hooks/useApiClient';
import { useApi } from '../hooks/useApi';
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

interface MetricCard {
  title: string;
  value: string;
  change: string;
  icon: string;
}

interface Meeting {
  id: string;
  clientName: string;
  time: string;
  type: string;
}

interface Alert {
  id: string;
  type: 'compliance' | 'market';
  title: string;
  message: string;
  severity: 'high' | 'medium' | 'low';
}

export function AdvisorDashboard() {
  const navigate = useNavigate();
  const api = useApiClient();
  const apiOptions = useApi();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedThemeId, setSelectedThemeId] = useState<string | null>(null);
  const [themeArticles, setThemeArticles] = useState<any[]>([]);
  const [articlesLoading, setArticlesLoading] = useState(false);
  const [expandedThemeId, setExpandedThemeId] = useState<string | null>(null);
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(
    null,
  );

  const themesQuery = useQuery(
    apiOptions.marketThemes.queryOptions({ limit: 6 }),
  );
  const aumQuery = useQuery(apiOptions.aumTrends.queryOptions({ limit: 12 }));
  const segmentsQuery = useQuery(apiOptions.clientSegments.queryOptions());
  const summaryQuery = useQuery(apiOptions.dashboardSummary.queryOptions());
  const topClientsQuery = useQuery(apiOptions.topClients.queryOptions());

  const marketThemes = themesQuery.data?.success
    ? (themesQuery.data.themes ?? [])
    : [];
  const themesStale = themesQuery.data?.staleMessage ?? null;
  const themesLoading = themesQuery.isLoading;

  const aumData = (aumQuery.data?.trends ?? []) as Array<{
    report_month: string;
    total_aum: number;
  }>;
  const aumLoading = aumQuery.isLoading;

  const clientSegments = (segmentsQuery.data?.segments ?? []).map((s) => ({
    segment: s.segment,
    client_count: s.clientCount,
    percentage: s.percentage,
  }));
  const segmentsLoading = segmentsQuery.isLoading;

  const dashboardSummary = summaryQuery.data
    ? {
        total_aum: summaryQuery.data.totalAum,
        total_aum_change: summaryQuery.data.totalAumChange,
        total_aum_change_percent: summaryQuery.data.totalAumChangePercent,
        active_clients: summaryQuery.data.activeClients,
        active_clients_change: summaryQuery.data.activeClientsChange,
        total_fees: summaryQuery.data.totalFees,
        fees_change: summaryQuery.data.feesChange,
        avg_portfolio_return_pct: summaryQuery.data.avgPortfolioReturnPct,
        avg_portfolio_return_value: summaryQuery.data.avgPortfolioReturnValue,
      }
    : null;

  const topClientsRaw = topClientsQuery.data?.clients ?? [];
  const sortedClients = [...topClientsRaw].sort((a, b) =>
    (a.clientSince ?? '').localeCompare(b.clientSince ?? ''),
  );
  const topClients = [
    ...new Map(sortedClients.map((c) => [c.clientId, c])).values(),
  ];
  const topClientsLoading = topClientsQuery.isLoading;

  // Auto-expand first theme when data arrives
  if (marketThemes.length > 0 && expandedThemeId === null) {
    setExpandedThemeId(marketThemes[0].themeId);
  }

  const fetchMarketThemes = () => {
    queryClient.invalidateQueries(
      apiOptions.marketThemes.queryFilter({ limit: 6 }),
    );
  };

  const metrics: MetricCard[] = [
    {
      title: 'Total AUM',
      value: dashboardSummary
        ? `$${(dashboardSummary.total_aum / 1000000).toFixed(2)}M`
        : '$0.00M',
      change: dashboardSummary
        ? `${dashboardSummary.total_aum_change >= 0 ? '+' : ''}${dashboardSummary.total_aum_change_percent?.toFixed(1) ?? '0.0'}% from last month`
        : '+0.0% from last month',
      icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    },
    {
      title: 'Avg. Portfolio Return',
      value: dashboardSummary?.avg_portfolio_return_pct
        ? `${dashboardSummary.avg_portfolio_return_pct >= 0 ? '+' : ''}${(dashboardSummary.avg_portfolio_return_pct * 100).toFixed(1)}%`
        : '+0.0%',
      change: dashboardSummary?.avg_portfolio_return_value
        ? `${dashboardSummary.avg_portfolio_return_value >= 0 ? '+' : ''}$${(Math.abs(dashboardSummary.avg_portfolio_return_value) / 1000).toFixed(1)}K from last month`
        : '+$0.0K from last month',
      icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6',
    },
    {
      title: 'Active Clients',
      value: dashboardSummary
        ? (dashboardSummary.active_clients?.toString() ?? '0')
        : '0',
      change: dashboardSummary
        ? `${dashboardSummary.active_clients_change >= 0 ? '+' : ''}${dashboardSummary.active_clients_change ?? 0} from last month`
        : '+0 from last month',
      icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z',
    },
    {
      title: 'Fee/Revenue',
      value: dashboardSummary
        ? `$${(dashboardSummary.total_fees / 1000000).toFixed(1)}M`
        : '$0.0M',
      change: dashboardSummary
        ? `${dashboardSummary.fees_change >= 0 ? '+' : ''}$${(Math.abs(dashboardSummary.fees_change) / 1000).toFixed(1)}K new this month`
        : '+$0.0K new this month',
      icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z',
    },
  ];

  const upcomingMeetings: Meeting[] = [
    {
      id: '1',
      clientName: 'Michael Chen',
      time: '10:00 AM',
      type: 'Portfolio Review',
    },
    {
      id: '2',
      clientName: 'Sarah Johnson',
      time: '2:00 PM',
      type: 'Financial Planning',
    },
    {
      id: '3',
      clientName: 'David Lee',
      time: '4:00 PM',
      type: 'Investment Strategy',
    },
  ];

  const alerts: Alert[] = [
    {
      id: '1',
      type: 'compliance',
      title: 'Compliance Alert',
      message: 'Annual compliance review due for 5 clients',
      severity: 'high',
    },
    {
      id: '2',
      type: 'market',
      title: 'Market Alert',
      message: 'S&P 500 volatility increased by 15%',
      severity: 'medium',
    },
  ];

  return (
    <PageLayout
      title="Advisor Dashboard"
      headerContent={
        <SearchBox value={searchQuery} onChange={setSearchQuery} />
      }
    >
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Key Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {metrics.map((metric, index) => (
            <div
              key={index}
              className="bg-white rounded-lg shadow p-4 relative overflow-hidden hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-pointer"
            >
              {!dashboardSummary && (
                <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
              )}
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  {!dashboardSummary ? (
                    <div className="space-y-2">
                      <div className="h-4 bg-gray-200 rounded w-24"></div>
                      <div className="h-7 bg-gray-200 rounded w-32"></div>
                      <div className="h-3 bg-gray-100 rounded w-36"></div>
                    </div>
                  ) : (
                    <>
                      <p className="text-sm text-gray-600 mb-1">
                        {metric.title}
                      </p>
                      <p className="text-2xl font-bold text-gray-900 mb-1">
                        {metric.value}
                      </p>
                      <p className="text-xs text-green-600">{metric.change}</p>
                    </>
                  )}
                </div>
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center ${!dashboardSummary ? 'bg-gray-100' : ''}`}
                >
                  {!dashboardSummary ? (
                    <div className="w-10 h-10 bg-gray-200 rounded-lg"></div>
                  ) : (
                    <svg
                      className="w-6 h-6 text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d={metric.icon}
                      />
                    </svg>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Row 1: AUM Trends + Client Segments */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* AUM Trends - Area Chart */}
          <div className="bg-white rounded-lg shadow p-4 lg:col-span-2">
            <h2 className="text-lg font-semibold text-[#1e293b] mb-4">
              AUM Trends
            </h2>
            <div className="h-56 -mr-4">
              {aumLoading ? (
                <div className="relative h-full bg-gray-50 rounded overflow-hidden">
                  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                  <div className="p-4 space-y-3">
                    <div className="h-4 bg-gray-200 rounded w-32"></div>
                    <div className="h-32 bg-gray-200 rounded"></div>
                    <div className="flex gap-2">
                      {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div
                          key={i}
                          className="h-3 bg-gray-200 rounded w-12"
                        ></div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : aumData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <AreaChart
                    data={aumData.map((d) => ({
                      month: new Date(d.report_month).toLocaleDateString(
                        'en-US',
                        { month: 'short' },
                      ),
                      value: d.total_aum / 1000000,
                    }))}
                    margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient
                        id="colorValue"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="5%"
                          stopColor="#8b5cf6"
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="95%"
                          stopColor="#8b5cf6"
                          stopOpacity={0.05}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="month"
                      stroke="#6b7280"
                      style={{ fontSize: '13px' }}
                      interval={0}
                    />
                    <YAxis
                      stroke="#6b7280"
                      style={{ fontSize: '13px' }}
                      width={60}
                      tickFormatter={(value) => `$${value}M`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'white',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                        fontSize: '13px',
                      }}
                      formatter={(value) => [
                        `$${Number(value ?? 0).toFixed(1)}M`,
                        'AUM',
                      ]}
                      labelFormatter={(label) => `Month ${label}`}
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke="#8b5cf6"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#colorValue)"
                      dot={{ fill: '#8b5cf6', r: 4.5 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full bg-gray-50 rounded">
                  <p className="text-gray-500">No AUM data available</p>
                </div>
              )}
            </div>
          </div>

          {/* Client Segments - Pie Chart */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold text-[#1e293b] mb-4">
              Client Segments
            </h2>
            <div className="h-56">
              {segmentsLoading ? (
                <div className="relative h-full bg-gray-50 rounded overflow-hidden">
                  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                  <div className="flex items-center justify-center h-full">
                    <div className="w-40 h-40 bg-gray-200 rounded-full"></div>
                  </div>
                </div>
              ) : clientSegments.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <PieChart>
                    <Pie
                      data={clientSegments}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      paddingAngle={2}
                      dataKey="client_count"
                      isAnimationActive={true}
                      animationBegin={0}
                      animationDuration={800}
                      labelLine={false}
                      onMouseEnter={(_, index) => setActiveSegmentIndex(index)}
                      onMouseLeave={() => setActiveSegmentIndex(null)}
                      label={(props: any) => {
                        const {
                          cx,
                          cy,
                          midAngle,
                          outerRadius,
                          segment,
                          percent,
                          index: _index,
                        } = props;
                        const RADIAN = Math.PI / 180;

                        // Label inside pie
                        const radius = outerRadius * 0.55;
                        const x = cx + radius * Math.cos(-midAngle * RADIAN);
                        const y = cy + radius * Math.sin(-midAngle * RADIAN);

                        // Split long segment names
                        const words = segment.split(' ');
                        const lines = words.length > 1 ? words : [segment];
                        const totalLines = lines.length + 1; // +1 for percentage
                        const startY = -(totalLines - 1) * 0.5;

                        return (
                          <text
                            x={x}
                            y={y}
                            fill="#1e293b"
                            fillOpacity={1}
                            textAnchor="middle"
                            dominantBaseline="central"
                            className="text-xs font-semibold"
                            style={{ pointerEvents: 'none' }}
                          >
                            {lines.map((line: string, i: number) => (
                              <tspan
                                key={i}
                                x={x}
                                dy={i === 0 ? `${startY}em` : '1em'}
                              >
                                {line}
                              </tspan>
                            ))}
                            <tspan
                              x={x}
                              dy="1em"
                            >{`(${(percent * 100).toFixed(0)}%)`}</tspan>
                          </text>
                        );
                      }}
                    >
                      {clientSegments.map((entry, index) => {
                        const COLORS = [
                          '#8b5cf6',
                          '#ec4899',
                          '#06b6d4',
                          '#f59e0b',
                        ];
                        const isActive = activeSegmentIndex === index;
                        return (
                          <Cell
                            key={`cell-${index}`}
                            fill={COLORS[index % COLORS.length]}
                            fillOpacity={
                              activeSegmentIndex === null || isActive ? 1 : 0.3
                            }
                            style={{
                              filter: isActive ? 'brightness(1.2)' : 'none',
                              cursor: 'pointer',
                              transition: 'all 0.3s ease',
                            }}
                          />
                        );
                      })}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'white',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                        fontSize: '13px',
                        padding: '8px 12px',
                      }}
                      formatter={(value, name, props: any) => [
                        `${value} clients (${props.payload.percentage.toFixed(1)}%)`,
                        props.payload.segment,
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full bg-gray-50 rounded">
                  <p className="text-gray-500">No data</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Row 2: Market Themes + Meetings/Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Market Themes */}
          <div className="lg:col-span-2 bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-900">
                Market Themes
              </h2>
              <button
                onClick={fetchMarketThemes}
                className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
              >
                <span>🔄</span> Refresh
              </button>
            </div>
            <div className="min-h-[200px]">
              {themesStale && (
                <div className="mb-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 flex items-center gap-2">
                  <span>⚠️</span> {themesStale}
                </div>
              )}
              {themesLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div
                      key={i}
                      className="border rounded-lg bg-white p-4 relative overflow-hidden"
                    >
                      {/* Shimmer effect */}
                      <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>

                      <div className="flex items-start gap-3">
                        {/* Rank */}
                        <div className="w-6 h-5 bg-gray-200 rounded"></div>

                        {/* Content */}
                        <div className="flex-1 space-y-3">
                          {/* Title and badges */}
                          <div className="flex items-center gap-2">
                            <div
                              className="flex-1 h-5 bg-gray-200 rounded"
                              style={{ width: `${60 + i * 5}%` }}
                            ></div>
                            <div className="w-16 h-6 bg-gray-200 rounded-full"></div>
                            <div className="w-12 h-6 bg-gray-200 rounded"></div>
                          </div>

                          {/* Summary lines */}
                          <div className="space-y-2">
                            <div className="h-3 bg-gray-100 rounded w-full"></div>
                            <div
                              className="h-3 bg-gray-100 rounded"
                              style={{ width: `${70 + i * 3}%` }}
                            ></div>
                          </div>

                          {/* Article count */}
                          <div className="h-4 bg-gray-100 rounded w-32"></div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : marketThemes.length > 0 ? (
                <div className="space-y-2">
                  {marketThemes.map((theme, index) => {
                    const isExpanded = expandedThemeId === theme.themeId;
                    return (
                      <div
                        key={theme.themeId}
                        className="border rounded-lg bg-white hover:shadow-md transition-shadow"
                        style={{ overflow: 'visible' }}
                      >
                        {/* Header - Always Visible */}
                        <div
                          className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                          onClick={() =>
                            setExpandedThemeId(
                              isExpanded ? null : theme.themeId,
                            )
                          }
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3 flex-1">
                              <span className="text-xs font-semibold text-gray-500">
                                #{index + 1}
                              </span>
                              <h3 className="font-semibold text-gray-900 flex-1">
                                {theme.title}
                              </h3>
                              <div className="flex items-center gap-2">
                                <span
                                  className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                                    theme.sentiment === 'bullish'
                                      ? 'bg-green-100 text-green-800'
                                      : theme.sentiment === 'bearish'
                                        ? 'bg-red-100 text-red-800'
                                        : 'bg-gray-100 text-gray-800'
                                  }`}
                                >
                                  {theme.sentiment}
                                </span>
                              </div>
                            </div>
                            <svg
                              className={`w-5 h-5 text-gray-400 transition-transform ${
                                isExpanded ? 'rotate-180' : ''
                              }`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M19 9l-7 7-7-7"
                              />
                            </svg>
                          </div>
                        </div>

                        {/* Expandable Content */}
                        {isExpanded && (
                          <div className="px-4 pb-4 pt-0 border-t border-gray-100">
                            <p className="text-sm text-gray-600 leading-relaxed mb-3">
                              {theme.summary}
                            </p>
                            <div className="flex items-center gap-3 text-xs">
                              <span
                                className="text-gray-500 cursor-help"
                                title="Calculated from article count, source diversity, recency, and keyword relevance."
                              >
                                Score: {theme.score.toFixed(1)}/100
                              </span>
                              <span className="text-gray-500">•</span>
                              <div className="relative">
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    console.log(
                                      'Button clicked, theme_id:',
                                      theme.themeId,
                                    );
                                    console.log(
                                      'Current selectedThemeId:',
                                      selectedThemeId,
                                    );

                                    if (selectedThemeId === theme.themeId) {
                                      setSelectedThemeId(null);
                                    } else {
                                      setSelectedThemeId(theme.themeId);
                                      console.log(
                                        'Set selectedThemeId to:',
                                        theme.themeId,
                                      );
                                      setArticlesLoading(true);
                                      try {
                                        if (!api) return;
                                        console.log(
                                          'Fetching articles for theme:',
                                          theme.themeId,
                                        );
                                        const response =
                                          await api.themeArticles({
                                            themeId: theme.themeId,
                                          });
                                        const data =
                                          typeof response === 'string'
                                            ? JSON.parse(response)
                                            : response;
                                        console.log('Articles received:', data);
                                        setThemeArticles(data.articles || []);
                                      } catch (error) {
                                        console.error(
                                          'Error fetching articles:',
                                          error,
                                        );
                                        setThemeArticles([]);
                                      } finally {
                                        setArticlesLoading(false);
                                      }
                                    }
                                  }}
                                  className="text-blue-600 hover:text-blue-800 hover:underline"
                                >
                                  {theme.articleCount} articles from{' '}
                                  {theme.sources.join(', ')}
                                </button>

                                {/* Popover */}
                                {selectedThemeId === theme.themeId && (
                                  <div
                                    className="absolute right-0 top-full mt-1 w-64 bg-white rounded shadow-lg border border-gray-200 z-50 text-xs"
                                    style={{ zIndex: 9999 }}
                                  >
                                    <div className="px-2 py-1.5 border-b border-gray-200 flex items-center justify-between">
                                      <h4 className="text-xs font-semibold text-gray-900">
                                        Sources
                                      </h4>
                                      <button
                                        onClick={() => setSelectedThemeId(null)}
                                        className="text-gray-400 hover:text-gray-600"
                                      >
                                        <svg
                                          className="w-3 h-3"
                                          fill="none"
                                          stroke="currentColor"
                                          viewBox="0 0 24 24"
                                        >
                                          <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M6 18L18 6M6 6l12 12"
                                          />
                                        </svg>
                                      </button>
                                    </div>
                                    <div className="px-2 py-1.5 max-h-48 overflow-y-auto">
                                      {articlesLoading ? (
                                        <div className="space-y-2">
                                          {[1, 2, 3, 4].map((i) => (
                                            <div
                                              key={i}
                                              className="p-1.5 relative overflow-hidden rounded"
                                            >
                                              {/* Shimmer effect */}
                                              <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>

                                              {/* Title */}
                                              <div
                                                className="h-3 bg-gray-200 rounded mb-1.5"
                                                style={{
                                                  width: `${75 + i * 5}%`,
                                                }}
                                              ></div>

                                              {/* Source and date */}
                                              <div className="flex gap-2">
                                                <div className="h-2 bg-gray-100 rounded w-16"></div>
                                                <div className="h-2 bg-gray-100 rounded w-12"></div>
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      ) : themeArticles.length > 0 ? (
                                        <div className="space-y-1">
                                          {themeArticles.map(
                                            (article: any, idx: number) => (
                                              <a
                                                key={idx}
                                                href={article.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="block p-1.5 rounded hover:bg-blue-50 transition-colors"
                                              >
                                                <div className="flex items-start gap-1.5">
                                                  <svg
                                                    className="w-2.5 h-2.5 text-blue-600 mt-0.5 flex-shrink-0"
                                                    fill="none"
                                                    stroke="currentColor"
                                                    viewBox="0 0 24 24"
                                                  >
                                                    <path
                                                      strokeLinecap="round"
                                                      strokeLinejoin="round"
                                                      strokeWidth={2}
                                                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                                                    />
                                                  </svg>
                                                  <div className="flex-1 min-w-0">
                                                    <p className="text-xs font-medium text-gray-900 hover:text-blue-600 line-clamp-2">
                                                      {article.title}
                                                    </p>
                                                    <p className="text-xs text-gray-500 mt-0.5">
                                                      {article.source}
                                                    </p>
                                                  </div>
                                                </div>
                                              </a>
                                            ),
                                          )}
                                        </div>
                                      ) : (
                                        <p className="text-gray-500 text-center py-2 text-xs">
                                          No articles
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex items-center justify-center h-48 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                  <div className="text-center">
                    <div className="w-16 h-16 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-3">
                      <svg
                        className="w-8 h-8 text-gray-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                        />
                      </svg>
                    </div>
                    <p className="text-gray-500 mb-3">
                      No market themes available
                    </p>
                    <button
                      onClick={fetchMarketThemes}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      Load Themes
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Top 5 Clients - moved to full width below */}

          {/* Right Column: Meetings + Alerts */}
          <div className="flex flex-col gap-4">
            {/* Upcoming Meetings */}
            <div className="bg-white rounded-lg shadow p-4 flex-1">
              <h2 className="text-base font-semibold text-gray-900 mb-3">
                Upcoming Meetings
              </h2>
              <div className="space-y-2">
                {upcomingMeetings.map((meeting) => (
                  <div
                    key={meeting.id}
                    className="p-2.5 bg-blue-50 rounded-lg hover:shadow-md hover:scale-105 transition-all duration-200 cursor-pointer"
                  >
                    <p className="font-medium text-gray-900 text-sm">
                      {meeting.clientName}
                    </p>
                    <p className="text-xs text-gray-600">{meeting.time}</p>
                    <p className="text-xs text-blue-600 mt-0.5">
                      {meeting.type}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Alerts */}
            <div className="bg-white rounded-lg shadow p-4 flex-1">
              <h2 className="text-base font-semibold text-gray-900 mb-3">
                Alerts
              </h2>
              <div className="space-y-2">
                {alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`p-2.5 rounded-lg hover:shadow-md hover:scale-105 transition-all duration-200 cursor-pointer ${
                      alert.type === 'compliance'
                        ? 'bg-red-50 border-l-4 border-red-500'
                        : 'bg-yellow-50 border-l-4 border-yellow-500'
                    }`}
                  >
                    <p className="font-semibold text-gray-900 text-sm">
                      {alert.title}
                    </p>
                    <p className="text-xs text-gray-600 mt-0.5">
                      {alert.message}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Top 5 Clients - Full Width */}
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Top 5 clients by AUM
          </h2>
          {topClientsLoading ? (
            <div className="relative overflow-hidden">
              <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="flex gap-4 py-3">
                    <div className="h-4 bg-gray-200 rounded w-32"></div>
                    <div className="h-4 bg-gray-200 rounded w-24"></div>
                    <div className="h-4 bg-gray-200 rounded w-20"></div>
                    <div className="h-4 bg-gray-200 rounded w-24"></div>
                    <div className="h-4 bg-gray-200 rounded w-16"></div>
                    <div className="h-4 bg-gray-200 rounded w-16"></div>
                    <div className="h-4 bg-gray-200 rounded flex-1"></div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm table-fixed">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="pb-3 pt-3 font-medium w-[18%] align-bottom">
                      Customer Name
                      <span className="block text-[10px] invisible">‎</span>
                    </th>
                    <th className="pb-3 pt-3 font-medium w-[12%] align-bottom">
                      Total AUM
                      <span className="block text-[10px] invisible">‎</span>
                    </th>
                    <th className="pb-3 pt-3 font-medium w-[10%] align-bottom">
                      YTD Perf.
                      <span className="block text-[10px] invisible">‎</span>
                    </th>
                    <th className="pb-3 pt-3 font-medium w-[12%] align-bottom">
                      Client Since
                      <span className="block text-[10px] invisible">‎</span>
                    </th>
                    <th className="pb-3 font-medium w-[10%]">
                      Client Sentiment
                      <span className="block text-[10px] text-blue-600 font-normal">
                        ◆ AI Generated
                      </span>
                    </th>
                    <th className="pb-3 font-medium w-[10%]">
                      Client Report
                      <span className="block text-[10px] text-blue-600 font-normal">
                        ◆ AI Generated
                      </span>
                    </th>
                    <th className="pb-3 font-medium w-[28%]">
                      Next Best Actions
                      <span className="block text-[10px] text-blue-600 font-normal">
                        ◆ AI Generated
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {topClients.map((client) => (
                    <tr
                      key={client.clientId}
                      className="border-b border-gray-100 hover:bg-gray-50 transition"
                    >
                      <td
                        className="py-3 font-medium text-blue-600 cursor-pointer hover:underline"
                        onClick={() =>
                          navigate({ to: `/clients/${client.clientId}` })
                        }
                      >
                        {client.name}
                      </td>
                      <td className="py-3 text-gray-900">
                        $
                        {client.aum >= 1000000
                          ? `${(client.aum / 1000000).toFixed(1)}M`
                          : client.aum.toLocaleString()}
                      </td>
                      <td
                        className={`py-3 font-semibold ${client.ytdPerformance >= 0 ? 'text-emerald-600' : 'text-red-600'}`}
                      >
                        {client.ytdPerformance >= 0 ? '+' : ''}
                        {client.ytdPerformance.toFixed(0)}%
                      </td>
                      <td className="py-3 text-gray-700">
                        {client.clientSince}
                      </td>
                      <td className="py-3 font-semibold text-emerald-600">
                        {client.clientSentiment}
                      </td>
                      <td className="py-3">
                        <ReportCell clientId={client.clientId} api={api} />
                      </td>
                      <td className="py-3 text-gray-700 text-xs">
                        &ldquo;{client.nextBestAction}&rdquo;
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  );
}
