import { createFileRoute } from '@tanstack/react-router';
import { ClientDetails } from '../../components/ClientDetails';

export const Route = createFileRoute('/clients/$clientId')({
  component: ClientDetails,
});
