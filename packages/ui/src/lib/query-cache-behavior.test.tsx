/**
 * Behavioral tests for the app's stale-while-revalidate caching.
 *
 * These mirror the QueryClient defaults configured in src/routes/__root.tsx and
 * assert the two behaviors the caching change is meant to deliver:
 *   1. Revisiting a page within staleTime serves cached data instantly — no
 *      refetch, no loading state (fixes "queries the table every time" + the
 *      laggy loading screen on every visit).
 *   2. When the query key changes, the previous data stays on screen while the
 *      new data loads (keepPreviousData) — "show old data until new loads".
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { useState } from 'react';
import {
  QueryClient,
  QueryClientProvider,
  keepPreviousData,
  useQuery,
} from '@tanstack/react-query';

// Same defaults as the production client in src/routes/__root.tsx.
const makeClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        gcTime: 24 * 60 * 60 * 1000,
        refetchOnWindowFocus: false,
        placeholderData: keepPreviousData,
        retry: 1,
      },
    },
  });

function Probe({
  id,
  fetcher,
}: {
  id: string;
  fetcher: (id: string) => Promise<string>;
}) {
  const q = useQuery<string>({
    queryKey: ['probe', id],
    queryFn: () => fetcher(id),
  });
  return (
    <div>
      <span data-testid="status">{q.isLoading ? 'loading' : 'ready'}</span>
      <span data-testid="data">{q.data ?? ''}</span>
    </div>
  );
}

describe('QueryClient caching (stale-while-revalidate)', () => {
  it('serves cached data on revisit within staleTime — no refetch, no loading screen', async () => {
    const fetcher = vi.fn(async (id: string) => `data-${id}`);
    const client = makeClient();

    const first = render(
      <QueryClientProvider client={client}>
        <Probe id="A" fetcher={fetcher} />
      </QueryClientProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('data')).toHaveTextContent('data-A'),
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    first.unmount();

    // Revisit: remount against the SAME client, still within staleTime.
    render(
      <QueryClientProvider client={client}>
        <Probe id="A" fetcher={fetcher} />
      </QueryClientProvider>,
    );

    // Cached data shown immediately (never 'loading'), and no extra fetch fired.
    expect(screen.getByTestId('status')).toHaveTextContent('ready');
    expect(screen.getByTestId('data')).toHaveTextContent('data-A');
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('keeps previous data visible while the next key loads (keepPreviousData)', async () => {
    let resolveB: ((v: string) => void) | null = null;
    const fetcher = vi.fn((id: string) =>
      id === 'A'
        ? Promise.resolve('data-A')
        : new Promise<string>((r) => {
            resolveB = r;
          }),
    );
    const client = makeClient();

    function Switcher() {
      const [id, setId] = useState('A');
      return (
        <div>
          <button onClick={() => setId('B')}>next</button>
          <Probe id={id} fetcher={fetcher} />
        </div>
      );
    }

    render(
      <QueryClientProvider client={client}>
        <Switcher />
      </QueryClientProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('data')).toHaveTextContent('data-A'),
    );

    // Switch to B (its fetch stays pending): old data-A must remain, not a spinner.
    act(() => {
      screen.getByText('next').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('ready');
    expect(screen.getByTestId('data')).toHaveTextContent('data-A');

    // Resolve B: new data swaps in.
    await act(async () => {
      resolveB?.('data-B');
    });
    await waitFor(() =>
      expect(screen.getByTestId('data')).toHaveTextContent('data-B'),
    );
  });
});
