import { useParams, useNavigate } from '@tanstack/react-router';
import { useState, useEffect } from 'react';
import { PageLayout } from './PageLayout';
import { useApiClient } from '../hooks/useApiClient';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

import { StockThemes } from '../generated/api/types.gen';

interface Client {
  id: string;
  name: string;
  email: string;
  phone: string;
  segment: string;
  aum: number;
  risk_tolerance: string;
  interaction_sentiment: string;
  client_city: string;
  client_state: string;
  client_created_date: string;
}

interface AUMDataPoint {
  month: string;
  value: number;
}

export function ClientDetails() {
  const { clientId } = useParams({ strict: false });
  const navigate = useNavigate();
  const api = useApiClient();
  const [client, setClient] = useState<Client | null>(null);
  const [clientLoading, setClientLoading] = useState(true);
  const [holdings, setHoldings] = useState<any[]>([]);
  const [holdingsLoading, setHoldingsLoading] = useState(true);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [transactionsLoading, setTransactionsLoading] = useState(true);
  const [holdingsOffset, setHoldingsOffset] = useState(0);
  const [transactionsOffset, setTransactionsOffset] = useState(0);
  const [hasMoreHoldings, setHasMoreHoldings] = useState(true);
  const [hasMoreTransactions, setHasMoreTransactions] = useState(true);
  const [marketThemes, setMarketThemes] = useState<StockThemes[]>([]);
  const [themesLoading, setThemesLoading] = useState(true);
  const [expandedStock, setExpandedStock] = useState<string | null>(null);
  const [expandedThemeId, setExpandedThemeId] = useState<string | null>(null);
  const [selectedThemeId, setSelectedThemeId] = useState<string | null>(null);
  const [themeArticles, setThemeArticles] = useState<any[]>([]);
  const [articlesLoading, setArticlesLoading] = useState(false);
  const [themesStale, setThemesStale] = useState<string | null>(null);
  const [aumData, setAumData] = useState<AUMDataPoint[]>([]);
  const [aumLoading, setAumLoading] = useState(true);
  const [assetAllocation, setAssetAllocation] = useState<any[]>([]);
  const [allocationLoading, setAllocationLoading] = useState(true);
  const [sectorAllocation, setSectorAllocation] = useState<any[]>([]);
  const [reportData, setReportData] = useState<{
    nextBestAction?: string | null;
  } | null>(null);
  const [holdingsSortField, setHoldingsSortField] = useState<string | null>(
    null,
  );
  const [holdingsSortDirection, setHoldingsSortDirection] = useState<
    'asc' | 'desc'
  >('asc');
  const [transactionsSortField, setTransactionsSortField] = useState<
    string | null
  >(null);
  const [transactionsSortDirection, setTransactionsSortDirection] = useState<
    'asc' | 'desc'
  >('asc');

  useEffect(() => {
    if (!clientId || !api) return;

    // Fetch client details
    const fetchClientDetails = async () => {
      setClientLoading(true);
      try {
        const clientData = await api.clientDetails({ clientId });
        const parsedClientData =
          typeof clientData === 'string' ? JSON.parse(clientData) : clientData;
        setClient({
          id: parsedClientData.clientId,
          name: parsedClientData.customerName,
          email: parsedClientData.email,
          phone: parsedClientData.phone,
          segment: parsedClientData.segment,
          aum: parsedClientData.aum,
          risk_tolerance: parsedClientData.riskTolerance,
          interaction_sentiment: parsedClientData.interactionSentiment,
          client_city: parsedClientData.clientCity || '',
          client_state: parsedClientData.clientState || '',
          client_created_date: parsedClientData.clientCreatedDate || '',
        });
      } catch (error) {
        console.error('Error fetching client:', error);
      } finally {
        setClientLoading(false);
      }
    };

    // Fetch holdings
    const fetchHoldings = async () => {
      setHoldingsLoading(true);
      try {
        const holdingsData = await api.clientHoldings({ clientId, limit: 10 });
        const parsedHoldingsData =
          typeof holdingsData === 'string'
            ? JSON.parse(holdingsData)
            : holdingsData;
        setHoldings(parsedHoldingsData.holdings || []);
        setHasMoreHoldings((parsedHoldingsData.holdings || []).length === 10);
      } catch (error) {
        console.error('Error fetching holdings:', error);
      } finally {
        setHoldingsLoading(false);
      }
    };

    // Fetch transactions
    const fetchTransactions = async () => {
      setTransactionsLoading(true);
      try {
        const transactionsData = await api.clientTransactions({
          clientId,
          limit: 10,
        });
        const parsedTransactionsData =
          typeof transactionsData === 'string'
            ? JSON.parse(transactionsData)
            : transactionsData;
        setTransactions(parsedTransactionsData.transactions || []);
        setHasMoreTransactions(
          (parsedTransactionsData.transactions || []).length === 10,
        );
      } catch (error) {
        console.error('Error fetching transactions:', error);
      } finally {
        setTransactionsLoading(false);
      }
    };

    // Fetch portfolio themes (v2 - grouped by stock)
    const fetchThemes = async () => {
      setThemesLoading(true);
      try {
        const data = await api.clientThemes({ clientId, limit: 15 });
        setMarketThemes(data.stockThemes || []);
        setThemesStale(data.staleMessage || null);
        if (data.stockThemes && data.stockThemes.length > 0) {
          setExpandedStock(data.stockThemes[0].ticker);
        }
      } catch (error) {
        console.error('Error fetching themes:', error);
      } finally {
        setThemesLoading(false);
      }
    };

    // Fetch AUM data
    const fetchAumData = async () => {
      setAumLoading(true);
      try {
        const aumDataResponse = await api.clientAum({ clientId, months: 12 });
        const parsedAum =
          typeof aumDataResponse === 'string'
            ? JSON.parse(aumDataResponse)
            : aumDataResponse;
        setAumData(parsedAum.aum_data || []);
      } catch (error) {
        console.error('Error fetching AUM data:', error);
      } finally {
        setAumLoading(false);
      }
    };

    // Fetch asset allocation
    const fetchAllocation = async () => {
      setAllocationLoading(true);
      try {
        const allocationData = await api.clientAssetAllocation({ clientId });
        const parsedAllocation =
          typeof allocationData === 'string'
            ? JSON.parse(allocationData)
            : allocationData;
        if (parsedAllocation.success && parsedAllocation.allocations) {
          setAssetAllocation(parsedAllocation.allocations);
        }
        setSectorAllocation([
          { name: 'Technology', value: 30, amount: 850000 },
          { name: 'Financials', value: 25, amount: 700000 },
          { name: 'Consumer', value: 20, amount: 560000 },
          { name: 'Healthcare', value: 15, amount: 420000 },
        ]);
      } catch (error) {
        console.error('Error fetching allocation:', error);
      } finally {
        setAllocationLoading(false);
      }
    };

    // Execute all fetches in parallel
    fetchClientDetails();
    fetchHoldings();
    fetchTransactions();
    fetchThemes();
    fetchAumData();
    fetchAllocation();
  }, [clientId, api]);

  // Fetch report data on mount to get the AI-generated Next Best Action
  useEffect(() => {
    if (!clientId || !api) return;
    api
      .clientReport({ clientId })
      .then((report) => setReportData(report))
      .catch((e) => console.error('Failed to fetch report data:', e));
  }, [clientId, api]);

  const handleHoldingsSort = (field: string) => {
    if (holdingsSortField === field) {
      setHoldingsSortDirection(
        holdingsSortDirection === 'asc' ? 'desc' : 'asc',
      );
    } else {
      setHoldingsSortField(field);
      setHoldingsSortDirection('asc');
    }
  };

  const handleTransactionsSort = (field: string) => {
    if (transactionsSortField === field) {
      setTransactionsSortDirection(
        transactionsSortDirection === 'asc' ? 'desc' : 'asc',
      );
    } else {
      setTransactionsSortField(field);
      setTransactionsSortDirection('asc');
    }
  };

  const sortedHoldings = [...holdings].sort((a, b) => {
    if (!holdingsSortField) return 0;
    const aVal = a[holdingsSortField];
    const bVal = b[holdingsSortField];
    const modifier = holdingsSortDirection === 'asc' ? 1 : -1;
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return (aVal - bVal) * modifier;
    }
    return String(aVal).localeCompare(String(bVal)) * modifier;
  });

  const sortedTransactions = [...transactions].sort((a, b) => {
    if (!transactionsSortField) return 0;
    const aVal = a[transactionsSortField];
    const bVal = b[transactionsSortField];
    const modifier = transactionsSortDirection === 'asc' ? 1 : -1;
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return (aVal - bVal) * modifier;
    }
    return String(aVal).localeCompare(String(bVal)) * modifier;
  });

  return (
    <PageLayout title="Client Details">
      <div className="flex-1 overflow-auto p-6 space-y-4">
        <button
          onClick={() => navigate({ to: '/clients' })}
          className="mb-6 text-blue-600 hover:text-blue-800 font-medium flex items-center gap-2"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back
        </button>

        {/* Client Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          {clientLoading ? (
            <div className="relative overflow-hidden">
              <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
              <div className="space-y-4">
                <div className="h-8 bg-gray-200 rounded w-48"></div>
                <div className="flex gap-4">
                  <div className="h-4 bg-gray-100 rounded w-32"></div>
                  <div className="h-4 bg-gray-100 rounded w-32"></div>
                </div>
                <div className="flex gap-4">
                  <div className="h-4 bg-gray-100 rounded w-24"></div>
                  <div className="h-4 bg-gray-100 rounded w-24"></div>
                  <div className="h-4 bg-gray-100 rounded w-24"></div>
                </div>
              </div>
            </div>
          ) : client ? (
            <div className="flex items-center justify-between mb-4">
              <div>
                <h1 className="text-2xl font-bold text-gray-900 mb-1">
                  {client.name}
                </h1>
                <div className="flex items-center gap-4 text-sm text-gray-600">
                  <a
                    href={`mailto:${client.email}`}
                    className="flex items-center gap-1 hover:text-blue-600 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                      />
                    </svg>
                    {client.email}
                  </a>
                  <span className="flex items-center gap-1">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                      />
                    </svg>
                    {client.phone}
                  </span>
                  {(client.client_city || client.client_state) && (
                    <span className="flex items-center gap-1">
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                      </svg>
                      {[client.client_city, client.client_state]
                        .filter(Boolean)
                        .join(', ')}
                    </span>
                  )}
                  {client.client_created_date && (
                    <span className="flex items-center gap-1">
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                        />
                      </svg>
                      Client since{' '}
                      {new Date(
                        client.client_created_date + 'T00:00:00',
                      ).toLocaleDateString('en-US', {
                        month: 'short',
                        year: 'numeric',
                      })}
                    </span>
                  )}
                  <span className="px-2 py-1 bg-gray-100 rounded text-xs font-medium">
                    {client.segment}
                  </span>
                  <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs font-medium">
                    {client.risk_tolerance}
                  </span>
                </div>
              </div>
              <button
                onClick={() => {
                  const params = new URLSearchParams({
                    to: client.email,
                    subject: `Meeting with ${client.name}`,
                  });
                  window.open(
                    `https://outlook.office.com/calendar/action/compose?${params.toString()}`,
                    '_blank',
                  );
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              >
                Schedule Meeting
              </button>
            </div>
          ) : (
            <div className="text-center py-4 text-gray-500">
              Client not found
            </div>
          )}
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-6 gap-4 mb-6">
          {clientLoading ? (
            <>
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div
                  key={i}
                  className="bg-white rounded-lg shadow p-4 relative overflow-hidden"
                >
                  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                  <div className="space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-16 mx-auto"></div>
                    <div className="h-6 bg-gray-200 rounded w-20 mx-auto"></div>
                  </div>
                </div>
              ))}
            </>
          ) : client ? (
            <>
              {/* Gold Badge */}
              <div className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-pointer">
                <svg
                  className="w-8 h-8 text-yellow-500 mb-1"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                <p className="text-xs font-semibold text-gray-900">Gold</p>
              </div>

              {/* AUM */}
              <div className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center text-center hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-pointer">
                <p className="text-xs text-gray-500 mb-1">AUM</p>
                <p className="text-xl font-bold text-blue-600">
                  $
                  {client.aum >= 1000000
                    ? `${(client.aum / 1000000).toFixed(1)}M`
                    : client.aum.toLocaleString()}
                </p>
              </div>

              {/* Interaction Sentiment */}
              <div className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center text-center hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-pointer">
                <p className="text-xs text-gray-500 mb-1">
                  Interaction Sentiment
                </p>
                <p className="text-xl font-bold text-green-600">
                  {client.interaction_sentiment || 'N/A'}
                </p>
              </div>

              {/* Next Meeting */}
              <div className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center text-center hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-pointer">
                <p className="text-xs text-gray-500 mb-1">Next Meeting</p>
                <p className="text-sm font-semibold text-gray-900">
                  Monday, January 20, 2025
                </p>
                <button
                  onClick={async () => {
                    if (!api || !client) {
                      console.error('API or client not available', {
                        api: !!api,
                        client: !!client,
                      });
                      return;
                    }
                    try {
                      const report = await api.clientReport({
                        clientId: client.id,
                      });
                      if (report.status === 'complete' && report.presignedUrl) {
                        window.open(report.presignedUrl, '_blank');
                      } else {
                        alert(`Report status: ${report.status}`);
                      }
                    } catch (e) {
                      console.error('Failed to fetch report:', e);
                      alert(
                        'Failed to generate report. Check console for details.',
                      );
                    }
                  }}
                  className="text-xs text-blue-600 hover:text-blue-700 mt-1 cursor-pointer"
                >
                  📋 View customer report
                </button>
                <p className="text-[10px] text-blue-600 mt-0.5">
                  ✨ AI Generated
                </p>
              </div>

              {/* Next Best Actions */}
              <div className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center text-center hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-pointer">
                <p className="text-xs text-gray-500 mb-1">Next Best Actions</p>
                <p className="text-xs text-gray-700">
                  {reportData?.nextBestAction || 'No recommendation available'}
                </p>
              </div>
            </>
          ) : null}
        </div>

        {/* Row 1: Market Summary + Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* US Market Summary - 2/3 width */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow p-6 h-full">
              <h2 className="text-lg font-bold text-gray-900 mb-6 pb-4 border-b-2 border-blue-500">
                Portfolio Market Themes
              </h2>
              {themesStale && (
                <div className="mb-4 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 flex items-center gap-2">
                  <span>⚠️</span> {themesStale}
                </div>
              )}
              <div className="space-y-2">
                {themesLoading ? (
                  <>
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="border rounded-lg bg-white p-4 relative overflow-hidden"
                      >
                        <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                        <div className="space-y-3">
                          <div className="flex items-center gap-2">
                            <div className="h-5 bg-gray-200 rounded flex-1"></div>
                            <div className="w-16 h-6 bg-gray-200 rounded-full"></div>
                          </div>
                          <div className="h-3 bg-gray-100 rounded w-full"></div>
                          <div className="h-3 bg-gray-100 rounded w-3/4"></div>
                        </div>
                      </div>
                    ))}
                  </>
                ) : (
                  marketThemes.map((stock) => {
                    const isStockExpanded = expandedStock === stock.ticker;
                    return (
                      <div
                        key={stock.ticker}
                        className="border rounded-lg bg-white"
                      >
                        <div
                          className="p-3 cursor-pointer hover:bg-gray-50 transition-colors flex items-center justify-between"
                          onClick={() =>
                            setExpandedStock(
                              isStockExpanded ? null : stock.ticker,
                            )
                          }
                        >
                          <div className="flex items-center gap-3">
                            <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-sm font-bold rounded">
                              {stock.ticker}
                            </span>
                            <span className="text-sm text-gray-600">
                              {stock.securityName}
                            </span>
                            {stock.aumValue > 0 && (
                              <span className="text-xs text-gray-400">
                                ${(stock.aumValue / 1000).toFixed(0)}K
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500">
                              {stock.themes.length} theme
                              {stock.themes.length !== 1 ? 's' : ''}
                            </span>
                            <svg
                              className={`w-4 h-4 text-gray-400 transition-transform ${isStockExpanded ? 'rotate-180' : ''}`}
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
                        {isStockExpanded && (
                          <div className="border-t border-gray-100 px-3 pb-3 space-y-2">
                            {stock.themes.map((theme) => {
                              const isThemeExpanded =
                                expandedThemeId === theme.themeId;
                              return (
                                <div
                                  key={theme.themeId}
                                  className="border rounded bg-gray-50"
                                >
                                  <div
                                    className="p-3 cursor-pointer hover:bg-gray-100 transition-colors"
                                    onClick={() =>
                                      setExpandedThemeId(
                                        isThemeExpanded ? null : theme.themeId,
                                      )
                                    }
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className="flex-1">
                                        <h4 className="text-sm font-medium text-gray-900">
                                          {theme.title}
                                        </h4>
                                      </div>
                                      <span
                                        className={`ml-2 px-2 py-0.5 text-xs font-medium rounded-full ${
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
                                  {isThemeExpanded && (
                                    <div className="px-3 pb-3 border-t border-gray-200">
                                      <p className="text-sm text-gray-600 leading-relaxed mt-2">
                                        {theme.summary}
                                      </p>
                                      {theme.relevanceReasoning && (
                                        <p className="text-xs text-gray-500 mt-2 italic">
                                          {theme.relevanceReasoning}
                                        </p>
                                      )}
                                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                                        <span
                                          className="cursor-help"
                                          title="Combines market theme score with relevance to client holdings."
                                        >
                                          Score:{' '}
                                          {theme.combinedScore.toFixed(1)}
                                        </span>
                                        {theme.articleCount > 0 && (
                                          <span>
                                            • {theme.articleCount} articles
                                          </span>
                                        )}
                                        {theme.sources.length > 0 && (
                                          <>
                                            <span>•</span>
                                            <div className="relative inline-block">
                                              <button
                                                onClick={(e) => {
                                                  e.stopPropagation();
                                                  if (
                                                    selectedThemeId ===
                                                    theme.themeId
                                                  ) {
                                                    setSelectedThemeId(null);
                                                  } else {
                                                    setSelectedThemeId(
                                                      theme.themeId,
                                                    );
                                                    setArticlesLoading(true);
                                                    api
                                                      .themeArticles({
                                                        themeId: theme.themeId,
                                                      })
                                                      .then((resp) => {
                                                        const data =
                                                          typeof resp ===
                                                          'string'
                                                            ? JSON.parse(resp)
                                                            : resp;
                                                        setThemeArticles(
                                                          data.articles || [],
                                                        );
                                                      })
                                                      .catch(() =>
                                                        setThemeArticles([]),
                                                      )
                                                      .finally(() =>
                                                        setArticlesLoading(
                                                          false,
                                                        ),
                                                      );
                                                  }
                                                }}
                                                className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                                              >
                                                {theme.articleCount > 0 &&
                                                  `${theme.articleCount} `}
                                                articles from{' '}
                                                {theme.sources.join(', ')}
                                              </button>
                                              {selectedThemeId ===
                                                theme.themeId && (
                                                <div
                                                  className="absolute left-0 top-full mt-1 w-64 bg-white rounded shadow-lg border border-gray-200 z-50 text-xs"
                                                  onClick={(e) =>
                                                    e.stopPropagation()
                                                  }
                                                >
                                                  <div className="px-2 py-1.5 border-b border-gray-200 flex items-center justify-between">
                                                    <h4 className="text-xs font-semibold text-gray-900">
                                                      Sources
                                                    </h4>
                                                    <button
                                                      onClick={() =>
                                                        setSelectedThemeId(null)
                                                      }
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
                                                        {[1, 2, 3].map((i) => (
                                                          <div
                                                            key={i}
                                                            className="p-1.5 rounded"
                                                          >
                                                            <div
                                                              className="h-3 bg-gray-200 rounded mb-1.5"
                                                              style={{
                                                                width: `${75 + i * 5}%`,
                                                              }}
                                                            ></div>
                                                            <div className="h-2 bg-gray-100 rounded w-16"></div>
                                                          </div>
                                                        ))}
                                                      </div>
                                                    ) : themeArticles.length >
                                                      0 ? (
                                                      <div className="space-y-1">
                                                        {themeArticles.map(
                                                          (
                                                            article: any,
                                                            idx: number,
                                                          ) => (
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
                                                                    strokeWidth={
                                                                      2
                                                                    }
                                                                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                                                                  />
                                                                </svg>
                                                                <div className="flex-1 min-w-0">
                                                                  <p className="text-xs font-medium text-gray-900 hover:text-blue-600 line-clamp-2">
                                                                    {
                                                                      article.title
                                                                    }
                                                                  </p>
                                                                  <p className="text-xs text-gray-500 mt-0.5">
                                                                    {
                                                                      article.source
                                                                    }
                                                                  </p>
                                                                </div>
                                                              </div>
                                                            </a>
                                                          ),
                                                        )}
                                                      </div>
                                                    ) : (
                                                      <p className="text-gray-500 text-center py-2 text-xs">
                                                        No articles found
                                                      </p>
                                                    )}
                                                  </div>
                                                </div>
                                              )}
                                            </div>
                                          </>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* Alerts and Events - 1/3 width */}
          <div>
            <div className="bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow p-6 h-full">
              <h2 className="text-lg font-bold text-gray-900 mb-6 pb-4 border-b-2 border-blue-500">
                Alerts & Events
              </h2>
              <div className="space-y-3">
                <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded-r hover:shadow-md hover:scale-105 transition-all duration-200 cursor-pointer">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-2 h-2 rounded-full bg-red-500 mt-1.5"></div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-gray-900 mb-1">
                        AML & Suspicious Activity
                      </p>
                      <p className="text-xs text-gray-600">
                        Large cash deposit detected
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-amber-50 border-l-4 border-amber-500 p-3 rounded-r hover:shadow-md hover:scale-105 transition-all duration-200 cursor-pointer">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-2 h-2 rounded-full bg-amber-500 mt-1.5"></div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-gray-900 mb-1">
                        Market Event
                      </p>
                      <p className="text-xs text-gray-600">
                        China Research downgrade on US listings
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-blue-50 border-l-4 border-blue-500 p-3 rounded-r hover:shadow-md hover:scale-105 transition-all duration-200 cursor-pointer">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-2 h-2 rounded-full bg-blue-500 mt-1.5"></div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-gray-900 mb-1">
                        Scheduled Review
                      </p>
                      <p className="text-xs text-gray-600">
                        Annual portfolio review on 2/14/2026 at 3:00 PM
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Row 2: AUM + Asset Allocation + Sector Allocation */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          {/* AUM Chart */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow p-6">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900">
                Assets Under Management
              </h2>
              <span className="text-xs font-medium text-red-600 bg-red-50 px-2 py-1 rounded">
                -4.5%
              </span>
            </div>
            <div className="mb-6">
              <div className="text-3xl font-bold text-gray-900 mb-1">
                ${client?.aum.toLocaleString()}
              </div>
              <p className="text-sm text-gray-500">Last 12 months</p>
            </div>
            <div className="h-48">
              {aumLoading ? (
                <div className="relative h-full bg-gray-50 rounded overflow-hidden">
                  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                  <div className="p-4 space-y-3">
                    <div className="h-4 bg-gray-200 rounded w-32"></div>
                    <div className="h-32 bg-gray-200 rounded"></div>
                  </div>
                </div>
              ) : aumData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={aumData.map((d) => ({
                      month: new Date(d.month + '-01').toLocaleDateString(
                        'en-US',
                        { month: 'short', year: '2-digit' },
                      ),
                      value: d.value / 1000000,
                    }))}
                    margin={{ top: 10, right: 30, left: -20, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient
                        id="colorClientAUM"
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
                      style={{ fontSize: '11px' }}
                      interval="preserveStartEnd"
                      angle={-45}
                      textAnchor="end"
                      height={60}
                    />
                    <YAxis
                      stroke="#6b7280"
                      style={{ fontSize: '13px' }}
                      width={45}
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
                      labelFormatter={(label) => `${label}`}
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke="#8b5cf6"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#colorClientAUM)"
                      dot={{ fill: '#8b5cf6', r: 4.5 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                  No AUM data available
                </div>
              )}
            </div>
          </div>

          {/* Asset Allocation */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-4 pb-3 border-b border-gray-100">
              Target Asset Allocation
            </h2>
            <div className="h-64">
              {allocationLoading ? (
                <div className="relative h-full bg-gray-50 rounded overflow-hidden">
                  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                  <div className="p-4 space-y-3">
                    <div className="h-4 bg-gray-200 rounded w-32"></div>
                    <div className="h-48 bg-gray-200 rounded"></div>
                  </div>
                </div>
              ) : assetAllocation.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={assetAllocation}
                    margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="name"
                      stroke="#6b7280"
                      style={{ fontSize: '13px' }}
                    />
                    <YAxis
                      stroke="#6b7280"
                      style={{ fontSize: '13px' }}
                      label={{
                        value: 'Allocation %',
                        angle: -90,
                        position: 'insideLeft',
                        style: { fontSize: '13px' },
                      }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'white',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                        fontSize: '13px',
                      }}
                      formatter={(value) => [
                        `${Number(value ?? 0).toFixed(1)}%`,
                        'Target',
                      ]}
                    />
                    <Bar dataKey="value" fill="#8b5cf6" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                  No allocation data available
                </div>
              )}
            </div>
          </div>

          {/* Sector Allocation */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-4 pb-3 border-b border-gray-100">
              Sector Allocation
            </h2>
            <div className="space-y-3">
              {sectorAllocation.map((item, index) => (
                <div
                  key={item.name}
                  className="py-1 px-2 rounded hover:bg-gray-50 hover:shadow-sm transition-all duration-200 cursor-pointer"
                >
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-gray-700 font-medium">
                      {item.name}
                    </span>
                    <div className="text-right">
                      <div className="font-semibold text-gray-900">
                        ${item.amount.toLocaleString()}
                      </div>
                      <div className="text-xs text-gray-500">{item.value}%</div>
                    </div>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2.5">
                    <div
                      className="h-2.5 rounded-full transition-all"
                      style={{
                        width: `${item.value}%`,
                        backgroundColor: [
                          '#f59e0b',
                          '#3b82f6',
                          '#10b981',
                          '#ef4444',
                        ][index % 4],
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Row 3: Holdings Section */}

        {/* Holdings Section */}
        <div className="bg-white rounded-lg shadow mb-6 mt-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Portfolio Holdings
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th
                    onClick={() => handleHoldingsSort('ticker')}
                    className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-1">
                      Symbol
                      {holdingsSortField === 'ticker' && (
                        <span>
                          {holdingsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleHoldingsSort('companyName')}
                    className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-1">
                      Company
                      {holdingsSortField === 'companyName' && (
                        <span>
                          {holdingsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleHoldingsSort('shares')}
                    className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center justify-end gap-1">
                      Shares
                      {holdingsSortField === 'shares' && (
                        <span>
                          {holdingsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleHoldingsSort('currentPrice')}
                    className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center justify-end gap-1">
                      Price
                      {holdingsSortField === 'currentPrice' && (
                        <span>
                          {holdingsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleHoldingsSort('currentValue')}
                    className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center justify-end gap-1">
                      Value
                      {holdingsSortField === 'currentValue' && (
                        <span>
                          {holdingsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleHoldingsSort('gainLoss')}
                    className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center justify-end gap-1">
                      Change
                      {holdingsSortField === 'gainLoss' && (
                        <span>
                          {holdingsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {holdingsLoading ? (
                  <tr>
                    <td colSpan={6} className="relative">
                      <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                      <div className="space-y-0">
                        {[1, 2, 3, 4, 5].map((i) => (
                          <div
                            key={i}
                            className="flex gap-4 px-6 py-4 border-b border-gray-100"
                          >
                            <div className="h-4 bg-gray-200 rounded w-16"></div>
                            <div className="h-4 bg-gray-200 rounded flex-1"></div>
                            <div className="h-4 bg-gray-200 rounded w-20"></div>
                            <div className="h-4 bg-gray-200 rounded w-20"></div>
                            <div className="h-4 bg-gray-200 rounded w-24"></div>
                            <div className="h-4 bg-gray-200 rounded w-16"></div>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                ) : sortedHoldings.length > 0 ? (
                  sortedHoldings.map((holding, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-6 py-4 font-bold text-gray-900">
                        {holding.ticker}
                      </td>
                      <td className="px-6 py-4 text-gray-700">
                        {holding.companyName}
                      </td>
                      <td className="px-6 py-4 text-right font-medium text-gray-900">
                        {(holding.shares ?? 0).toFixed(3)}
                      </td>
                      <td className="px-6 py-4 text-right font-medium text-gray-900">
                        ${(holding.currentPrice ?? 0).toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-right font-bold text-gray-900">
                        $
                        {(holding.currentValue ?? 0).toLocaleString('en-US', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </td>
                      <td
                        className={`px-6 py-4 text-right font-bold ${(holding.unrealizedGainLoss ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}
                      >
                        {(holding.unrealizedGainLoss ?? 0) >= 0 ? '+' : ''}$
                        {Math.abs(
                          holding.unrealizedGainLoss ?? 0,
                        ).toLocaleString('en-US', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-6 py-8 text-center text-gray-500"
                    >
                      No holdings found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {hasMoreHoldings && (
            <div className="px-6 pb-4 flex items-center justify-center gap-2">
              {holdingsOffset > 0 && (
                <button
                  onClick={async () => {
                    if (!api) return;
                    const newOffset = Math.max(0, holdingsOffset - 20);
                    const data = await api.clientHoldings({
                      clientId: clientId as string,
                      limit: 20,
                      offset: newOffset,
                    });
                    setHoldings(data.holdings || []);
                    setHoldingsOffset(newOffset);
                    setHasMoreHoldings((data.holdings || []).length === 20);
                  }}
                  className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
                >
                  ← Previous
                </button>
              )}
              <span className="text-sm text-gray-600">
                Page {Math.floor(holdingsOffset / 10) + 1}
              </span>
              <button
                onClick={async () => {
                  if (!api) return;
                  const newOffset = holdingsOffset + 20;
                  const data = await api.clientHoldings({
                    clientId: clientId as string,
                    limit: 20,
                    offset: newOffset,
                  });
                  const newHoldings = data.holdings || [];
                  setHoldings([...holdings, ...newHoldings]);
                  setHoldingsOffset(newOffset);
                  setHasMoreHoldings(newHoldings.length === 20);
                }}
                className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
              >
                Next →
              </button>
            </div>
          )}
        </div>

        {/* Transaction History */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Transaction History
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th
                    onClick={() => handleTransactionsSort('transactionDate')}
                    className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-1">
                      Date
                      {transactionsSortField === 'transactionDate' && (
                        <span>
                          {transactionsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleTransactionsSort('transaction_type')}
                    className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-1">
                      Type
                      {transactionsSortField === 'transaction_type' && (
                        <span>
                          {transactionsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleTransactionsSort('ticker')}
                    className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-1">
                      Description
                      {transactionsSortField === 'ticker' && (
                        <span>
                          {transactionsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleTransactionsSort('amount')}
                    className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center justify-end gap-1">
                      Amount
                      {transactionsSortField === 'amount' && (
                        <span>
                          {transactionsSortDirection === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                  <th className="px-6 py-4 text-right text-xs font-bold text-gray-700 uppercase">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {transactionsLoading ? (
                  <tr>
                    <td colSpan={5} className="relative">
                      <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent"></div>
                      <div className="space-y-0">
                        {[1, 2, 3, 4, 5].map((i) => (
                          <div
                            key={i}
                            className="flex gap-4 px-6 py-4 border-b border-gray-100"
                          >
                            <div className="h-4 bg-gray-200 rounded w-24"></div>
                            <div className="h-4 bg-gray-200 rounded w-20"></div>
                            <div className="h-4 bg-gray-200 rounded flex-1"></div>
                            <div className="h-4 bg-gray-200 rounded w-24"></div>
                            <div className="h-4 bg-gray-200 rounded w-20"></div>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                ) : sortedTransactions.length > 0 ? (
                  sortedTransactions.map((txn, index) => {
                    const isDeposit =
                      txn.transaction_type?.toLowerCase().includes('deposit') ||
                      txn.transaction_type
                        ?.toLowerCase()
                        .includes('contribution');
                    const isBuy = txn.transaction_type
                      ?.toLowerCase()
                      .includes('buy');
                    const description = txn.ticker
                      ? `${txn.ticker} - ${txn.quantity || 0} shares`
                      : txn.transaction_type;

                    return (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm font-medium text-gray-700">
                          {txn.transactionDate
                            ? new Date(
                                txn.transactionDate + 'T00:00:00',
                              ).toLocaleDateString('en-US')
                            : 'N/A'}
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`px-3 py-1 rounded-full text-xs font-semibold ${
                              isDeposit
                                ? 'bg-green-100 text-green-700'
                                : isBuy
                                  ? 'bg-blue-100 text-blue-700'
                                  : 'bg-gray-100 text-gray-700'
                            }`}
                          >
                            {txn.transaction_type}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-700">
                          {description}
                        </td>
                        <td
                          className={`px-6 py-4 text-right text-sm font-bold ${
                            (txn.amount || 0) >= 0
                              ? 'text-green-600'
                              : 'text-red-600'
                          }`}
                        >
                          {(txn.amount || 0) >= 0 ? '+' : ''}$
                          {Math.abs(txn.amount || 0).toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </td>
                        <td className="px-6 py-4 text-right text-sm font-bold text-gray-900">
                          {txn.status}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-6 py-8 text-center text-gray-500"
                    >
                      No transactions found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {hasMoreTransactions && (
            <div className="px-6 pb-4 flex items-center justify-center gap-2">
              {transactionsOffset > 0 && (
                <button
                  onClick={async () => {
                    if (!api) return;
                    const newOffset = Math.max(0, transactionsOffset - 20);
                    const data = await api.clientTransactions({
                      clientId: clientId as string,
                      limit: 20,
                      offset: newOffset,
                    });
                    setTransactions(data.transactions || []);
                    setTransactionsOffset(newOffset);
                    setHasMoreTransactions(
                      (data.transactions || []).length === 20,
                    );
                  }}
                  className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
                >
                  ← Previous
                </button>
              )}
              <span className="text-sm text-gray-600">
                Page {Math.floor(transactionsOffset / 10) + 1}
              </span>
              <button
                onClick={async () => {
                  if (!api) return;
                  const newOffset = transactionsOffset + 20;
                  const data = await api.clientTransactions({
                    clientId: clientId as string,
                    limit: 20,
                    offset: newOffset,
                  });
                  const newTransactions = data.transactions || [];
                  setTransactions([...transactions, ...newTransactions]);
                  setTransactionsOffset(newOffset);
                  setHasMoreTransactions(newTransactions.length === 20);
                }}
                className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
              >
                Next →
              </button>
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  );
}
