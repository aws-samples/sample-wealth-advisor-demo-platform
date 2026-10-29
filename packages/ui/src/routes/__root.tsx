import { createRootRoute, Outlet } from '@tanstack/react-router';
import { ImprovedChatWidget } from '../components/ImprovedChatWidget';
import CognitoAuth from '../components/CognitoAuth';
import ApiProvider from '../components/ApiProvider';
import RuntimeConfigProvider from '../components/RuntimeConfig';
import { QueryClient, keepPreviousData } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';

// Stale-while-revalidate defaults: serve cached data instantly, then check for
// new data in the background and swap it in only once it has loaded — so
// revisiting a page never drops to a skeleton when we already have data.
// - staleTime 5m: don't re-hit the API on every mount within the window
// - gcTime 24h: keep cached data around across navigation (default 5m evicted
//   it, which is why revisits showed the loading screen again)
// - placeholderData keepPreviousData: while a query key changes (client switch,
//   pagination) keep showing the previous data instead of a spinner
// - refetchOnWindowFocus off: no surprise refetch/flash when tabbing back
const queryClient = new QueryClient({
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

// Persist the query cache to localStorage so a full reload / new tab is not
// cold: the last-known data is rehydrated and shown instantly while it
// revalidates in the background. maxAge matches gcTime; bump `buster` to
// invalidate persisted caches after an incompatible data-shape change.
const persister = createSyncStoragePersister({
  storage: typeof window !== 'undefined' ? window.localStorage : undefined,
  key: 'wmp-query-cache',
});

export const Route = createRootRoute({
  component: () => (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: 24 * 60 * 60 * 1000,
        buster: 'wmp-v1',
      }}
    >
      <RuntimeConfigProvider>
        <CognitoAuth>
          <ApiProvider>
            <Outlet />
            <ImprovedChatWidget />
          </ApiProvider>
        </CognitoAuth>
      </RuntimeConfigProvider>
    </PersistQueryClientProvider>
  ),
});
