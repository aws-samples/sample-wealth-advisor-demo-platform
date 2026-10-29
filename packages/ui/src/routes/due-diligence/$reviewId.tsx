import { createFileRoute } from '@tanstack/react-router';
import { ReviewDetail } from '../../components/PortfolioDD/ReviewDetail';

export const Route = createFileRoute('/due-diligence/$reviewId')({
  component: ReviewDetail,
});
