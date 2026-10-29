import { createFileRoute } from '@tanstack/react-router';
import { MessagesPage } from '../components/Messages';

export const Route = createFileRoute('/messages')({
  component: MessagesPage,
});
