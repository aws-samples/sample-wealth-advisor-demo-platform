import { createFileRoute } from '@tanstack/react-router';
import { ClientSearch } from '../../components/ClientSearch';

export const Route = createFileRoute('/clients/')({
  component: ClientSearch,
});
