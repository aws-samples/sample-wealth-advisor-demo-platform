import { createFileRoute } from '@tanstack/react-router';
import { useClientReport } from '../../../hooks/useClientReport';
import { useEffect } from 'react';

function ClientReportRoute() {
  const { clientId } = Route.useParams();
  const { data: report, isLoading, error } = useClientReport(clientId);

  useEffect(() => {
    if (report?.status === 'complete' && report.presignedUrl) {
      window.location.href = report.presignedUrl;
    }
  }, [report]);

  if (isLoading) {
    return <div>Loading report...</div>;
  }

  if (error) {
    return <div>Error loading report: {String(error)}</div>;
  }

  if (!report) {
    return <div>Report not found</div>;
  }

  if (report.status === 'in_progress') {
    return <div>Report is being generated. Please try again later.</div>;
  }

  if (report.status === 'not_found') {
    return <div>Report not found for this client</div>;
  }

  return <div>Report status: {report.status}</div>;
}

export const Route = createFileRoute('/clients/$clientId/report')({
  component: ClientReportRoute,
});
