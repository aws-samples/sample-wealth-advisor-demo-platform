import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ClientSearch } from './ClientSearch';

// Mock dependencies
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('./PageLayout', () => ({
  PageLayout: ({
    children,
    headerContent,
  }: {
    children: React.ReactNode;
    headerContent?: React.ReactNode;
  }) => (
    <div data-testid="sidebar">
      {headerContent}
      {children}
    </div>
  ),
  SearchBox: ({
    onSearch,
    onChange,
  }: {
    onSearch?: () => void;
    onChange?: (v: string) => void;
  }) => (
    <input
      data-testid="nl-search"
      placeholder="Search"
      onChange={(e) => onChange?.(e.target.value)}
      onKeyDown={(e) => e.key === 'Enter' && onSearch?.()}
    />
  ),
}));

vi.mock('./ClientGraphView', () => ({
  ClientGraphView: () => <div>Graph View</div>,
}));

vi.mock('../hooks/useApiClient', () => ({
  useApiClient: () => ({
    clients: vi.fn().mockResolvedValue({
      clients: [],
      total: 0,
    }),
    clientsSearch: vi.fn().mockResolvedValue({
      success: true,
      data: [
        {
          client_id: 'CL001',
          first_name: 'John',
          last_name: 'Doe',
          segment: 'HNW',
          risk_tolerance: 'Moderate',
          created_date: '2024-01-01',
          net_worth: 5000000,
          aum: 3000000,
        },
      ],
    }),
  }),
}));

vi.mock('../hooks/useRuntimeConfig', () => ({
  useRuntimeConfig: () => ({
    intelligenceApiUrl: 'http://localhost:8001',
    apiUrl: 'http://localhost:8000',
    apis: {
      Api: 'http://localhost:8000',
      IntelligenceApi: 'http://localhost:8001',
    },
  }),
}));

describe('ClientSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders search inputs', () => {
    render(<ClientSearch />);

    const searchInputs = screen.getAllByPlaceholderText(/search/i);
    expect(searchInputs.length).toBeGreaterThan(0);
  });

  it.skip('handles natural language search on Enter key', async () => {
    const { useApiClient } = await import('../hooks/useApiClient');
    const mockApi = useApiClient();

    render(<ClientSearch />);

    const nlSearchInput = screen.getByPlaceholderText(/natural language/i);

    fireEvent.change(nlSearchInput, {
      target: { value: 'show me HNW clients' },
    });
    fireEvent.keyDown(nlSearchInput, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(mockApi.clientsSearch).toHaveBeenCalledWith({
        query: 'show me HNW clients',
      });
    });
  });

  it.skip('displays search results', async () => {
    render(<ClientSearch />);

    const nlSearchInput = screen.getByPlaceholderText(/natural language/i);

    fireEvent.change(nlSearchInput, { target: { value: 'show me clients' } });
    fireEvent.keyDown(nlSearchInput, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  it('maintains separate state for two search boxes', async () => {
    render(<ClientSearch />);

    await waitFor(() => {
      const searchInputs = screen.getAllByRole('textbox');
      expect(searchInputs.length).toBeGreaterThan(1);
    });

    const searchInputs = screen.getAllByRole('textbox');
    const firstInput = searchInputs[0] as HTMLInputElement;
    const secondInput = searchInputs.find((input) =>
      input.getAttribute('placeholder')?.includes('15M'),
    ) as HTMLInputElement;

    fireEvent.change(firstInput, { target: { value: 'query 1' } });
    fireEvent.change(secondInput!, { target: { value: 'query 2' } });

    expect(firstInput.value).toBe('query 1');
    expect(secondInput.value).toBe('query 2');
  });
});
