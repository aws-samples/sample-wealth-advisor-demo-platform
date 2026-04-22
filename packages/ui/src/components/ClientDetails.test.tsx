import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ClientDetails } from './ClientDetails';

vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({ clientId: 'CL001' }),
  useNavigate: () => vi.fn(),
}));

vi.mock('./Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar">Sidebar</div>,
}));

vi.mock('../hooks/useApiClient', () => ({
  useApiClient: () => ({
    clientDetails: vi.fn().mockResolvedValue({
      clientId: 'CL001',
      customerName: 'John Doe',
      segment: 'HNW',
      aum: 5000000,
    }),
    clientHoldings: vi.fn().mockResolvedValue([]),
    clientTransactions: vi.fn().mockResolvedValue([]),
  }),
}));

vi.mock('../hooks/useReportApiClient', () => ({
  useReportApiClient: () => ({
    generateReport: vi.fn().mockResolvedValue({}),
  }),
}));

describe('ClientDetails', () => {
  it.skip('renders client details', async () => {
    render(<ClientDetails />);

    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    });
  });

  it.skip('loads client data', async () => {
    const { useApiClient } = await import('../hooks/useApiClient');
    const mockApi = useApiClient();

    render(<ClientDetails />);

    await waitFor(() => {
      expect(mockApi.clientDetails).toHaveBeenCalledWith({ clientId: 'CL001' });
    });
  });
});
