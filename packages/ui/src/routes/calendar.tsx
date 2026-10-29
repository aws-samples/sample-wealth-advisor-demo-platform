import { createFileRoute } from '@tanstack/react-router';
import { CalendarPage } from '../components/Calendar';

export const Route = createFileRoute('/calendar')({
  component: CalendarPage,
});
