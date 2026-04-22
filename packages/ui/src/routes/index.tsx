import { createFileRoute } from '@tanstack/react-router';
import { AdvisorDashboard } from '../components/AdvisorDashboard';

export const Route = createFileRoute('/')({
  component: AdvisorDashboard,
});
