import { createFileRoute } from '@tanstack/react-router';
import { ReportsPage } from '../components/Reports';

export const Route = createFileRoute('/reports')({
  component: ReportsPage,
});
