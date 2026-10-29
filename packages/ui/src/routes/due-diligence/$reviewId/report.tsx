import { createFileRoute } from '@tanstack/react-router';
import { ReportViewer } from '../../../components/PortfolioDD/ReportViewer';

export const Route = createFileRoute('/due-diligence/$reviewId/report')({
  component: ReportViewer,
});
