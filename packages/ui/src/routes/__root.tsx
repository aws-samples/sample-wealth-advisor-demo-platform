import { createRootRoute, Outlet } from '@tanstack/react-router';
import { ImprovedChatWidget } from '../components/ImprovedChatWidget';
import CognitoAuth from '../components/CognitoAuth';
import ApiProvider from '../components/ApiProvider';
import RuntimeConfigProvider from '../components/RuntimeConfig';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

export const Route = createRootRoute({
  component: () => (
    <QueryClientProvider client={queryClient}>
      <RuntimeConfigProvider>
        <CognitoAuth>
          <ApiProvider>
            <Outlet />
            <ImprovedChatWidget />
          </ApiProvider>
        </CognitoAuth>
      </RuntimeConfigProvider>
    </QueryClientProvider>
  ),
});
