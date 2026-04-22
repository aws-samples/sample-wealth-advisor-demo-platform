import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AdvisorDashboard } from './AdvisorDashboard';

vi.mock('./PageLayout', () => ({
  PageLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="sidebar">{children}</div>
  ),
  SearchBox: () => <div />,
}));

const mockApi = {
  dashboardSummary: vi.fn().mockResolvedValue({
    totalClients: 100,
    totalAum: 1000000000,
    avgSatisfaction: 4.5,
  }),
  aumTrends: vi.fn().mockResolvedValue({ trends: [] }),
  clientSegments: vi.fn().mockResolvedValue({ segments: [] }),
  marketThemes: vi.fn().mockResolvedValue({ themes: [] }),
  topClients: vi.fn().mockResolvedValue({ clients: [] }),
};

vi.mock('../hooks/useApiClient', () => ({
  useApiClient: () => mockApi,
}));

const mockQueryOptions = (fn: (...args: any[]) => any) => ({
  queryOptions: (...args: any[]) => ({
    queryKey: ['mock', ...args],
    queryFn: () => fn(...args),
  }),
  queryFilter: (...args: any[]) => ({ queryKey: ['mock', ...args] }),
});

vi.mock('../hooks/useApi', () => ({
  useApi: () => ({
    dashboardSummary: mockQueryOptions(mockApi.dashboardSummary),
    aumTrends: mockQueryOptions(mockApi.aumTrends),
    clientSegments: mockQueryOptions(mockApi.clientSegments),
    marketThemes: mockQueryOptions(mockApi.marketThemes),
    topClients: mockQueryOptions(mockApi.topClients),
  }),
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

describe('AdvisorDashboard', () => {
  it('renders dashboard', async () => {
    render(<AdvisorDashboard />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    });
  });

  it.skip('loads dashboard data', async () => {
    render(<AdvisorDashboard />, { wrapper });

    await waitFor(() => {
      expect(mockApi.dashboardSummary).toHaveBeenCalled();
    });
  });
});
