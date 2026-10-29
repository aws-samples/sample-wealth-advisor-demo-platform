import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '../hooks/useApi';

interface ReportCellProps {
  clientId: string;
  hasReport?: boolean;
}

export function ReportCell({ clientId, hasReport }: ReportCellProps) {
  const apiOptions = useApi();
  const queryClient = useQueryClient();

  const reportQuery = useQuery({
    ...apiOptions.clientReport.queryOptions({ clientId }),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.status === 'pending' ? 3000 : false,
  });

  const generateMutation = useMutation({
    ...apiOptions.generateReport.mutationOptions({
      onSuccess: (data) => {
        if (data.presignedUrl) {
          window.open(data.presignedUrl, '_blank');
        }
        queryClient.setQueryData(
          apiOptions.clientReport.queryKey({ clientId }),
          data,
        );
        queryClient.invalidateQueries(
          apiOptions.clientReport.queryFilter({ clientId }),
        );
        queryClient.invalidateQueries(apiOptions.reportsSummary.queryFilter());
      },
    }),
  });

  const handleClick = () => {
    const report = reportQuery.data;
    if (report?.status === 'complete' && report.presignedUrl) {
      window.open(report.presignedUrl, '_blank');
    } else {
      generateMutation.mutate({ clientId });
    }
  };

  const isGenerating =
    generateMutation.isPending || reportQuery.data?.status === 'pending';
  const isLoading = reportQuery.isLoading;
  const reportAvailable = reportQuery.data
    ? reportQuery.data.status === 'complete' && !!reportQuery.data.presignedUrl
    : (hasReport ?? false);

  if (isLoading)
    return <span className="text-xs text-gray-400">Checking...</span>;
  if (isGenerating)
    return (
      <span className="text-xs text-amber-600 animate-pulse">
        Generating...
      </span>
    );
  if (generateMutation.isError)
    return (
      <button
        onClick={handleClick}
        className="text-xs text-red-500 hover:text-red-700 font-medium"
      >
        Retry
      </button>
    );
  if (reportAvailable) {
    return (
      <span className="flex items-center gap-2">
        <button
          onClick={() => window.open(reportQuery.data!.presignedUrl!, '_blank')}
          className="text-xs font-medium text-blue-600 hover:text-blue-700"
        >
          View Report
        </button>
        <button
          onClick={() => generateMutation.mutate({ clientId })}
          className="text-xs text-gray-400 hover:text-amber-600"
          title="Regenerate report"
        >
          ↻
        </button>
      </span>
    );
  }

  return (
    <button
      onClick={handleClick}
      className="text-xs font-medium text-amber-600 hover:text-amber-700"
    >
      Generate Report
    </button>
  );
}
