import { createFileRoute } from '@tanstack/react-router';
import { PortfolioDDDashboard } from '../../components/PortfolioDD/Dashboard';

export const Route = createFileRoute('/due-diligence/')({
  component: PortfolioDDDashboard,
});
