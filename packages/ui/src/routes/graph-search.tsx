import { createFileRoute } from '@tanstack/react-router';
import { GraphSearchPage } from '../components/GraphSearch';

export const Route = createFileRoute('/graph-search')({
  component: GraphSearchPage,
});
