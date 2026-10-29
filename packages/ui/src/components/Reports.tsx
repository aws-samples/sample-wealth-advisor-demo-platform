import { useNavigate } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { PageLayout } from './PageLayout';
import { useApi } from '../hooks/useApi';
import { ReportCell } from './ReportCell';

export function ReportsPage() {
  const navigate = useNavigate();
  const apiOptions = useApi();

  const clientsQuery = useQuery(
    apiOptions.clients.queryOptions({ limit: 100 }),
  );
  const reportsSummaryQuery = useQuery({
    ...apiOptions.reportsSummary.queryOptions(),
    retry: false,
  });

  const clients = clientsQuery.data?.clients ?? [];
  const clientsWithReports = new Set(
    reportsSummaryQuery.data?.clientsWithReports ?? [],
  );
  const loading = clientsQuery.isLoading;

  const totalClients = clients.length;
  const reportsAvailable = clientsWithReports.size;
  const pendingGeneration = Math.max(0, totalClients - reportsAvailable);

  return (
    <PageLayout title="Reports">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500">Total Clients</p>
          <p className="text-3xl font-bold mt-1 text-blue-600">
            {totalClients}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500">Reports Available</p>
          <p className="text-3xl font-bold mt-1 text-green-600">
            {reportsAvailable}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500">Pending Generation</p>
          <p className="text-3xl font-bold mt-1 text-amber-600">
            {pendingGeneration}
          </p>
        </div>
      </div>

      {/* Client reports table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">Client Reports</h2>
        </div>
        {loading ? (
          <div className="px-6 py-12 text-center text-gray-400">
            Loading clients...
          </div>
        ) : clients.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-400">
            No clients found.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-gray-100">
                <th className="px-6 py-3">Customer Name</th>
                <th className="px-6 py-3">Segment</th>
                <th className="px-6 py-3">AUM</th>
                <th className="px-6 py-3">YTD Perf.</th>
                <th className="px-6 py-3">Report</th>
                <th className="px-6 py-3">Next Best Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {clients.map((c) => (
                <tr
                  key={c.clientId}
                  className="hover:bg-gray-50 transition-colors"
                >
                  <td className="px-6 py-4">
                    <button
                      onClick={() =>
                        navigate({
                          to: '/clients/$clientId',
                          params: { clientId: c.clientId },
                        })
                      }
                      className="text-blue-600 hover:underline font-medium"
                    >
                      {c.customerName}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    <span className="px-2 py-1 rounded-full text-xs bg-gray-100">
                      {c.segment}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-900 font-medium">
                    ${(c.aum / 1000000).toFixed(2)}M
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={
                        c.ytdPerf >= 0 ? 'text-green-600' : 'text-red-600'
                      }
                    >
                      {c.ytdPerf >= 0 ? '+' : ''}
                      {c.ytdPerf?.toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <ReportCell
                      clientId={c.clientId}
                      hasReport={clientsWithReports.has(c.clientId)}
                    />
                  </td>
                  <td className="px-6 py-4 text-gray-500 text-xs max-w-[200px] truncate">
                    {c.nextBestAction || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </PageLayout>
  );
}
