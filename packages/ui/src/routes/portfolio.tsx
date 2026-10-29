import { createFileRoute } from '@tanstack/react-router';
import { Portfolio } from '../components/Portfolio';

export const Route = createFileRoute('/portfolio')({
  component: Portfolio,
});
