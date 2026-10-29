import { useQuery } from '@tanstack/react-query';
import { PageLayout } from './PageLayout';
import { useRuntimeConfig } from '../hooks/useRuntimeConfig';
import { useAuth } from 'react-oidc-context';

interface Holding {
  ticker: string | null;
  security_name: string | null;
  sector: string | null;
  asset_class: string | null;
  total_shares: number;
  avg_price: number;
  total_value: number;
  total_gain_loss: number;
}

interface Allocation {
  name: string;
  value: number;
  percentage: number;
}

interface PortfolioSummary {
  total_value: number;
  top_holdings: Holding[];
  sector_allocation: Allocation[];
  asset_allocation: Allocation[];
}

export function Portfolio() {
  const runtimeConfig = useRuntimeConfig();
  const auth = useAuth();
  const apiUrl = runtimeConfig?.apis?.Api;
  const token = auth.user?.id_token;

  // Cached portfolio summary: revisiting the page serves cached data instantly
  // (stale-while-revalidate) instead of re-fetching and flashing "Loading..."
  // on every mount.
  const summaryQuery = useQuery<PortfolioSummary>({
    queryKey: ['portfolio-summary'],
    enabled: !!apiUrl,
    queryFn: async () => {
      const r = await fetch(`${apiUrl}portfolio-summary`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      return r.json();
    },
  });
  const summary = summaryQuery.data ?? null;
  const loading = summaryQuery.isLoading;

  const formatCurrency = (val: number) => {
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
    if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
    return `$${val.toFixed(2)}`;
  };

  return (
    <PageLayout title="Portfolio Overview">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-5 border border-gray-100">
          <p className="text-sm text-gray-500">Total Portfolio Value</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">
            {loading ? '...' : formatCurrency(summary?.total_value ?? 0)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-5 border border-gray-100">
          <p className="text-sm text-gray-500">Unique Holdings</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {loading ? '...' : (summary?.top_holdings?.length ?? 0)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-5 border border-gray-100">
          <p className="text-sm text-gray-500">Asset Classes</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {loading ? '...' : (summary?.asset_allocation?.length ?? 0)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Holdings — takes 2 columns */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-5 border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Top Holdings
          </h2>
          {loading ? (
            <p className="text-gray-400">Loading...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 uppercase border-b">
                    <th className="pb-2 pr-4">Ticker</th>
                    <th className="pb-2 pr-4">Name</th>
                    <th className="pb-2 pr-4">Sector</th>
                    <th className="pb-2 pr-4 text-right">Shares</th>
                    <th className="pb-2 pr-4 text-right">Avg Price</th>
                    <th className="pb-2 pr-4 text-right">Total Value</th>
                    <th className="pb-2 text-right">Gain/Loss</th>
                  </tr>
                </thead>
                <tbody>
                  {(summary?.top_holdings ?? []).map((h, i) => (
                    <tr
                      key={i}
                      className="border-b border-gray-50 hover:bg-gray-50"
                    >
                      <td className="py-2.5 pr-4 font-medium text-blue-600">
                        {h.ticker ?? '—'}
                      </td>
                      <td className="py-2.5 pr-4 text-gray-700 max-w-[180px] truncate">
                        {h.security_name ?? '—'}
                      </td>
                      <td className="py-2.5 pr-4 text-gray-500">
                        {h.sector ?? '—'}
                      </td>
                      <td className="py-2.5 pr-4 text-right text-gray-700">
                        {h.total_shares.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })}
                      </td>
                      <td className="py-2.5 pr-4 text-right text-gray-700">
                        ${h.avg_price.toFixed(2)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-medium text-gray-900">
                        {formatCurrency(h.total_value)}
                      </td>
                      <td
                        className={`py-2.5 text-right font-medium ${h.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}
                      >
                        {h.total_gain_loss >= 0 ? '+' : ''}
                        {formatCurrency(Math.abs(h.total_gain_loss))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(summary?.top_holdings ?? []).length === 0 && (
                <p className="text-gray-400 text-center py-8">
                  No holdings data available
                </p>
              )}
            </div>
          )}
        </div>

        {/* Allocations — right column */}
        <div className="space-y-6">
          {/* Sector Allocation */}
          <div className="bg-white rounded-lg shadow p-5 border border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Sector Allocation
            </h2>
            {loading ? (
              <p className="text-gray-400">Loading...</p>
            ) : (
              <div className="space-y-3">
                {(summary?.sector_allocation ?? []).map((s, i) => (
                  <div key={i}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-700">{s.name}</span>
                      <span className="text-gray-500">{s.percentage}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${s.percentage}%` }}
                      />
                    </div>
                  </div>
                ))}
                {(summary?.sector_allocation ?? []).length === 0 && (
                  <p className="text-gray-400 text-sm">No data</p>
                )}
              </div>
            )}
          </div>

          {/* Asset Class Allocation */}
          <div className="bg-white rounded-lg shadow p-5 border border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Asset Allocation
            </h2>
            {loading ? (
              <p className="text-gray-400">Loading...</p>
            ) : (
              <div className="space-y-3">
                {(summary?.asset_allocation ?? []).map((a, i) => (
                  <div key={i}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-700">{a.name}</span>
                      <span className="text-gray-500">{a.percentage}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 rounded-full"
                        style={{ width: `${a.percentage}%` }}
                      />
                    </div>
                  </div>
                ))}
                {(summary?.asset_allocation ?? []).length === 0 && (
                  <p className="text-gray-400 text-sm">No data</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
